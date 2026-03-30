"""
Tests unitarios para app/queue.py — JobQueue con asyncio.Semaphore.

Cubre todos los escenarios definidos en el plan 01-03:
- Concurrencia controlada (max_concurrent)
- 503 inmediato cuando cola llena
- 504 cuando timeout expira esperando semaphore
- Estado correcto (active_jobs, queued_jobs, total_processed, total_errors)
- Trabajo CPU-bound en asyncio.to_thread (no bloquea event loop)
- Config snapshot llega correctamente a process_fn
"""

import asyncio
import threading
import time
import pytest

from app.queue import JobQueue, QueueFullError, QueueTimeoutError
from app.models import AppConfig


# ---------------------------------------------------------------------------
# Fixtures y helpers
# ---------------------------------------------------------------------------

def make_config(**kwargs) -> AppConfig:
    """Crea un AppConfig con valores de cola personalizados."""
    config = AppConfig()
    if "max_concurrent" in kwargs:
        config.queue.max_concurrent = kwargs["max_concurrent"]
    if "max_queue_size" in kwargs:
        config.queue.max_queue_size = kwargs["max_queue_size"]
    if "timeout_seconds" in kwargs:
        config.queue.timeout_seconds = kwargs["timeout_seconds"]
    return config


def make_slow_process_fn(sleep_seconds: float):
    """Devuelve un process_fn sincrónico que duerme N segundos."""
    def process_fn(image_bytes, article_id, config, rembg_session):
        time.sleep(sleep_seconds)
        return f"result-{article_id}"
    return process_fn


def make_fast_process_fn():
    """Devuelve un process_fn sincrónico que termina casi inmediato."""
    def process_fn(image_bytes, article_id, config, rembg_session):
        return f"result-{article_id}"
    return process_fn


def make_failing_process_fn():
    """Devuelve un process_fn que lanza una excepción."""
    def process_fn(image_bytes, article_id, config, rembg_session):
        raise ValueError(f"Error procesando {article_id}")
    return process_fn


def make_thread_tracking_process_fn(thread_names: list):
    """Registra el nombre del thread en que se ejecuta process_fn."""
    def process_fn(image_bytes, article_id, config, rembg_session):
        thread_names.append(threading.current_thread().name)
        return f"result-{article_id}"
    return process_fn


def make_config_capturing_process_fn(captured_configs: list):
    """Captura el config que recibe process_fn."""
    def process_fn(image_bytes, article_id, config, rembg_session):
        captured_configs.append(config)
        return f"result-{article_id}"
    return process_fn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_max_concurrent():
    """Solo 1 job activo a la vez con max_concurrent=1. El segundo espera."""
    queue = JobQueue(max_concurrent=1, max_queue_size=10, timeout_seconds=5)

    # Job lento que ocupa el semaphore por 0.3s
    slow_fn = make_slow_process_fn(0.3)
    fast_fn = make_fast_process_fn()

    # Lanzamos ambos casi simultáneamente
    task1 = asyncio.create_task(
        queue.submit_job(slow_fn, b"img", "art-1", AppConfig(), None)
    )
    # Pequeña pausa para asegurar que task1 adquirió el semaphore primero
    await asyncio.sleep(0.05)

    # En este momento, art-1 está activo
    assert queue.state.active_jobs == 1, f"Esperaba 1 activo, got {queue.state.active_jobs}"

    task2 = asyncio.create_task(
        queue.submit_job(fast_fn, b"img", "art-2", AppConfig(), None)
    )
    await asyncio.sleep(0.05)

    # art-2 debe estar en cola, no activo todavía
    assert queue.state.queued_jobs == 1, f"Esperaba 1 en cola, got {queue.state.queued_jobs}"
    assert queue.state.active_jobs == 1

    # Esperar a que ambos terminen
    results = await asyncio.gather(task1, task2)
    assert results[0] == "result-art-1"
    assert results[1] == "result-art-2"

    # Estado final limpio
    assert queue.state.active_jobs == 0
    assert queue.state.queued_jobs == 0
    assert queue.state.total_processed == 2


async def test_503_queue_full():
    """Con max_queue_size=1: tercer submit cuando semaphore ocupado y cola llena -> QueueFullError."""
    # max_concurrent=1, max_queue_size=1
    queue = JobQueue(max_concurrent=1, max_queue_size=1, timeout_seconds=5)

    slow_fn = make_slow_process_fn(2.0)  # ocupa semaphore por 2s
    fast_fn = make_fast_process_fn()

    # Job 1: ocupa el semaphore
    task1 = asyncio.create_task(
        queue.submit_job(slow_fn, b"img", "art-1", AppConfig(), None)
    )
    await asyncio.sleep(0.05)  # art-1 activo

    # Job 2: entra en cola (max_queue_size=1, hay espacio)
    task2 = asyncio.create_task(
        queue.submit_job(fast_fn, b"img", "art-2", AppConfig(), None)
    )
    await asyncio.sleep(0.05)  # art-2 en cola

    assert queue.state.queued_jobs == 1, f"Esperaba 1 en cola, got {queue.state.queued_jobs}"

    # Job 3: cola llena -> QueueFullError INMEDIATO
    with pytest.raises(QueueFullError):
        await queue.submit_job(fast_fn, b"img", "art-3", AppConfig(), None)

    # Cancelar job1 y job2 para limpiar el test
    task1.cancel()
    task2.cancel()
    try:
        await asyncio.gather(task1, task2, return_exceptions=True)
    except Exception:
        pass


async def test_504_timeout():
    """Timeout esperando semaphore -> QueueTimeoutError (no 503, porque hay espacio en cola)."""
    # timeout_seconds muy corto: 0.1s
    queue = JobQueue(max_concurrent=1, max_queue_size=10, timeout_seconds=0.1)

    slow_fn = make_slow_process_fn(2.0)  # ocupa semaphore por 2s

    # Job 1: ocupa el semaphore
    task1 = asyncio.create_task(
        queue.submit_job(slow_fn, b"img", "art-1", AppConfig(), None)
    )
    await asyncio.sleep(0.05)  # art-1 activo

    # Job 2: entra a esperar en cola, pero timeout=0.1s -> QueueTimeoutError
    with pytest.raises(QueueTimeoutError):
        await queue.submit_job(make_fast_process_fn(), b"img", "art-2", AppConfig(), None)

    # Verificar que queued_jobs volvió a 0 correctamente (cleanup en timeout)
    assert queue.state.queued_jobs == 0, f"Esperaba queued_jobs=0, got {queue.state.queued_jobs}"

    # Cancelar job1 para limpiar
    task1.cancel()
    try:
        await task1
    except (asyncio.CancelledError, Exception):
        pass


async def test_state_tracking():
    """Estado se actualiza correctamente: active_jobs, queued_jobs, total_processed."""
    queue = JobQueue(max_concurrent=1, max_queue_size=10, timeout_seconds=5)
    states_during = []

    def tracking_fn(image_bytes, article_id, config, rembg_session):
        # Capturar estado durante ejecución
        states_during.append({
            "active_jobs": queue.state.active_jobs,
            "queued_jobs": queue.state.queued_jobs,
        })
        return f"result-{article_id}"

    assert queue.state.active_jobs == 0
    assert queue.state.total_processed == 0

    await queue.submit_job(tracking_fn, b"img", "art-1", AppConfig(), None)

    # Durante la ejecución, active_jobs debía ser 1
    assert len(states_during) == 1
    assert states_during[0]["active_jobs"] == 1

    # Después de completar
    assert queue.state.active_jobs == 0
    assert queue.state.queued_jobs == 0
    assert queue.state.total_processed == 1


async def test_error_tracking():
    """Job que falla: total_errors incrementado, active_jobs vuelve a 0."""
    queue = JobQueue(max_concurrent=1, max_queue_size=10, timeout_seconds=5)
    failing_fn = make_failing_process_fn()

    with pytest.raises(ValueError, match="Error procesando"):
        await queue.submit_job(failing_fn, b"img", "art-fail", AppConfig(), None)

    assert queue.state.total_errors == 1
    assert queue.state.total_processed == 0
    assert queue.state.active_jobs == 0


async def test_to_thread():
    """process_fn se ejecuta en un thread diferente al MainThread (event loop)."""
    queue = JobQueue(max_concurrent=1, max_queue_size=10, timeout_seconds=5)
    thread_names = []

    thread_tracking_fn = make_thread_tracking_process_fn(thread_names)

    await queue.submit_job(thread_tracking_fn, b"img", "art-1", AppConfig(), None)

    assert len(thread_names) == 1, "process_fn no se ejecutó"
    # asyncio.to_thread() corre en el ThreadPoolExecutor, nunca en MainThread
    assert thread_names[0] != "MainThread", (
        f"process_fn corrió en MainThread — no usa asyncio.to_thread: {thread_names[0]}"
    )


async def test_config_snapshot():
    """El config pasado a submit_job llega exactamente a process_fn (misma referencia o valor)."""
    queue = JobQueue(max_concurrent=1, max_queue_size=10, timeout_seconds=5)
    captured = []

    config_capturing_fn = make_config_capturing_process_fn(captured)

    config_in = AppConfig()
    config_in.rembg.model = "birefnet-lite"

    await queue.submit_job(config_capturing_fn, b"img", "art-1", config_in, None)

    assert len(captured) == 1
    # El config que llega debe ser el mismo que pasamos
    assert captured[0].rembg.model == "birefnet-lite"
    # Verificar que es el mismo objeto (o al menos igual) — submit_job no debe transformarlo
    assert captured[0] == config_in


async def test_job_history():
    """Historial de jobs registra resultados correctamente."""
    queue = JobQueue(max_concurrent=1, max_queue_size=10, timeout_seconds=5)
    fast_fn = make_fast_process_fn()

    await queue.submit_job(fast_fn, b"img", "art-1", AppConfig(), None)

    assert len(queue.state.job_history) == 1
    record = queue.state.job_history[0]
    assert record.article_id == "art-1"
    assert record.status == "completed"
    assert record.processing_time_ms >= 0
    assert record.model_used == "birefnet-lite"  # default model


async def test_multiple_jobs_sequential():
    """Múltiples jobs se procesan en secuencia con max_concurrent=1."""
    queue = JobQueue(max_concurrent=1, max_queue_size=10, timeout_seconds=5)
    fast_fn = make_fast_process_fn()

    results = []
    for i in range(3):
        result = await queue.submit_job(fast_fn, b"img", f"art-{i}", AppConfig(), None)
        results.append(result)

    assert queue.state.total_processed == 3
    assert queue.state.total_errors == 0
    assert len(queue.state.job_history) == 3
