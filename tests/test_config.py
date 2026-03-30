import pytest

from app.config import ConfigManager


def test_config_loads_yaml(config_manager):
    """ConfigManager carga settings.yaml y retorna AppConfig con valores correctos."""
    config = config_manager.config
    assert config.rembg.model == "birefnet-lite"
    assert config.output.size == 800
    assert config.queue.max_concurrent == 1


def test_config_defaults_without_file(tmp_path):
    """ConfigManager con path inexistente retorna AppConfig con defaults."""
    nonexistent = str(tmp_path / "nonexistent.yaml")
    cm = ConfigManager(config_path=nonexistent)
    assert cm.config.rembg.model == "birefnet-lite"
    assert cm.config.output.size == 800
    assert cm.config.queue.max_concurrent == 1


def test_config_snapshot_immutable(config_manager):
    """get_snapshot() retorna copia profunda; modificar la copia no afecta el original."""
    snap = config_manager.get_snapshot()
    snap.output.size = 1200
    # El original no debe verse afectado
    assert config_manager.config.output.size == 800


def test_config_reload(tmp_settings_yaml):
    """Modificar el YAML en disco y llamar reload() actualiza la config."""
    cm = ConfigManager(config_path=tmp_settings_yaml)
    assert cm.config.output.size == 800

    # Modificar el archivo en disco
    import yaml
    with open(tmp_settings_yaml) as f:
        data = yaml.safe_load(f)
    data["output"]["size"] = 1024
    with open(tmp_settings_yaml, "w") as f:
        yaml.dump(data, f)

    # Recargar y verificar
    cm.reload()
    assert cm.config.output.size == 1024
