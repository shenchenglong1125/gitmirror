import logging
import requests
from .comment import mirror_github_issue_comments

logger = logging.getLogger('github-gitea-mirror')

def mirror_github_issues(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_token=None):
    """Mirror issues from GitHub to Gitea"""
    logger.info(f"Mirroring issues from GitHub repository {github_repo} to Gitea repository {gitea_owner}/{gitea_repo}")
    
    # GitHub API headers
    github_headers = {}
    if github_token:
        github_headers['Authorization'] = f'token {github_token}'
    
    # Gitea API headers
    gitea_headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    # Get issues from GitHub
    github_api_url = f"https://api.github.com/repos/{github_repo}/issues"
    params = {
        'state': 'all',  # Get both open and closed issues
        'per_page': 100,  # Maximum allowed by GitHub API
    }
    
    try:
        # Paginate through all issues
        page = 1
        all_issues = []
        
        while True:
            params['page'] = page
            response = requests.get(github_api_url, headers=github_headers, params=params)
            response.raise_for_status()
            
            issues = response.json()
            if not issues:
                break  # No more issues
                
            all_issues.extend([issue for issue in issues if 'pull_request' not in issue])  # Filter out PRs
            
            # Check if there are more pages
            if len(issues) < params['per_page']:
                break
                
            page += 1
        
        logger.info(f"Found {len(all_issues)} issues in GitHub repository {github_repo}")
        
        # Count open and closed issues
        open_issues = sum(1 for issue in all_issues if issue['state'] == 'open')
        closed_issues = sum(1 for issue in all_issues if issue['state'] == 'closed')
        logger.info(f"GitHub issues breakdown: {open_issues} open, {closed_issues} closed")
        
        # Create issues in Gitea
        gitea_api_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/issues"
        
        # Get existing issues in Gitea to avoid duplicates
        existing_issues = {}
        existing_titles = {}
        existing_gh_numbers = set()
        
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
            
            logger.info(f"Found {len(gitea_issues)} existing issues in Gitea repository {gitea_owner}/{gitea_repo}")
            
            # Count open and closed issues in Gitea
            gitea_open_issues = sum(1 for issue in gitea_issues if issue['state'] == 'open')
            gitea_closed_issues = sum(1 for issue in gitea_issues if issue['state'] == 'closed')
            logger.info(f"Gitea issues breakdown before mirroring: {gitea_open_issues} open, {gitea_closed_issues} closed")
            
            # Create a mapping of GitHub issue numbers to Gitea issue numbers
            for issue in gitea_issues:
                # Look for the GitHub issue number in the body
                github_issue_num = None
                
                if issue['body']:
                    # Try to extract GitHub issue number from the body
                    body_lines = issue['body'].split('\n')
                    for line in body_lines:
                        if '*Mirrored from GitHub issue' in line:
                            try:
                                # Extract the GitHub issue number - handle both formats
                                # *Mirrored from GitHub issue #123*
                                # *Mirrored from GitHub issue [#123](url)*
                                if '#' in line:
                                    # Extract number after # and before closing * or ]
                                    num_text = line.split('#')[1]
                                    if ']' in num_text:
                                        github_issue_num = int(num_text.split(']')[0])
                                    elif '*' in num_text:
                                        github_issue_num = int(num_text.split('*')[0])
                                    else:
                                        github_issue_num = int(num_text.strip())
                                    
                                    if github_issue_num:
                                        existing_issues[github_issue_num] = issue['number']
                                        existing_gh_numbers.add(github_issue_num)
                                        break
                            except (ValueError, IndexError) as e:
                                logger.warning(f"Failed to extract GitHub issue number from body: {e}")
                
                # Also check title for [GH-123] format
                if issue['title'] and '[GH-' in issue['title']:
                    try:
                        title_parts = issue['title'].split('[GH-')
                        if len(title_parts) > 1:
                            num_part = title_parts[1].split(']')[0]
                            # Handle PR references like 'PR-31'
                            if num_part.startswith('PR-'):
                                # This is a PR reference, not an issue reference
                                # Skip it as it will be handled by the PR module
                                pass
                            else:
                                # Try to convert to integer, but handle non-numeric values
                                try:
                                    gh_num = int(num_part)
                                    existing_issues[gh_num] = issue['number']
                                    existing_gh_numbers.add(gh_num)
                                except ValueError:
                                    logger.warning(f"Non-numeric issue reference in title: {num_part}")
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to extract GitHub issue number from title: {e}")
                
                # Store title mapping as fallback
                existing_titles[issue['title']] = issue['number']
        except Exception as e:
            logger.warning(f"Error getting existing issues from Gitea: {e}")
        
        # Mirror issues
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        for issue in all_issues:
            try:
                # Format the title with GitHub issue number
                issue_title = f"[GH-{issue['number']}] {issue['title']}"
                
                # Create a prominent link at the top of the issue body
                issue_body = f"*Mirrored from GitHub issue [#{issue['number']}]({issue['html_url']})*\n\n"
                issue_body += f"**Original author: @{issue['user']['login']}**\n\n"
                issue_body += f"**Created at: {issue['created_at']}**\n\n"
                
                # Add labels
                if issue['labels']:
                    issue_body += "**Labels:** "
                    for label in issue['labels']:
                        issue_body += f"`{label['name']}` "
                    issue_body += "\n\n"
                
                # Add milestone
                if issue['milestone']:
                    issue_body += f"**Milestone:** {issue['milestone']['title']}\n\n"
                
                # Add assignees
                if issue['assignees']:
                    issue_body += "**Assignees:** "
                    for assignee in issue['assignees']:
                        issue_body += f"@{assignee['login']} "
                    issue_body += "\n\n"
                
                # Add the original issue body
                if issue['body']:
                    issue_body += f"## Description\n\n{issue['body']}\n\n"
                
                # Skip if we've already processed this GitHub issue number in this run
                if issue['number'] in existing_gh_numbers:
                    logger.debug(f"Skipping already processed GitHub issue #{issue['number']}")
                    skipped_count += 1
                    continue
                
                # Check if issue already exists in Gitea by GitHub issue number
                if issue['number'] in existing_issues:
                    # Update existing issue
                    gitea_issue_number = existing_issues[issue['number']]
                    update_url = f"{gitea_api_url}/{gitea_issue_number}"
                    
                    # Prepare issue data
                    issue_data = {
                        'title': issue_title,
                        'body': issue_body,
                    }
                    
                    # Handle state properly for Gitea API
                    if issue['state'] == 'closed':
                        issue_data['state'] = 'closed'
                    
                    try:
                        # Don't use Sudo parameter as it's causing 404 errors when the user doesn't exist in Gitea
                        update_response = requests.patch(update_url, headers=gitea_headers, json=issue_data)
                        update_response.raise_for_status()
                        updated_count += 1
                        logger.debug(f"Updated issue in Gitea: {issue_title} (state: {issue['state']})")
                        
                        # Mark as processed
                        existing_gh_numbers.add(issue['number'])
                        
                        # Mirror comments for this issue
                        mirror_github_issue_comments(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, issue['number'], gitea_issue_number, github_token)
                    except Exception as e:
                        logger.error(f"Error updating issue in Gitea: {e}")
                        skipped_count += 1
                else:
                    # Look for an existing issue with the exact issue number marker in the title
                    issue_number_marker = f"[GH-{issue['number']}]"
                    found_matching_issue = False
                    
                    for existing_title, gitea_num in existing_titles.items():
                        if issue_number_marker in existing_title:
                            # Found a title with the correct issue number, update it
                            update_url = f"{gitea_api_url}/{gitea_num}"
                            
                            # Prepare issue data
                            issue_data = {
                                'title': issue_title,
                                'body': issue_body,
                            }
                            
                            # Handle state properly for Gitea API
                            if issue['state'] == 'closed':
                                issue_data['state'] = 'closed'
                            
                            try:
                                update_response = requests.patch(update_url, headers=gitea_headers, json=issue_data)
                                update_response.raise_for_status()
                                updated_count += 1
                                logger.debug(f"Updated issue in Gitea by title match: {issue_title} (state: {issue['state']})")
                                
                                # Mark as processed
                                existing_gh_numbers.add(issue['number'])
                                existing_issues[issue['number']] = gitea_num
                                
                                # Mirror comments for this issue
                                mirror_github_issue_comments(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, issue['number'], gitea_num, github_token)
                                
                                found_matching_issue = True
                                break
                            except Exception as e:
                                logger.error(f"Error updating issue in Gitea by title match: {e}")
                                # Continue to try creating a new issue
                    
                    if found_matching_issue:
                        continue
                    
                    # Create a new issue
                    # Prepare issue data
                    issue_data = {
                        'title': issue_title,
                        'body': issue_body,
                    }
                    
                    # Handle state properly for Gitea API
                    if issue['state'] == 'closed':
                        issue_data['state'] = 'closed'
                    
                    try:
                        # Don't use Sudo parameter as it's causing 404 errors when the user doesn't exist in Gitea
                        create_response = requests.post(gitea_api_url, headers=gitea_headers, json=issue_data)
                        create_response.raise_for_status()
                        
                        # Add the newly created issue to our mapping to avoid duplicates in the same run
                        new_issue = create_response.json()
                        existing_issues[issue['number']] = new_issue['number']
                        existing_titles[issue_title] = new_issue['number']
                        existing_gh_numbers.add(issue['number'])
                        
                        created_count += 1
                        logger.info(f"Created issue in Gitea: {issue_title} (state: {issue['state']})")
                        
                        # Mirror comments for this issue
                        mirror_github_issue_comments(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, issue['number'], new_issue['number'], github_token)
                    except Exception as e:
                        logger.error(f"Error creating issue in Gitea: {e}")
                        skipped_count += 1
            except Exception as e:
                logger.error(f"Error processing issue: {e}")
                skipped_count += 1
        
        logger.info(f"Issues mirroring summary: {created_count} created, {updated_count} updated, {skipped_count} skipped")
        
        # Get final count of issues in Gitea after mirroring
        try:
            gitea_issues_after = []
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
                    
                gitea_issues_after.extend(page_issues)
                
                # Check if there are more pages
                if len(page_issues) < 50:
                    break
                    
                gitea_page += 1
            
            # Count open and closed issues in Gitea after mirroring
            gitea_open_issues_after = sum(1 for issue in gitea_issues_after if issue['state'] == 'open')
            gitea_closed_issues_after = sum(1 for issue in gitea_issues_after if issue['state'] == 'closed')
            logger.info(f"Gitea issues breakdown after mirroring: {gitea_open_issues_after} open, {gitea_closed_issues_after} closed")
        except Exception as e:
            logger.error(f"Error getting final issue counts: {e}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error mirroring issues: {e}")
        return False

def delete_all_issues(gitea_token, gitea_url, gitea_owner, gitea_repo):
    """Delete all issues for a repository in Gitea"""
    logger.info(f"Deleting all issues for repository {gitea_owner}/{gitea_repo}")
    
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
        
        logger.info(f"Found {len(gitea_issues)} issues to delete in Gitea repository {gitea_owner}/{gitea_repo}")
        
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
                    logger.debug(f"Successfully deleted issue #{issue_number}")
                    deleted_count += 1
                else:
                    # If direct deletion fails, try closing the issue as a fallback
                    logger.warning(f"Could not delete issue #{issue_number} (status code: {delete_response.status_code}), attempting to close it instead")
                    
                    # Close the issue with a note
                    close_data = {
                        'state': 'closed',
                        'body': issue.get('body', '') + '\n\n*This issue was automatically closed during repository cleanup.*'
                    }
                    
                    close_response = requests.patch(delete_url, headers=gitea_headers, json=close_data)
                    if close_response.status_code in [200, 201, 204]:
                        logger.warning(f"Issue #{issue_number} was closed but could not be deleted")
                        deleted_count += 1  # Count as deleted since it was at least closed
                    else:
                        logger.error(f"Failed to close issue #{issue_number} (status code: {close_response.status_code})")
                        failed_count += 1
            except Exception as e:
                logger.error(f"Error deleting issue #{issue_number}: {e}")
                failed_count += 1
        
        logger.info(f"Issues deletion summary: {deleted_count} deleted/closed, {failed_count} failed")
        return True, deleted_count, failed_count
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting issues: {e}")
        return False, 0, 0 