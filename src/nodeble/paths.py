from pathlib import Path


def get_data_dir() -> Path:
    """Return ~/.nodeble/ data directory, creating it if needed."""
    data_dir = Path.home() / ".nodeble"
    data_dir.mkdir(exist_ok=True)
    return data_dir


def get_config_dir() -> Path:
    config_dir = get_data_dir() / "config"
    config_dir.mkdir(exist_ok=True)
    return config_dir
