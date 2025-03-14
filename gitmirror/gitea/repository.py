import logging
import requests
import json
import time
from ..utils.config import get_repo_config

logger = logging.getLogger('github-gitea-mirror')

def get_gitea_repos(gitea_token, gitea_url):
    """Get list of repositories from Gitea that are configured as GitHub mirrors"""
    headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    # Get all repositories the user has access to
    api_url = f"{gitea_url}/api/v1/user/repos"
    try:
        logger.info(f"Fetching repositories from {api_url}")
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        repos = response.json()
        logger.info(f"Found {len(repos)} repositories")
        
        # Filter for repositories that are mirrors from GitHub
        mirrored_repos = []
        for repo in repos:
            logger.debug(f"Checking repository: {repo['name']}")
            
            # Check if it's a mirror with original_url pointing to GitHub
            if repo.get('mirror', False) and repo.get('original_url', '').startswith('https://github.com/'):
                # Extract the GitHub repository path from the original_url
                github_url = repo.get('original_url', '')
                github_repo = github_url.replace('https://github.com/', '')
                
                # Remove .git suffix if present
                if github_repo.endswith('.git'):
                    github_repo = github_repo[:-4]
                
                # Get repository configuration to retrieve last mirror timestamp
                repo_config = get_repo_config(github_repo, repo['owner']['username'], repo['name'])
                
                mirrored_repos.append({
                    'gitea_owner': repo['owner']['username'],
                    'gitea_repo': repo['name'],
                    'github_repo': github_repo,
                    'is_mirror': True,
                    'mirror_interval': repo.get('mirror_interval', 'unknown'),
                    'last_mirror_timestamp': repo_config.get('last_mirror_timestamp', None),
                    'last_mirror_date': repo_config.get('last_mirror_date', 'Never'),
                    'last_mirror_status': repo_config.get('last_mirror_status', 'unknown'),
                    'last_mirror_messages': repo_config.get('last_mirror_messages', []),
                    'last_mirror_log': repo_config.get('last_mirror_log', None)
                })
                logger.info(f"Added as mirrored repository: {repo['name']} -> {github_repo}")
        
        return mirrored_repos
    except Exception as e:
        logger.error(f"Error fetching repositories: {e}")
        return []

def create_or_update_repo(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_token=None, force_recreate=False, skip_mirror=False, mirror_options=None):
    """Create or update repository in Gitea with mirror information
    
    Args:
        gitea_token: Gitea API token
        gitea_url: Gitea URL
        gitea_owner: Gitea repository owner
        gitea_repo: Gitea repository name
        github_repo: GitHub repository in format owner/repo or URL
        github_token: GitHub API token (optional)
        force_recreate: Whether to force recreate the repository if it exists but is not a mirror
        skip_mirror: Whether to skip the immediate mirroring of content (just set up the mirror configuration)
        mirror_options: Dictionary of mirroring options (issues, pull_requests, labels, etc.)
    
    Returns:
        bool: True if successful, False otherwise
    """
    headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    # Set default mirror options if not provided
    if mirror_options is None:
        mirror_options = {}
    
    # Normalize GitHub repository information
    # If it's a URL, convert it to a standard format
    if github_repo.startswith('http'):
        github_url = github_repo.rstrip('/')
        if not github_url.endswith('.git'):
            github_url = f"{github_url}.git"
        
        parts = github_repo.rstrip('/').rstrip('.git').split('/')
        if len(parts) >= 2:
            normalized_github_repo = f"{parts[-2]}/{parts[-1]}"
        else:
            logger.error(f"Invalid GitHub URL format: {github_repo}")
            return False
    else:
        # Convert owner/repo format to full GitHub URL
        normalized_github_repo = github_repo
        github_url = f"https://github.com/{github_repo}.git"
    
    # First check if the repository already exists
    check_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}"
    try:
        check_response = requests.get(check_url, headers=headers)
        
        if check_response.status_code == 200:
            # Repository exists, check if it's already a mirror
            repo_info = check_response.json()
            
            if repo_info.get('mirror', False):
                logger.info(f"Repository {gitea_owner}/{gitea_repo} is already configured as a mirror")
                return True
            
            # Repository exists but is not a mirror
            # We need to delete it and recreate it as a mirror
            # First, check if it's empty to avoid data loss
            logger.info(f"Repository {gitea_owner}/{gitea_repo} exists but is not a mirror. Checking if it's empty...")
            
            # Check if the repository has any commits
            commits_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/commits"
            commits_response = requests.get(commits_url, headers=headers)
            
            if commits_response.status_code == 200 and len(commits_response.json()) > 0:
                logger.warning(f"Repository {gitea_owner}/{gitea_repo} has commits and cannot be safely converted to a mirror.")
                logger.warning("Please delete the repository manually and run the script again.")
                return False
            
            # Repository is empty, but we need explicit confirmation to delete and recreate it
            if not force_recreate:
                logger.warning(f"Repository {gitea_owner}/{gitea_repo} is empty but not a mirror.")
                logger.warning("To delete and recreate it as a mirror, use the --force-recreate flag.")
                return False
            
            # Repository is empty and force_recreate is True, we can delete and recreate it as a mirror
            logger.info(f"Repository {gitea_owner}/{gitea_repo} is empty. Deleting it to recreate as a mirror...")
            
            delete_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}"
            delete_response = requests.delete(delete_url, headers=headers)
            
            if delete_response.status_code != 204:
                logger.error(f"Failed to delete repository: {delete_response.status_code} - {delete_response.text}")
                return False
            
            logger.info(f"Repository {gitea_owner}/{gitea_repo} deleted successfully. Recreating as a mirror...")
            
            # Wait a moment to ensure the deletion is processed
            time.sleep(2)
        
        # Repository doesn't exist or was deleted, create it as a mirror
        logger.info(f"Creating new mirror repository: {gitea_owner}/{gitea_repo} from {github_url}")
        
        # Create a new repository as a mirror
        create_url = f"{gitea_url}/api/v1/repos/migrate"
        repo_payload = {
            'clone_addr': github_url,
            'repo_name': gitea_repo,
            'mirror': True,
            'private': False,
            'description': f"Mirror of {normalized_github_repo}",
            'repo_owner': gitea_owner,
            'issues': mirror_options.get('mirror_issues', False),
            'pull_requests': mirror_options.get('mirror_pull_requests', False),
            'wiki': mirror_options.get('mirror_wiki', False),
            'labels': mirror_options.get('mirror_labels', False),
            'milestones': mirror_options.get('mirror_milestones', False),
            'releases': mirror_options.get('mirror_releases', False),
            'service': 'github',
        }
        
        # Log the mirror options being applied
        logger.info(f"Applying mirror options: {repo_payload}")
        
        # Add authentication for GitHub if token is provided
        if github_token:
            masked_token = f"{'*' * 5}{github_token[-5:]}" if github_token else "None"
            logger.info(f"Using GitHub token (masked: {masked_token}) for authentication")
            repo_payload['auth_token'] = github_token
        else:
            # No token provided, use empty credentials (works for public repos)
            logger.info("No GitHub token provided, using empty credentials (only works for public repos)")
            repo_payload['auth_username'] = ''
            repo_payload['auth_password'] = ''
        
        # Set a default mirror interval when skipping immediate mirroring
        if skip_mirror:
            logger.info("Skipping immediate mirroring as requested")
            repo_payload['mirror_interval'] = '8h0m0s'  # Set a reasonable default interval (8 hours)
        
        response = requests.post(create_url, headers=headers, json=repo_payload)
        
        if response.status_code == 201 or response.status_code == 200:
            logger.info(f"Successfully created mirror repository {gitea_owner}/{gitea_repo}")
            return True
        else:
            logger.error(f"Error creating mirror repository: {response.status_code} - {response.text}")
            
            # If we get a 401 or 403 error, it might be because the repository is private and we need authentication
            if (response.status_code == 401 or response.status_code == 403) and not github_token:
                logger.error("Authentication error. If this is a private repository, make sure to set the GITHUB_TOKEN environment variable.")
            
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error configuring repository {gitea_owner}/{gitea_repo}: {e}")
        return False

def trigger_mirror_sync(gitea_token, gitea_url, gitea_owner, gitea_repo):
    """Trigger a mirror sync for a repository"""
    headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    sync_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/mirror-sync"
    try:
        response = requests.post(sync_url, headers=headers)
        
        if response.status_code == 200:
            logger.info(f"Successfully triggered mirror sync for code in {gitea_owner}/{gitea_repo}")
            return True
        else:
            logger.warning(f"Failed to trigger mirror sync for code: {response.status_code} - {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Error triggering mirror sync: {e}")
        return False

def update_repo_description(gitea_token, gitea_url, gitea_owner, gitea_repo, description):
    """Update the description of a repository"""
    headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    update_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}"
    try:
        update_data = {
            'description': description
        }
        
        response = requests.patch(update_url, headers=headers, json=update_data)
        
        if response.status_code == 200:
            logger.info(f"Successfully updated description for {gitea_owner}/{gitea_repo}")
            return True
        else:
            logger.warning(f"Failed to update repository description: {response.status_code} - {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating repository description: {e}")
        return False

def check_repo_exists(gitea_token, gitea_url, gitea_owner, gitea_repo):
    """Check if a repository exists in Gitea"""
    headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    check_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}"
    try:
        check_response = requests.get(check_url, headers=headers)
        return check_response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def is_repo_mirror(gitea_token, gitea_url, gitea_owner, gitea_repo):
    """Check if a repository is configured as a mirror in Gitea"""
    headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    check_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}"
    try:
        check_response = requests.get(check_url, headers=headers)
        if check_response.status_code == 200:
            repo_info = check_response.json()
            return repo_info.get('mirror', False)
        return False
    except requests.exceptions.RequestException:
        return False

def is_repo_empty(gitea_token, gitea_url, gitea_owner, gitea_repo):
    """Check if a repository is empty (has no commits)"""
    headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    commits_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/commits"
    try:
        commits_response = requests.get(commits_url, headers=headers)
        if commits_response.status_code == 200:
            commits = commits_response.json()
            return len(commits) == 0
        return True  # Assume empty if we can't check
    except requests.exceptions.RequestException:
        return True  # Assume empty if we can't check 