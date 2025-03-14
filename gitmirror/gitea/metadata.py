import logging
import requests
from ..utils.config import get_repo_config

logger = logging.getLogger('github-gitea-mirror')

def mirror_github_labels(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_token=None):
    """Mirror labels from GitHub to Gitea"""
    logger.info(f"Mirroring labels from GitHub repository {github_repo} to Gitea repository {gitea_owner}/{gitea_repo}")
    
    # GitHub API headers
    github_headers = {}
    if github_token:
        github_headers['Authorization'] = f'token {github_token}'
    
    # Gitea API headers
    gitea_headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    # Get labels from GitHub
    github_api_url = f"https://api.github.com/repos/{github_repo}/labels"
    
    try:
        response = requests.get(github_api_url, headers=github_headers)
        response.raise_for_status()
        
        github_labels = response.json()
        logger.info(f"Found {len(github_labels)} labels in GitHub repository {github_repo}")
        
        # Get existing labels in Gitea
        gitea_api_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/labels"
        gitea_labels_response = requests.get(gitea_api_url, headers=gitea_headers)
        gitea_labels_response.raise_for_status()
        
        gitea_labels = gitea_labels_response.json()
        existing_labels = {label['name']: label for label in gitea_labels}
        
        # Mirror labels
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        for label in github_labels:
            # Check if label already exists in Gitea
            if label['name'] in existing_labels:
                # Update existing label
                gitea_label = existing_labels[label['name']]
                update_url = f"{gitea_api_url}/{gitea_label['id']}"
                
                # Prepare label data
                label_data = {
                    'name': label['name'],
                    'color': label['color'],
                    'description': label.get('description', ''),
                }
                
                try:
                    update_response = requests.patch(update_url, headers=gitea_headers, json=label_data)
                    update_response.raise_for_status()
                    updated_count += 1
                    logger.debug(f"Updated label in Gitea: {label['name']}")
                except Exception as e:
                    logger.error(f"Error updating label in Gitea: {e}")
                    skipped_count += 1
            else:
                # Create new label
                label_data = {
                    'name': label['name'],
                    'color': label['color'],
                    'description': label.get('description', ''),
                }
                
                try:
                    create_response = requests.post(gitea_api_url, headers=gitea_headers, json=label_data)
                    create_response.raise_for_status()
                    created_count += 1
                    logger.debug(f"Created label in Gitea: {label['name']}")
                except Exception as e:
                    logger.error(f"Error creating label in Gitea: {e}")
                    skipped_count += 1
        
        logger.info(f"Labels mirroring summary: {created_count} created, {updated_count} updated, {skipped_count} skipped")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error mirroring labels: {e}")
        return False

def mirror_github_milestones(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_token=None):
    """Mirror milestones from GitHub to Gitea"""
    logger.info(f"Mirroring milestones from GitHub repository {github_repo} to Gitea repository {gitea_owner}/{gitea_repo}")
    
    # GitHub API headers
    github_headers = {}
    if github_token:
        github_headers['Authorization'] = f'token {github_token}'
    
    # Gitea API headers
    gitea_headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    # Get milestones from GitHub
    github_api_url = f"https://api.github.com/repos/{github_repo}/milestones"
    params = {
        'state': 'all',  # Get both open and closed milestones
        'per_page': 100,  # Maximum allowed by GitHub API
    }
    
    try:
        # Paginate through all milestones
        page = 1
        all_milestones = []
        
        while True:
            params['page'] = page
            response = requests.get(github_api_url, headers=github_headers, params=params)
            response.raise_for_status()
            
            milestones = response.json()
            if not milestones:
                break  # No more milestones
                
            all_milestones.extend(milestones)
            
            # Check if there are more pages
            if len(milestones) < params['per_page']:
                break
                
            page += 1
        
        logger.info(f"Found {len(all_milestones)} milestones in GitHub repository {github_repo}")
        
        # Get existing milestones in Gitea
        gitea_api_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/milestones"
        gitea_milestones_response = requests.get(gitea_api_url, headers=gitea_headers, params={'state': 'all'})
        gitea_milestones_response.raise_for_status()
        
        gitea_milestones = gitea_milestones_response.json()
        existing_milestones = {milestone['title']: milestone for milestone in gitea_milestones}
        
        # Mirror milestones
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        for milestone in all_milestones:
            # Check if milestone already exists in Gitea
            if milestone['title'] in existing_milestones:
                # Update existing milestone
                gitea_milestone = existing_milestones[milestone['title']]
                update_url = f"{gitea_api_url}/{gitea_milestone['id']}"
                
                # Prepare milestone data
                milestone_data = {
                    'title': milestone['title'],
                    'description': milestone.get('description', ''),
                    'state': milestone['state'],
                    'due_on': milestone.get('due_on', None),
                }
                
                try:
                    update_response = requests.patch(update_url, headers=gitea_headers, json=milestone_data)
                    update_response.raise_for_status()
                    updated_count += 1
                    logger.debug(f"Updated milestone in Gitea: {milestone['title']}")
                except Exception as e:
                    logger.error(f"Error updating milestone in Gitea: {e}")
                    skipped_count += 1
            else:
                # Create new milestone
                milestone_data = {
                    'title': milestone['title'],
                    'description': milestone.get('description', ''),
                    'state': milestone['state'],
                    'due_on': milestone.get('due_on', None),
                }
                
                try:
                    create_response = requests.post(gitea_api_url, headers=gitea_headers, json=milestone_data)
                    create_response.raise_for_status()
                    created_count += 1
                    logger.debug(f"Created milestone in Gitea: {milestone['title']}")
                except Exception as e:
                    logger.error(f"Error creating milestone in Gitea: {e}")
                    skipped_count += 1
        
        logger.info(f"Milestones mirroring summary: {created_count} created, {updated_count} updated, {skipped_count} skipped")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error mirroring milestones: {e}")
        return False

def delete_all_issues_and_prs(gitea_token, gitea_url, gitea_owner, gitea_repo):
    """Delete all issues and PRs for a repository in Gitea"""
    logger.info(f"Deleting all issues and PRs for repository {gitea_owner}/{gitea_repo}")
    
    # Gitea API headers
    gitea_headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    # Get all issues in Gitea (including PRs which are represented as issues)
    gitea_api_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/issues"
    
    try:
        # Get all issues with pagination
        gitea_issues = []
        gitea_page = 1
        
        while True:
            gitea_issues_response = requests.get(
                gitea_api_url, 
                headers=gitea_headers, 
                params={'state': 'all', 'page': gitea_page, 'limit': 50}
            )
            gitea_issues_response.raise_for_status()
            
            page_issues = gitea_issues_response.json()
            if not page_issues:
                break  # No more issues
                
            gitea_issues.extend(page_issues)
            
            # Check if there are more pages
            if len(page_issues) < 50:
                break
                
            gitea_page += 1
        
        logger.info(f"Found {len(gitea_issues)} issues/PRs to delete in Gitea repository {gitea_owner}/{gitea_repo}")
        
        # Delete each issue
        deleted_count = 0
        failed_count = 0
        
        for issue in gitea_issues:
            issue_number = issue['number']
            delete_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/issues/{issue_number}"
            
            try:
                # Use the standard Gitea API to delete the issue
                delete_response = requests.delete(delete_url, headers=gitea_headers)
                
                if delete_response.status_code in [200, 204]:
                    logger.debug(f"Successfully deleted issue/PR #{issue_number}")
                    deleted_count += 1
                else:
                    # If direct deletion fails, try closing the issue as a fallback
                    logger.warning(f"Could not delete issue/PR #{issue_number} (status code: {delete_response.status_code}), attempting to close it instead")
                    
                    # Close the issue with a note
                    close_data = {
                        'state': 'closed',
                        'body': issue.get('body', '') + '\n\n*This issue was automatically closed during repository cleanup.*'
                    }
                    
                    close_response = requests.patch(delete_url, headers=gitea_headers, json=close_data)
                    if close_response.status_code in [200, 201, 204]:
                        logger.warning(f"Issue/PR #{issue_number} was closed but could not be deleted")
                        deleted_count += 1  # Count as deleted since it was at least closed
                    else:
                        logger.error(f"Failed to close issue/PR #{issue_number} (status code: {close_response.status_code})")
                        failed_count += 1
            except Exception as e:
                logger.error(f"Error deleting issue/PR #{issue_number}: {e}")
                failed_count += 1
        
        logger.info(f"Issues/PRs deletion summary: {deleted_count} deleted/closed, {failed_count} failed")
        return True, deleted_count, failed_count
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting issues/PRs: {e}")
        return False, 0, 0

def mirror_github_metadata(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_token=None, repo_config=None):
    """Mirror metadata (issues, PRs, labels, milestones, wiki) from GitHub to Gitea"""
    logger.info(f"Mirroring metadata from GitHub repository {github_repo} to Gitea repository {gitea_owner}/{gitea_repo}")
    
    # If no config provided, get the default config
    if repo_config is None:
        repo_config = get_repo_config(github_repo, gitea_owner, gitea_repo)
    
    # Check if metadata mirroring is enabled
    if not repo_config.get('mirror_metadata', False):
        logger.info(f"Metadata mirroring is disabled for {github_repo} -> {gitea_owner}/{gitea_repo}")
        return {
            'overall_success': True,
            'has_errors': False,
            'components': {}
        }
    
    # Import functions from other modules
    from .issue import mirror_github_issues
    from .pr import mirror_github_prs
    from .wiki import mirror_github_wiki
    
    # Track success status for each component
    components_status = {
        'labels': {'success': True, 'message': ''},
        'milestones': {'success': True, 'message': ''},
        'issues': {'success': True, 'message': ''},
        'prs': {'success': True, 'message': ''},
        'wiki': {'success': True, 'message': ''},
        'releases': {'success': True, 'message': ''}
    }
    
    has_errors = False
    
    # Mirror labels first (needed for issues and PRs)
    if repo_config.get('mirror_labels', False):
        try:
            labels_result = mirror_github_labels(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_token)
            if not labels_result:
                logger.warning("Labels mirroring failed or had issues")
                components_status['labels']['success'] = False
                components_status['labels']['message'] = "Labels mirroring failed"
        except Exception as e:
            logger.error(f"Error mirroring labels: {e}")
            components_status['labels']['success'] = False
            components_status['labels']['message'] = f"Error: {str(e)}"
            has_errors = True
    else:
        logger.info(f"Labels mirroring is disabled for {github_repo} -> {gitea_owner}/{gitea_repo}")
    
    # Mirror milestones (needed for issues and PRs)
    if repo_config.get('mirror_milestones', False):
        try:
            milestones_result = mirror_github_milestones(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_token)
            if not milestones_result:
                logger.warning("Milestones mirroring failed or had issues")
                components_status['milestones']['success'] = False
                components_status['milestones']['message'] = "Milestones mirroring failed"
        except Exception as e:
            logger.error(f"Error mirroring milestones: {e}")
            components_status['milestones']['success'] = False
            components_status['milestones']['message'] = f"Error: {str(e)}"
            has_errors = True
    else:
        logger.info(f"Milestones mirroring is disabled for {github_repo} -> {gitea_owner}/{gitea_repo}")
    
    # Mirror issues
    if repo_config.get('mirror_issues', False):
        try:
            issues_result = mirror_github_issues(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_token)
            if not issues_result:
                logger.warning("Issues mirroring failed or had issues")
                components_status['issues']['success'] = False
                components_status['issues']['message'] = "Issues mirroring failed"
        except Exception as e:
            logger.error(f"Error mirroring issues: {e}")
            components_status['issues']['success'] = False
            components_status['issues']['message'] = f"Error: {str(e)}"
            has_errors = True
    else:
        logger.info(f"Issues mirroring is disabled for {github_repo} -> {gitea_owner}/{gitea_repo}")
    
    # Mirror PRs
    if repo_config.get('mirror_pull_requests', False):
        try:
            prs_result = mirror_github_prs(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_token)
            if not prs_result:
                logger.warning("Pull requests mirroring failed or had issues")
                components_status['prs']['success'] = False
                components_status['prs']['message'] = "Pull requests mirroring failed"
        except Exception as e:
            logger.error(f"Error mirroring pull requests: {e}")
            components_status['prs']['success'] = False
            components_status['prs']['message'] = f"Error: {str(e)}"
            has_errors = True
    else:
        logger.info(f"Pull requests mirroring is disabled for {github_repo} -> {gitea_owner}/{gitea_repo}")
    
    # Mirror wiki
    if repo_config.get('mirror_wiki', False):
        try:
            wiki_result = mirror_github_wiki(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_token)
            if not wiki_result:
                logger.warning("Wiki mirroring failed or had issues")
                components_status['wiki']['success'] = False
                components_status['wiki']['message'] = "Wiki mirroring failed"
        except Exception as e:
            logger.error(f"Error mirroring wiki: {e}")
            components_status['wiki']['success'] = False
            components_status['wiki']['message'] = f"Error: {str(e)}"
            has_errors = True
    else:
        logger.info(f"Wiki mirroring is disabled for {github_repo} -> {gitea_owner}/{gitea_repo}")
    
    # Return overall success status
    overall_success = all(component['success'] for component in components_status.values())
    
    if overall_success:
        logger.info(f"Successfully mirrored all enabled metadata from GitHub repository {github_repo} to Gitea repository {gitea_owner}/{gitea_repo}")
    else:
        logger.warning(f"Completed metadata mirroring with some issues from GitHub repository {github_repo} to Gitea repository {gitea_owner}/{gitea_repo}")
    
    return {
        'overall_success': overall_success,
        'has_errors': has_errors,
        'components': components_status
    } 