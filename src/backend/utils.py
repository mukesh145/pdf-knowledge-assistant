import yaml
from pathlib import Path


def load_config(config_path: str = None) -> dict:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to the config file. If None, uses default path.
        
    Returns:
        Dictionary containing configuration values
    """
    if config_path is None:
        # Get the project root directory (parent of src)
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "configs" / "backend_config.yaml"
    else:
        config_path = Path(config_path)
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config
