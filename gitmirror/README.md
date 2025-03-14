# GitHub to Gitea Mirror - Core Package

This is the core package for the GitHub to Gitea Mirror tool. It contains the main functionality for mirroring GitHub repositories to Gitea.

## Package Structure

- `__init__.py`: Package initialization
- `__main__.py`: Entry point for running the package as a module
- `cli.py`: Command-line interface
- `mirror.py`: Main mirroring logic
- `web.py`: Web UI

### Subpackages

- `github/`: GitHub API interactions
  - `api.py`: GitHub API client

- `gitea/`: Gitea API interactions
  - `repository.py`: Repository management
  - `release.py`: Release management
  - `issue.py`: Issue management
  - `pr.py`: Pull request management
  - `comment.py`: Comment management
  - `wiki.py`: Wiki management
  - `metadata.py`: Labels, milestones, and other metadata

- `utils/`: Utility functions
  - `config.py`: Configuration management
  - `logging.py`: Logging setup

## Development

### Adding New Features

When adding new features, follow these guidelines:

1. **Modular Design**: Keep functionality in appropriate modules
2. **Error Handling**: Use try/except blocks for API calls
3. **Logging**: Log all significant actions and errors
4. **Configuration**: Make features configurable where appropriate

### Testing

Run tests with:

```bash
python -m unittest discover tests
```

### API Documentation

#### Mirror Module

The `mirror.py` module contains the main mirroring logic:

- `mirror_repository(github_token, gitea_token, gitea_url, github_repo, gitea_owner, gitea_repo, ...)`: 
  Set up a repository as a pull mirror from GitHub to Gitea and sync releases

- `process_all_repositories(github_token, gitea_token, gitea_url, ...)`:
  Process all mirrored repositories from Gitea

#### Web Module

The `web.py` module contains the Flask web application:

- Routes:
  - `/`: Home page
  - `/repos`: Repository list
  - `/repos/<owner>/<repo>`: Repository configuration
  - `/logs`: Log list
  - `/logs/<filename>`: View log
  - `/run`: Run mirror script
  - `/config`: Global configuration
  - `/add`: Add repository
  - `/health`: Health check endpoint

#### Utility Modules

- `config.py`: Configuration management
  - `load_config()`: Load configuration from environment variables
  - `get_repo_config(github_repo, gitea_owner, gitea_repo)`: Get repository-specific configuration
  - `save_repo_config(github_repo, gitea_owner, gitea_repo, config)`: Save repository-specific configuration

- `logging.py`: Logging setup
  - `setup_logging()`: Set up logging configuration
  - `get_current_log_filename(logger)`: Get the current log file name from logger handlers

## Performance Considerations

- API calls are rate-limited, so be mindful of the number of calls made
- Large repositories with many issues/PRs may take a long time to mirror
- Consider using caching for frequently accessed data
- Log files can grow large, so log rotation is implemented

## Usage

### Command Line

```bash
# Run as a module
python -m gitmirror

# Mirror a specific repository
python -m gitmirror <github_repo> <gitea_owner> <gitea_repo>

# List mirrored repositories
python -m gitmirror --list-repos

# Force recreation of repositories
python -m gitmirror --force-recreate

# Skip mirroring metadata (issues, PRs, labels, milestones, wikis)
python -m gitmirror --skip-metadata

# Combine flags
python -m gitmirror <github_repo> <gitea_owner> <gitea_repo> --skip-metadata
```

Note: By default, metadata mirroring is enabled when using the CLI, but disabled in the repository configuration. Use the `--skip-metadata` flag to disable metadata mirroring from the CLI.

### Web UI

```bash
# Start the web UI
python -m gitmirror.web
```

### Docker Usage

The recommended way to use this package is through Docker:

```bash
# Start the web UI
docker-compose up -d

# Run the mirror script
docker-compose run --rm mirror
```

See the main README.md for more details on Docker usage. 