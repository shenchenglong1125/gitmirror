import logging
import sys
import time
from datetime import datetime
from .github.api import get_github_releases, parse_github_repo_info
from .gitea.repository import (
    get_gitea_repos, 
    create_or_update_repo, 
    trigger_mirror_sync
)
from .gitea.release import create_gitea_release
from .gitea.metadata import mirror_github_metadata
from .utils.config import get_repo_config, save_repo_config
from .utils.logging import get_current_log_filename

logger = logging.getLogger('github-gitea-mirror')

def mirror_repository(github_token, gitea_token, gitea_url, github_repo, gitea_owner, gitea_repo, skip_repo_config=False, mirror_metadata=None, mirror_releases=None, repo_config=None, force_recreate=False):
    """Set up a repository as a pull mirror from GitHub to Gitea and sync releases"""
    logger.info(f"Processing repository: {github_repo} -> {gitea_owner}/{gitea_repo}")
    
    # Import datetime here to ensure it's available in this scope
    from datetime import datetime
    
    # Track mirror status
    mirror_status = {
        'status': 'success',  # Can be 'success', 'warning', or 'error'
        'messages': [],
        'log_file': None
    }
    
    # Get repository-specific configuration if not provided
    if repo_config is None:
        repo_config = get_repo_config(github_repo, gitea_owner, gitea_repo)
    
    # If mirror_metadata is explicitly provided, override the config
    if mirror_metadata is not None:
        repo_config['mirror_metadata'] = mirror_metadata
    
    # If mirror_releases is explicitly provided, override the config
    if mirror_releases is not None:
        repo_config['mirror_releases'] = mirror_releases
    
    # Create or update repository with mirror information
    if not skip_repo_config:
        # Create mirror options from repo_config
        mirror_options = {
            'mirror_issues': repo_config.get('mirror_issues', False),
            'mirror_pull_requests': repo_config.get('mirror_pull_requests', False),
            'mirror_labels': repo_config.get('mirror_labels', False),
            'mirror_milestones': repo_config.get('mirror_milestones', False),
            'mirror_wiki': repo_config.get('mirror_wiki', False),
            'mirror_releases': repo_config.get('mirror_releases', False)
        }
        
        if not create_or_update_repo(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_token, force_recreate=force_recreate, mirror_options=mirror_options):
            logger.error(f"Failed to configure repository {gitea_owner}/{gitea_repo} as a mirror")
            mirror_status['status'] = 'error'
            mirror_status['messages'].append("Failed to configure repository as a mirror")
            return False
        
        logger.info(f"Successfully configured {gitea_owner}/{gitea_repo} as a mirror of {github_repo}")
    
    # Trigger a sync for code
    if not trigger_mirror_sync(gitea_token, gitea_url, gitea_owner, gitea_repo):
        logger.warning(f"Failed to trigger mirror sync for code in {gitea_owner}/{gitea_repo}")
        if mirror_status['status'] == 'success':
            mirror_status['status'] = 'warning'
        mirror_status['messages'].append("Failed to trigger mirror sync for code")
    
    # Extract GitHub owner and repo name
    github_info = parse_github_repo_info(github_repo)
    if not github_info:
        mirror_status['status'] = 'error'
        mirror_status['messages'].append("Failed to parse GitHub repository information")
        return False
    
    # Only mirror releases if the option is enabled
    if repo_config.get('mirror_releases', False):
        logger.info(f"Manually syncing releases from {github_info['owner']}/{github_info['repo']} to {gitea_owner}/{gitea_repo}")
        
        # Get GitHub releases
        releases = get_github_releases(github_token, github_info['owner'], github_info['repo'])
        if not releases:
            logger.warning(f"No releases found for GitHub repository {github_info['owner']}/{github_info['repo']}")
            if mirror_status['status'] == 'success':
                mirror_status['status'] = 'warning'
            mirror_status['messages'].append("No releases found in GitHub repository")
        else:
            # Mirror each release to Gitea
            release_count = 0
            for release in releases:
                logger.debug(f"Mirroring release: {release.tag_name}")
                create_gitea_release(gitea_token, gitea_url, gitea_owner, gitea_repo, release)
                release_count += 1
            
            logger.info(f"Processed {release_count} releases for {github_repo}")
    else:
        logger.info(f"Release mirroring is disabled for {github_repo} -> {gitea_owner}/{gitea_repo}")
    
    # Mirror metadata (issues, PRs, labels, milestones, wiki) based on configuration
    metadata_result = mirror_github_metadata(
        gitea_token, 
        gitea_url, 
        gitea_owner, 
        gitea_repo, 
        github_info['owner'] + '/' + github_info['repo'], 
        github_token,
        repo_config
    )
    
    # Update mirror status based on metadata mirroring result
    if not metadata_result['overall_success']:
        if metadata_result['has_errors']:
            mirror_status['status'] = 'error'
        elif mirror_status['status'] == 'success':
            mirror_status['status'] = 'warning'
        
        # Add component-specific messages
        for component, status in metadata_result['components'].items():
            if not status['success']:
                mirror_status['messages'].append(f"Failed to mirror {component}: {status.get('message', 'Unknown error')}")
    
    # Update the last successful mirror timestamp and status
    repo_config['last_mirror_timestamp'] = int(time.time())
    repo_config['last_mirror_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    repo_config['last_mirror_status'] = mirror_status['status']
    repo_config['last_mirror_messages'] = mirror_status['messages']
    
    # Get the current log file name
    repo_config['last_mirror_log'] = get_current_log_filename(logger)
    
    save_repo_config(github_repo, gitea_owner, gitea_repo, repo_config)
    
    logger.info(f"Mirror setup and sync completed for {gitea_owner}/{gitea_repo}")
    return True

def process_all_repositories(github_token, gitea_token, gitea_url, force_recreate=False, mirror_metadata=None, mirror_releases=None):
    """Process all mirrored repositories from Gitea"""
    logger.info("Auto-discovery mode: Fetching all mirrored repositories from Gitea...")
    repos = get_gitea_repos(gitea_token, gitea_url)
    
    if not repos:
        logger.warning("No mirrored repositories found in Gitea.")
        logger.info("To set up a mirror for a specific repository, use:")
        logger.info("python -m gitmirror.cli <github_owner/repo> <gitea_owner> <gitea_repo>")
        logger.info("or")
        logger.info("python -m gitmirror.cli <https://github.com/owner/repo> <gitea_owner> <gitea_repo>")
        return False
    
    logger.info(f"Found {len(repos)} mirrored repositories")
    
    # Process each repository
    success_count = 0
    for repo in repos:
        logger.info(f"Repository {repo['gitea_owner']}/{repo['gitea_repo']} is configured as a pull mirror")
        
        # Check if we should force recreate
        if force_recreate:
            logger.info(f"Force recreate flag set, recreating repository {repo['gitea_owner']}/{repo['gitea_repo']}")
            
            # Get repository-specific configuration
            repo_config = get_repo_config(repo['github_repo'], repo['gitea_owner'], repo['gitea_repo'])
            
            # If mirror_metadata is explicitly provided, override the config
            if mirror_metadata is not None:
                repo_config['mirror_metadata'] = mirror_metadata
            
            # If mirror_releases is explicitly provided, override the config
            if mirror_releases is not None:
                repo_config['mirror_releases'] = mirror_releases
                
            if mirror_repository(
                github_token,
                gitea_token,
                gitea_url,
                repo['github_repo'],
                repo['gitea_owner'],
                repo['gitea_repo'],
                skip_repo_config=False,
                mirror_metadata=mirror_metadata,
                mirror_releases=mirror_releases,
                repo_config=repo_config,
                force_recreate=force_recreate
            ):
                success_count += 1
        else:
            # Just trigger a sync for existing mirrors
            if trigger_mirror_sync(gitea_token, gitea_url, repo['gitea_owner'], repo['gitea_repo']):
                # Get repository-specific configuration
                repo_config = get_repo_config(repo['github_repo'], repo['gitea_owner'], repo['gitea_repo'])
                
                # If mirror_metadata is explicitly provided, override the config
                if mirror_metadata is not None:
                    repo_config['mirror_metadata'] = mirror_metadata
                
                # If mirror_releases is explicitly provided, override the config
                if mirror_releases is not None:
                    repo_config['mirror_releases'] = mirror_releases
                
                # If sync was successful, also sync releases if enabled
                github_info = parse_github_repo_info(repo['github_repo'])
                if github_info:
                    # Only mirror releases if the option is enabled
                    if repo_config.get('mirror_releases', False):
                        releases = get_github_releases(github_token, github_info['owner'], github_info['repo'])
                        if releases:
                            for release in releases:
                                create_gitea_release(gitea_token, gitea_url, repo['gitea_owner'], repo['gitea_repo'], release)
                    else:
                        logger.info(f"Release mirroring is disabled for {repo['github_repo']} -> {repo['gitea_owner']}/{repo['gitea_repo']}")
                    
                    # Mirror metadata based on configuration
                    mirror_github_metadata(
                        gitea_token, 
                        gitea_url, 
                        repo['gitea_owner'], 
                        repo['gitea_repo'], 
                        github_info['owner'] + '/' + github_info['repo'], 
                        github_token,
                        repo_config
                    )
                    
                    # Update the last successful mirror timestamp and log file
                    repo_config['last_mirror_timestamp'] = int(time.time())
                    repo_config['last_mirror_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Get the current log file name
                    repo_config['last_mirror_log'] = get_current_log_filename(logger)
                    
                    save_repo_config(repo['github_repo'], repo['gitea_owner'], repo['gitea_repo'], repo_config)
                
                success_count += 1
    
    logger.info(f"Successfully processed {success_count} out of {len(repos)} repositories")
    return success_count > 0 