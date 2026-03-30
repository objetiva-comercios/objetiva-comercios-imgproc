"""
JobQueue — Gateway entre la API HTTP y el processor.

Controla concurrencia via asyncio.Semaphore, gestiona timeouts y rechazos,
y ejecuta el trabajo CPU-bound en asyncio.to_thread para no bloquear el event loop.

Exporta:
    JobQueue          — Cola principal con submit_job()
    QueueFullError    — Levantada cuando max_queue_size se alcanza (-> 503)
    QueueTimeoutError — Levantada cuando timeout expira esperando semaphore (-> 504)
"""

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------

class QueueFullError(Exception):
    """Cola llena — el request debe recibir HTTP 503."""
    pass


class QueueTimeoutError(Exception):
    """Timeout esperando semaphore disponible — el request debe recibir HTTP 504."""
    pass


# ---------------------------------------------------------------------------
# Estructuras de estado
# ---------------------------------------------------------------------------

@dataclass
class JobRecord:
    """Registro de un job completado (exitoso o fallido) en el historial."""
    article_id: str
    status: str                  # "completed" | "error"
    processing_time_ms: int
    model_used: str
    timestamp: str               # ISO 8601 UTC
    original_size: str | None = None   # "WxH" — per D-06
    output_size: str | None = None     # "WxH" — per D-06
    error: str | None = None


@dataclass
class QueueState:
    """Estado en memoria de la cola. Se actualiza en cada transición."""
    active_jobs: int = 0
    queued_jobs: int = 0
    total_processed: int = 0
    total_errors: int = 0
    job_history: deque = field(default_factory=lambda: deque(maxlen=50))


# ---------------------------------------------------------------------------
# JobQueue
# ---------------------------------------------------------------------------

class JobQueue:
    """
    Cola de procesamiento de imágenes con control de concurrencia.

    Flujo de un job:
        1. Verificar si max_queue_size se alcanzó -> QueueFullError (503)
        2. Incrementar queued_jobs
        3. Esperar asyncio.Semaphore con timeout -> QueueTimeoutError (504)
        4. Decrementar queued_jobs, incrementar active_jobs
        5. Ejecutar process_fn en asyncio.to_thread (CPU-bound safe)
        6. Decrementar active_jobs, liberar semaphore
        7. Actualizar contadores y historial
    """

    def __init__(
        self,
        max_concurrent: int = 1,
        max_queue_size: int = 10,
        timeout_seconds: float = 120,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_queue_size = max_queue_size
        self._timeout_seconds = timeout_seconds
        self._max_concurrent = max_concurrent
        self._state = QueueState()

    # ------------------------------------------------------------------
    # Propiedades de lectura
    # ------------------------------------------------------------------

    @property
    def state(self) -> QueueState:
        return self._state

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    async def submit_job(
        self,
        process_fn: Callable,
        image_bytes: bytes,
        article_id: str,
        config_snapshot: Any,   # AppConfig snapshot (debe tomarse ANTES de llamar)
        rembg_session: Any,
    ) -> Any:
        """
        Encola y ejecuta un job de procesamiento de imagen.

        Args:
            process_fn:      Función sincrónica (process_image). Se ejecutará en
                             asyncio.to_thread — nunca en el event loop.
            image_bytes:     Bytes de la imagen original.
            article_id:      Identificador del artículo (para logs y historial).
            config_snapshot: Snapshot inmutable de AppConfig tomado antes del call.
                             Se pasa directamente a process_fn sin modificación.
            rembg_session:   Sesión global de rembg (None en tests sin rembg).

        Returns:
            Lo que retorne process_fn.

        Raises:
            QueueFullError:    Si queued_jobs >= max_queue_size.
            QueueTimeoutError: Si el semaphore no se libera antes de timeout_seconds.
        """
        # CHECK 1: Cola llena → 503 inmediato, sin encolar (per QUEUE-02)
        if self._state.queued_jobs >= self._max_queue_size:
            logger.warning(json.dumps({
                "level": "warning",
                "event": "queue_full",
                "article_id": article_id,
                "queued_jobs": self._state.queued_jobs,
                "max_queue_size": self._max_queue_size,
            }))
            raise QueueFullError(
                f"Queue full: {self._state.queued_jobs}/{self._max_queue_size} slots ocupados"
            )

        # Registrar en la cola de espera
        self._state.queued_jobs += 1

        try:
            # CHECK 2: Esperar semaphore con timeout → 504 si expira (per QUEUE-03)
            try:
                await asyncio.wait_for(
                    self._semaphore.acquire(),
                    timeout=self._timeout_seconds,
                )
            except asyncio.TimeoutError:
                # Descontar: nunca llegamos a estar activos
                self._state.queued_jobs -= 1
                logger.warning(json.dumps({
                    "level": "warning",
                    "event": "queue_timeout",
                    "article_id": article_id,
                    "timeout_seconds": self._timeout_seconds,
                }))
                raise QueueTimeoutError(
                    f"Timeout: esperó {self._timeout_seconds}s y el semaphore no quedó libre"
                )

            # Semaphore adquirido: mover de "en cola" a "activo"
            self._state.queued_jobs -= 1
            self._state.active_jobs += 1

            start = time.monotonic()
            try:
                # CRÍTICO: to_thread para no bloquear el event loop (per QUEUE-04)
                result = await asyncio.to_thread(
                    process_fn,
                    image_bytes,
                    article_id,
                    config_snapshot,
                    rembg_session,
                )

                elapsed_ms = int((time.monotonic() - start) * 1000)

                # Job exitoso: contadores y historial
                self._state.total_processed += 1
                self._state.job_history.append(JobRecord(
                    article_id=article_id,
                    status="completed",
                    processing_time_ms=elapsed_ms,
                    model_used=config_snapshot.rembg.model,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    original_size=getattr(result, "original_size", None),
                    output_size=getattr(result, "output_size", None),
                ))

                logger.info(json.dumps({
                    "level": "info",
                    "event": "job_complete",
                    "article_id": article_id,
                    "processing_time_ms": elapsed_ms,
                }))

                return result

            except Exception as exc:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                self._state.total_errors += 1
                self._state.job_history.append(JobRecord(
                    article_id=article_id,
                    status="error",
                    processing_time_ms=elapsed_ms,
                    model_used=config_snapshot.rembg.model,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error=str(exc),
                ))

                logger.error(json.dumps({
                    "level": "error",
                    "event": "job_error",
                    "article_id": article_id,
                    "error": str(exc),
                    "processing_time_ms": elapsed_ms,
                }))

                raise

            finally:
                # Siempre liberar: active_jobs y semaphore
                self._state.active_jobs -= 1
                self._semaphore.release()

        except (QueueFullError, QueueTimeoutError):
            # Estas ya manejaron su propio cleanup; re-raise sin tocar estado adicional
            raise
