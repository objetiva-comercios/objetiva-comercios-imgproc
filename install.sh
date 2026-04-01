#!/bin/bash
# =============================================================================
# Image Standardizer — Instalador automatico
# =============================================================================
# Uso:
#   curl -sL https://raw.githubusercontent.com/objetiva-comercios/objetiva-comercios-imgproc/main/install.sh | bash
#
# O desde el VPS:
#   bash install.sh
#
# Que hace:
#   1. Verifica dependencias (git, docker, docker compose)
#   2. Clona o actualiza el repositorio
#   3. Construye la imagen Docker (incluye descarga del modelo rembg)
#   4. Levanta el servicio con docker compose
#   5. Ejecuta health check hasta confirmar que esta corriendo
#
# Requisitos:
#   - Docker >= 20.10 con el plugin compose v2
#   - Git
#   - ~3 GB de disco (imagen Docker + modelo ONNX)
#   - 2 GB de RAM disponibles para el container
# =============================================================================

set -euo pipefail

# -- Config ------------------------------------------------------------------
INSTALL_DIR="${HOME}/proyectos"
REPO_DIR="${INSTALL_DIR}/objetiva-comercios-imgproc"
REPO_URL="https://github.com/objetiva-comercios/objetiva-comercios-imgproc.git"
CONTAINER_NAME="imgproc"
HEALTH_PORT=8010
HEALTH_ENDPOINT="/health"
MAX_RETRIES=30
RETRY_INTERVAL=3

# -- Colores -----------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# -- Banner ------------------------------------------------------------------
echo ""
echo "=========================================="
echo "  Image Standardizer — Instalador"
echo "=========================================="
echo ""

# -- Verificar dependencias --------------------------------------------------
info "Verificando dependencias..."

command -v git >/dev/null 2>&1 || error "git no esta instalado"
ok "git encontrado"

command -v docker >/dev/null 2>&1 || error "docker no esta instalado"
ok "docker encontrado"

docker compose version >/dev/null 2>&1 || error "docker compose v2 no esta instalado (se requiere 'docker compose', no 'docker-compose')"
ok "docker compose v2 encontrado"

# -- Manejar instalacion previa ----------------------------------------------
REINSTALL=false
if [ -d "$REPO_DIR" ]; then
    warn "Instalacion previa detectada en $REPO_DIR"
    info "Deteniendo servicios existentes..."
    cd "$REPO_DIR"
    docker compose down 2>/dev/null || true
    cd "$INSTALL_DIR"

    # Backup de config personalizada
    if [ -f "$REPO_DIR/config/settings.yaml" ]; then
        info "Respaldando config/settings.yaml..."
        cp "$REPO_DIR/config/settings.yaml" "/tmp/imgproc-settings.yaml.bak"
    fi

    info "Eliminando instalacion anterior..."
    rm -rf "$REPO_DIR"
    REINSTALL=true
fi

# -- Clonar repositorio -----------------------------------------------------
info "Clonando repositorio..."
mkdir -p "$INSTALL_DIR"
git clone "$REPO_URL" "$REPO_DIR"
ok "Repositorio clonado en $REPO_DIR"

cd "$REPO_DIR"

# -- Restaurar config --------------------------------------------------------
if [ "$REINSTALL" = true ] && [ -f "/tmp/imgproc-settings.yaml.bak" ]; then
    info "Restaurando config/settings.yaml..."
    cp "/tmp/imgproc-settings.yaml.bak" "$REPO_DIR/config/settings.yaml"
    rm -f "/tmp/imgproc-settings.yaml.bak"
    ok "Configuracion restaurada"
fi

# -- Build y up ---------------------------------------------------------------
info "Construyendo imagen Docker (incluye descarga del modelo rembg, puede tardar varios minutos)..."
if [ "$REINSTALL" = true ]; then
    docker compose build --no-cache
else
    docker compose build
fi
ok "Imagen construida"

info "Levantando servicio..."
docker compose up -d
ok "Container iniciado"

# -- Health check -------------------------------------------------------------
info "Esperando que el servicio este listo (el modelo tarda ~60-90s en cargar)..."
RETRIES=0
while [ $RETRIES -lt $MAX_RETRIES ]; do
    if curl -sf "http://localhost:${HEALTH_PORT}${HEALTH_ENDPOINT}" >/dev/null 2>&1; then
        ok "Servicio saludable"
        break
    fi
    RETRIES=$((RETRIES + 1))
    sleep $RETRY_INTERVAL
done

if [ $RETRIES -eq $MAX_RETRIES ]; then
    warn "El servicio no respondio despues de $((MAX_RETRIES * RETRY_INTERVAL))s"
    info "Mostrando logs para diagnostico:"
    docker compose logs --tail 40
    error "Health check fallido. Revisar logs arriba."
fi

# -- Resultado final ----------------------------------------------------------
echo ""
echo "=========================================="
echo -e "  ${GREEN}Image Standardizer — Instalado${NC}"
echo "=========================================="
echo ""
echo "  Endpoints:"
echo "    POST /process  — Procesar imagen"
echo "    GET  /health   — Health check"
echo "    GET  /status   — Metricas y estado"
echo "    GET  /config   — Configuracion activa"
echo "    POST /config   — Actualizar configuracion"
echo "    GET  /ui       — Web UI de configuracion"
echo ""
echo "  URL local: http://localhost:8010"
echo ""
echo "  Comandos utiles:"
echo "    docker compose -f $REPO_DIR/docker-compose.yml logs -f    # Ver logs"
echo "    docker compose -f $REPO_DIR/docker-compose.yml restart    # Reiniciar"
echo "    docker compose -f $REPO_DIR/docker-compose.yml down       # Detener"
echo ""
echo "  Config: $REPO_DIR/config/settings.yaml (hot-reload, sin restart)"
echo ""
