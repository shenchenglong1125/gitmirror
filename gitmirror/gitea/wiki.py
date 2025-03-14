import logging
import requests
import tempfile
import os
import shutil
import subprocess
from .repository import update_repo_description

logger = logging.getLogger('github-gitea-mirror')

def check_git_installed():
    """Check if git is installed and available in the PATH"""
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def mirror_github_wiki(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_token=None):
    """Mirror a GitHub wiki to a separate Gitea repository"""
    logger.info(f"Checking if GitHub repository {github_repo} has a wiki")
    
    # Check if git is installed
    if not check_git_installed():
        logger.error("Git command not found. Please install git to mirror wikis.")
        return False
    
    # GitHub API headers
    github_headers = {}
    if github_token:
        github_headers['Authorization'] = f'token {github_token}'
    
    # Check if the GitHub repository has a wiki
    github_api_url = f"https://api.github.com/repos/{github_repo}"
    try:
        response = requests.get(github_api_url, headers=github_headers)
        response.raise_for_status()
        repo_info = response.json()
        
        if not repo_info.get('has_wiki', False):
            logger.info(f"GitHub repository {github_repo} does not have a wiki")
            return False
        
        logger.info(f"GitHub repository {github_repo} has wiki enabled, attempting to mirror it")
        
        # Create a temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            # Clone the GitHub wiki repository
            github_wiki_url = f"https://github.com/{github_repo}.wiki.git"
            clone_cmd = ["git", "clone", github_wiki_url]
            
            # Add authentication if token is provided
            if github_token:
                # Use https with token in the URL but don't log the actual token
                masked_token = f"{'*' * 5}{github_token[-5:]}" if github_token else "None"
                logger.info(f"Using GitHub token (masked: {masked_token}) for authentication")
                auth_url = f"https://{github_token}@github.com/{github_repo}.wiki.git"
                clone_cmd = ["git", "clone", auth_url]
            
            logger.info(f"Cloning GitHub wiki from {github_wiki_url}")
            try:
                # Run the clone command
                process = subprocess.run(clone_cmd, cwd=temp_dir, check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                # Log error without exposing the token
                sanitized_cmd = str(clone_cmd).replace(github_token, f"{'*' * 5}{github_token[-5:]}") if github_token else str(clone_cmd)
                logger.error(f"Failed to clone GitHub wiki: Command '{sanitized_cmd}' returned non-zero exit status {e.returncode}.")
                logger.error(f"Stdout: {e.stdout.decode() if e.stdout else 'None'}")
                logger.error(f"Stderr: {e.stderr.decode() if e.stderr else 'None'}")
                logger.warning(f"GitHub repository {github_repo} has wiki enabled but no wiki content found or cannot be accessed")
                return False
            
            # Get the name of the cloned directory
            wiki_dir_name = f"{github_repo.split('/')[-1]}.wiki"
            wiki_dir_path = os.path.join(temp_dir, wiki_dir_name)
            
            if not os.path.exists(wiki_dir_path):
                logger.error(f"Expected wiki directory {wiki_dir_path} not found after cloning")
                return False
            
            # Create a new repository in Gitea for the wiki
            wiki_repo_name = f"{gitea_repo}-wiki"
            
            # Gitea API headers
            gitea_headers = {
                'Authorization': f'token {gitea_token}',
                'Content-Type': 'application/json',
            }
            
            # Check if the wiki repository already exists
            check_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{wiki_repo_name}"
            check_response = requests.get(check_url, headers=gitea_headers)
            
            if check_response.status_code != 200:
                # Create a new repository for the wiki
                create_url = f"{gitea_url}/api/v1/user/repos"
                repo_payload = {
                    'name': wiki_repo_name,
                    'description': f"Wiki content for {gitea_owner}/{gitea_repo}, mirrored from GitHub",
                    'private': False,
                    'auto_init': False
                }
                
                logger.info(f"Creating new repository for wiki: {gitea_owner}/{wiki_repo_name}")
                create_response = requests.post(create_url, headers=gitea_headers, json=repo_payload)
                
                if create_response.status_code != 201:
                    logger.error(f"Failed to create wiki repository: {create_response.status_code} - {create_response.text}")
                    return False
                
                logger.info(f"Successfully created wiki repository: {gitea_owner}/{wiki_repo_name}")
            else:
                logger.info(f"Wiki repository {gitea_owner}/{wiki_repo_name} already exists")
            
            # Push the wiki content to the Gitea repository
            gitea_wiki_url = f"{gitea_url}/{gitea_owner}/{wiki_repo_name}.git"
            
            # Set up git config
            subprocess.run(["git", "config", "user.name", "GitHub Mirror"], cwd=wiki_dir_path, check=True)
            subprocess.run(["git", "config", "user.email", "mirror@example.com"], cwd=wiki_dir_path, check=True)
            
            # Add a new remote for Gitea
            subprocess.run(["git", "remote", "add", "gitea", gitea_wiki_url], cwd=wiki_dir_path, check=True)
            
            # Set up credentials for push
            gitea_auth_url = f"{gitea_url.replace('://', f'://{gitea_token}@')}/{gitea_owner}/{wiki_repo_name}.git"
            subprocess.run(["git", "remote", "set-url", "gitea", gitea_auth_url], cwd=wiki_dir_path, check=True)
            
            # Push to Gitea
            logger.info(f"Pushing wiki content to {gitea_owner}/{wiki_repo_name}")
            try:
                push_result = subprocess.run(
                    ["git", "push", "--force", "gitea", "master"], 
                    cwd=wiki_dir_path, 
                    check=True,
                    capture_output=True
                )
                logger.info("Successfully pushed wiki content to Gitea")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to push wiki content: {e}")
                logger.error(f"Stdout: {e.stdout.decode() if e.stdout else 'None'}")
                logger.error(f"Stderr: {e.stderr.decode() if e.stderr else 'None'}")
                return False
            
            # Update the main repository description to include a link to the wiki
            main_repo_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}"
            main_repo_response = requests.get(main_repo_url, headers=gitea_headers)
            
            if main_repo_response.status_code == 200:
                main_repo_info = main_repo_response.json()
                current_description = main_repo_info.get('description', '')
                
                # Always update the description to ensure it follows the new format
                wiki_link = f"{gitea_url}/{gitea_owner}/{wiki_repo_name}"
                # Extract GitHub owner and repo from the github_repo parameter
                github_parts = github_repo.split('/')
                github_owner = github_parts[0] if len(github_parts) > 0 else ""
                github_repo_name = github_parts[1] if len(github_parts) > 1 else ""
                
                # Use the original description if available, otherwise create a default one
                # First, remove any existing wiki link
                if "Wiki:" in current_description:
                    current_description = current_description.split("Wiki:")[0].strip()
                
                # If the description is a default "Mirror of..." description, replace it
                if current_description.startswith("Mirror of"):
                    # Try to get the original description from the GitHub repository
                    github_api_url = f"https://api.github.com/repos/{github_repo}"
                    github_headers = {}
                    if github_token:
                        github_headers['Authorization'] = f'token {github_token}'
                    
                    try:
                        github_response = requests.get(github_api_url, headers=github_headers)
                        github_response.raise_for_status()
                        github_repo_info = github_response.json()
                        github_description = github_repo_info.get('description', '')
                        
                        if github_description:
                            new_description = github_description
                        else:
                            new_description = f"Mirror of {github_owner}/{github_repo_name}"
                    except Exception as e:
                        logger.error(f"Error getting GitHub repository description: {e}")
                        new_description = f"Mirror of {github_owner}/{github_repo_name}"
                else:
                    new_description = current_description
                
                # Append the wiki link
                new_description += f"\nWiki: {wiki_link}"
                
                # Update the repository description
                update_repo_description(gitea_token, gitea_url, gitea_owner, gitea_repo, new_description)
            
            return True
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking GitHub repository for wiki: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error mirroring wiki: {e}")
        return False 