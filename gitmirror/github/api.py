import logging
from github import Github

logger = logging.getLogger('github-gitea-mirror')

def get_github_releases(github_token, repo_owner, repo_name):
    """Get releases from GitHub repository"""
    g = Github(github_token)
    try:
        repo = g.get_repo(f"{repo_owner}/{repo_name}")
        return repo.get_releases()
    except Exception as e:
        logger.error(f"Error getting GitHub releases for {repo_owner}/{repo_name}: {e}")
        return None

def parse_github_repo_info(github_repo):
    """Parse GitHub repository information from URL or owner/repo format"""
    if github_repo.startswith('http'):
        parts = github_repo.rstrip('/').rstrip('.git').split('/')
        if len(parts) >= 2:
            github_owner = parts[-2]
            github_repo_name = parts[-1]
            github_url = github_repo.rstrip('/')
            if not github_url.endswith('.git'):
                github_url = f"{github_url}.git"
            return {
                'owner': github_owner,
                'repo': github_repo_name,
                'url': github_url,
                'full_name': f"{github_owner}/{github_repo_name}"
            }
        else:
            logger.error(f"Invalid GitHub URL format: {github_repo}")
            return None
    else:
        parts = github_repo.split('/')
        if len(parts) == 2:
            github_owner, github_repo_name = parts
            return {
                'owner': github_owner,
                'repo': github_repo_name,
                'url': f"https://github.com/{github_owner}/{github_repo_name}.git",
                'full_name': github_repo
            }
        else:
            logger.error(f"Invalid GitHub repository format: {github_repo}. Expected format: owner/repo")
            return None 