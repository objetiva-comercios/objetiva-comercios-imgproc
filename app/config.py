import yaml
from pathlib import Path

from app.models import AppConfig


class ConfigManager:
    def __init__(self, config_path: str = "config/settings.yaml"):
        self._config_path = Path(config_path)
        self._config: AppConfig = self._load()

    def _load(self) -> AppConfig:
        if self._config_path.exists():
            with open(self._config_path) as f:
                data = yaml.safe_load(f) or {}
            return AppConfig(**data)
        return AppConfig()

    def reload(self) -> None:
        self._config = self._load()

    @property
    def config(self) -> AppConfig:
        return self._config

    def get_snapshot(self) -> AppConfig:
        """Retorna copia profunda inmutable para un job. Per CONF-06."""
        return self._config.model_copy(deep=True)

    def update_config(self, new_config: AppConfig) -> None:
        """Actualiza config en memoria y persiste en YAML. Per CONF-03."""
        self._config = new_config
        with open(self._config_path, "w") as f:
            yaml.dump(
                new_config.model_dump(),
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
