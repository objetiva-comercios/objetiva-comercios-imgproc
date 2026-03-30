from pydantic import BaseModel
from typing import Optional


class RembgConfig(BaseModel):
    model: str = "birefnet-lite"
    alpha_matting: bool = False
    alpha_matting_foreground_threshold: int = 240
    alpha_matting_background_threshold: int = 10
    alpha_matting_erode_size: int = 10


class OutputConfig(BaseModel):
    size: int = 800
    format: str = "webp"
    quality: int = 85
    background_color: list[int] = [255, 255, 255]


class PaddingConfig(BaseModel):
    enabled: bool = True
    percent: int = 10


class AutocropConfig(BaseModel):
    enabled: bool = True
    threshold: int = 10


class EnhancementConfig(BaseModel):
    brightness: float = 1.0
    contrast: float = 1.0


class QueueConfig(BaseModel):
    max_concurrent: int = 1
    max_queue_size: int = 10
    timeout_seconds: int = 120


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8010
    log_level: str = "info"


class AppConfig(BaseModel):
    rembg: RembgConfig = RembgConfig()
    output: OutputConfig = OutputConfig()
    padding: PaddingConfig = PaddingConfig()
    autocrop: AutocropConfig = AutocropConfig()
    enhancement: EnhancementConfig = EnhancementConfig()
    queue: QueueConfig = QueueConfig()
    server: ServerConfig = ServerConfig()


class ProcessingResult(BaseModel):
    image_bytes: bytes
    article_id: str
    processing_time_ms: int
    model_used: str
    original_size: str       # "WxH"
    output_size: str         # "WxH"
    steps_applied: list[str]


class ErrorResponse(BaseModel):
    error: str
    detail: str
    article_id: Optional[str] = None
