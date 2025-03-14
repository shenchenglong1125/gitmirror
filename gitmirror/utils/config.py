import os
import json
import logging
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger('github-gitea-mirror')

# Default configuration for repositories
DEFAULT_CONFIG = {
    "mirror_metadata": False,
    "mirror_issues": False,
    "mirror_pull_requests": False,
    "mirror_labels": False,
    "mirror_milestones": False,
    "mirror_wiki": False,
    "mirror_releases": False
}

def load_config():
    """Load configuration from environment variables"""
    # Load environment variables from .env file
    logger.debug("Loading environment variables from .env file...")
    load_dotenv()
    
    # Get configuration from environment variables
    github_token = os.getenv('GITHUB_TOKEN')
    gitea_token = os.getenv('GITEA_TOKEN')
    gitea_url = os.getenv('GITEA_URL', '').rstrip('/')
    
    logger.debug(f"GITEA_URL: {gitea_url}")
    logger.debug(f"GITHUB_TOKEN: {'*' * 5 + github_token[-5:] if github_token else 'Not set'}")
    logger.debug(f"GITEA_TOKEN: {'*' * 5 + gitea_token[-5:] if gitea_token else 'Not set'}")
    
    return {
        'github_token': github_token,
        'gitea_token': gitea_token,
        'gitea_url': gitea_url
    }

def get_config_dir():
    """Get the directory where configuration files are stored."""
    config_dir = os.environ.get("GITMIRROR_CONFIG_DIR", "/app/data/config")
    
    # Create directory if it doesn't exist
    Path(config_dir).mkdir(parents=True, exist_ok=True)
    
    return config_dir

def get_default_config():
    """Get the default configuration for repositories."""
    config_dir = get_config_dir()
    default_config_path = os.path.join(config_dir, "default.json")
    
    if os.path.exists(default_config_path):
        try:
            with open(default_config_path, 'r') as f:
                config = json.load(f)
                return config
        except Exception as e:
            logger.error(f"Error loading default config: {e}")
    
    # If no default config exists or there was an error, return the hardcoded default
    return DEFAULT_CONFIG.copy()

def save_default_config(config):
    """Save the default configuration for repositories."""
    config_dir = get_config_dir()
    default_config_path = os.path.join(config_dir, "default.json")
    
    try:
        with open(default_config_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving default config: {e}")
        return False

def get_repo_config_path(github_repo, gitea_owner, gitea_repo):
    """Get the path to the repository configuration file."""
    config_dir = get_config_dir()
    
    # Normalize GitHub repository name
    # If it's a URL, extract the owner/repo part
    if github_repo.startswith('http'):
        parts = github_repo.rstrip('/').rstrip('.git').split('/')
        if len(parts) >= 2:
            github_repo = f"{parts[-2]}/{parts[-1]}"
    
    # Sanitize the GitHub repo name to use as a filename
    github_repo_safe = github_repo.replace('/', '_')
    return os.path.join(config_dir, f"{github_repo_safe}_{gitea_owner}_{gitea_repo}.json")

def get_repo_config(github_repo, gitea_owner, gitea_repo):
    """Get the configuration for a specific repository."""
    config_path = get_repo_config_path(github_repo, gitea_owner, gitea_repo)
    logger.debug(f"Looking for config file at: {config_path}")
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                logger.debug(f"Loaded config from {config_path}: {config}")
                return config
        except Exception as e:
            logger.error(f"Error loading repo config for {github_repo} -> {gitea_owner}/{gitea_repo}: {e}")
    else:
        logger.debug(f"Config file not found at {config_path}, using default config")
    
    # If no specific config exists or there was an error, return the default config
    default_config = get_default_config()
    logger.debug(f"Using default config: {default_config}")
    return default_config

def save_repo_config(github_repo, gitea_owner, gitea_repo, config):
    """Save the configuration for a specific repository."""
    config_path = get_repo_config_path(github_repo, gitea_owner, gitea_repo)
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving repo config for {github_repo} -> {gitea_owner}/{gitea_repo}: {e}")
        return False

def get_all_repo_configs():
    """Get all repository configurations."""
    config_dir = get_config_dir()
    configs = {}
    
    try:
        for filename in os.listdir(config_dir):
            if filename.endswith('.json') and filename != 'default.json':
                try:
                    with open(os.path.join(config_dir, filename), 'r') as f:
                        config = json.load(f)
                        # Extract repo info from filename
                        parts = filename.replace('.json', '').split('_')
                        
                        # Standard format: owner_repo_gitea_owner_gitea_repo.json
                        if len(parts) >= 3:
                            github_repo = parts[0]
                            if len(parts) > 3:  # Handle GitHub repos with underscores
                                github_repo = '_'.join(parts[:-2])
                                github_repo = github_repo.replace('_', '/', 1)  # Replace first underscore with slash
                            else:
                                github_repo = github_repo.replace('_', '/')
                            gitea_owner = parts[-2]
                            gitea_repo = parts[-1]
                            
                            configs[f"{github_repo}|{gitea_owner}|{gitea_repo}"] = config
                except Exception as e:
                    logger.error(f"Error loading config from {filename}: {e}")
    except Exception as e:
        logger.error(f"Error listing config directory: {e}")
    
    return configs 