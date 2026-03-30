FROM python:3.11-slim

# Dependencias del sistema para Pillow y onnxruntime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Variables de entorno para limitar threads de ONNX (evitar thread explosion)
ENV OMP_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2

WORKDIR /app

# Copiar requirements primero (cache de Docker layers)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-descargar modelo rembg en build time (per DOCK-01)
COPY scripts/ scripts/
RUN python scripts/download_models.py birefnet-lite

# Copiar codigo de la aplicacion
COPY app/ app/
COPY config/ config/

# Puerto del servicio
EXPOSE 8010

# HEALTHCHECK con start_period: 90s porque el modelo tarda en cargar (per DOCK-03)
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8010/health || exit 1

# Ejecutar con uvicorn
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
