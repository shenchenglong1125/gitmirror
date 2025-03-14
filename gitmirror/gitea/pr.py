import logging
import requests
from .comment import mirror_github_issue_comments

logger = logging.getLogger('github-gitea-mirror')

def mirror_github_prs(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_token=None):
    """Mirror pull requests from GitHub to Gitea as issues (since we can't create PRs directly)"""
    logger.info(f"Mirroring pull requests from GitHub repository {github_repo} to Gitea repository {gitea_owner}/{gitea_repo}")
    
    # GitHub API headers
    github_headers = {}
    if github_token:
        github_headers['Authorization'] = f'token {github_token}'
    
    # Gitea API headers
    gitea_headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    # Get pull requests from GitHub
    github_api_url = f"https://api.github.com/repos/{github_repo}/pulls"
    params = {
        'state': 'all',  # Get both open and closed PRs
        'per_page': 100,  # Maximum allowed by GitHub API
    }
    
    all_prs = []
    try:
        # Paginate through all PRs
        page = 1
        
        while True:
            params['page'] = page
            response = requests.get(github_api_url, headers=github_headers, params=params)
            response.raise_for_status()
            
            prs = response.json()
            if not prs:
                break  # No more PRs
                
            all_prs.extend(prs)
            
            # Check if there are more pages
            if len(prs) < params['per_page']:
                break
                
            page += 1
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting pull requests: {e}")
        return False
    
    logger.info(f"Found {len(all_prs)} pull requests in GitHub repository {github_repo}")
    
    # Count open and closed PRs
    open_prs = sum(1 for pr in all_prs if pr['state'] == 'open')
    closed_prs = sum(1 for pr in all_prs if pr['state'] == 'closed')
    logger.info(f"GitHub PRs breakdown: {open_prs} open, {closed_prs} closed")
    
    # Create issues in Gitea for PRs
    gitea_api_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/issues"
    
    # Get existing issues in Gitea to avoid duplicates
    existing_issues = {}
    existing_titles = {}
    existing_gh_numbers = set()  # Track GitHub PR numbers we've already processed
    
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
        
        # Create a mapping of GitHub PR numbers to Gitea issue numbers
        for issue in gitea_issues:
            # Look for the GitHub PR number in the body
            github_pr_num = None
            
            if issue['body']:
                # Try to extract GitHub PR number from the body
                body_lines = issue['body'].split('\n')
                for line in body_lines:
                    if '*Mirrored from GitHub Pull Request' in line or '**Original PR:' in line:
                        try:
                            # Extract the GitHub PR number - handle both formats
                            # *Mirrored from GitHub Pull Request #123*
                            # *Mirrored from GitHub Pull Request [#123](url)*
                            if '#' in line:
                                # Extract number after # and before closing * or ]
                                num_text = line.split('#')[1]
                                if ']' in num_text:
                                    github_pr_num = int(num_text.split(']')[0])
                                elif '*' in num_text:
                                    github_pr_num = int(num_text.split('*')[0])
                                else:
                                    github_pr_num = int(num_text.strip())
                                
                                if github_pr_num:
                                    existing_issues[github_pr_num] = issue['number']
                                    existing_gh_numbers.add(github_pr_num)
                                    break
                        except (ValueError, IndexError) as e:
                            logger.warning(f"Failed to extract GitHub PR number from body: {e}")
            
            # Also check title for [GH-PR-123] format
            if issue['title'] and '[GH-PR-' in issue['title']:
                try:
                    title_parts = issue['title'].split('[GH-PR-')
                    if len(title_parts) > 1:
                        num_part = title_parts[1].split(']')[0]
                        gh_num = int(num_part)
                        existing_issues[gh_num] = issue['number']
                        existing_gh_numbers.add(gh_num)
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to extract GitHub PR number from title: {e}")
            
            # Also check for [GH-PR-31] format (without the PR- prefix in the split)
            elif issue['title'] and '[GH-' in issue['title']:
                try:
                    title_parts = issue['title'].split('[GH-')
                    if len(title_parts) > 1:
                        num_part = title_parts[1].split(']')[0]
                        # Check if this is a PR reference
                        if num_part.startswith('PR-'):
                            # Extract the number after 'PR-'
                            pr_num = int(num_part.split('PR-')[1])
                            existing_issues[pr_num] = issue['number']
                            existing_gh_numbers.add(pr_num)
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to extract GitHub PR number from title: {e}")
            
            # Store title mapping as fallback
            existing_titles[issue['title']] = issue['number']
    except Exception as e:
        logger.warning(f"Error getting existing issues from Gitea: {e}")
    
    # Mirror PRs as issues
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    for pr in all_prs:
        try:
            # Format the title with GitHub PR number and status
            status_indicator = ""
            if pr.get('merged', False):
                status_indicator = "[MERGED] "
            elif pr['state'] == 'closed':
                status_indicator = "[CLOSED] "
            
            pr_title = f"[GH-PR-{pr['number']}] {status_indicator}{pr['title']}"
            
            # Create a prominent link at the top of the issue body
            pr_body = f"*Mirrored from GitHub Pull Request [#{pr['number']}]({pr['html_url']})*\n\n"
            pr_body += f"**Original author: @{pr['user']['login']}**\n\n"
            pr_body += f"**Created at: {pr['created_at']}**\n\n"
            
            # Add PR status information
            pr_body += f"**Status: {pr['state'].upper()}**\n\n"
            if pr.get('merged', False):
                pr_body += f"**Merged: YES (at {pr.get('merged_at', 'unknown time')})**\n\n"
                # Add merge commit information if available
                if pr.get('merge_commit_sha'):
                    pr_body += f"**Merge commit: [{pr['merge_commit_sha'][:7]}]({pr.get('html_url', '')}/commits/{pr['merge_commit_sha']})**\n\n"
            elif pr['state'] == 'closed':
                pr_body += f"**Merged: NO (closed at {pr.get('closed_at', 'unknown time')})**\n\n"
            
            # Add branch information
            pr_body += f"**Source branch: {pr['head']['label']}**\n\n"
            pr_body += f"**Target branch: {pr['base']['label']}**\n\n"
            
            # Add commit information
            try:
                # Get commits for this PR
                commits_url = f"https://api.github.com/repos/{github_repo}/pulls/{pr['number']}/commits"
                logger.info(f"Fetching commits for PR #{pr['number']} from {commits_url}")
                commits_response = requests.get(commits_url, headers=github_headers)
                commits_response.raise_for_status()
                commits = commits_response.json()
                
                if commits:
                    logger.info(f"Found {len(commits)} commits for PR #{pr['number']}")
                    pr_body += f"## Commits ({len(commits)})\n\n"
                    for commit in commits[:10]:  # Limit to 10 commits to avoid huge bodies
                        commit_sha = commit.get('sha', '')[:7]
                        commit_message = commit.get('commit', {}).get('message', '').split('\n')[0]  # First line only
                        commit_author = commit.get('commit', {}).get('author', {}).get('name', 'Unknown')
                        commit_link = f"{pr.get('html_url', '')}/commits/{commit.get('sha', '')}"
                        pr_body += f"* [`{commit_sha}`]({commit_link}) {commit_message} - {commit_author}\n"
                    
                    if len(commits) > 10:
                        pr_body += f"\n*... and {len(commits) - 10} more commits*\n"
                    
                    pr_body += "\n"
                else:
                    logger.warning(f"No commits found for PR #{pr['number']} - API returned empty list")
            except Exception as e:
                logger.error(f"Error fetching commits for PR #{pr['number']}: {e}")
            
            # Add PR description
            if pr['body']:
                pr_body += f"## Description\n\n{pr['body']}\n\n"
            
            # Add file changes summary
            try:
                # Get file changes for this PR
                files_url = f"https://api.github.com/repos/{github_repo}/pulls/{pr['number']}/files"
                logger.info(f"Fetching file changes for PR #{pr['number']} from {files_url}")
                files_response = requests.get(files_url, headers=github_headers)
                files_response.raise_for_status()
                files = files_response.json()
                
                if files:
                    logger.info(f"Found {len(files)} changed files for PR #{pr['number']}")
                    additions = sum(file.get('additions', 0) for file in files)
                    deletions = sum(file.get('deletions', 0) for file in files)
                    pr_body += f"## Changes\n\n"
                    pr_body += f"**Files changed:** {len(files)}\n"
                    pr_body += f"**Lines added:** +{additions}\n"
                    pr_body += f"**Lines removed:** -{deletions}\n\n"
                    
                    pr_body += "**Modified files:**\n"
                    for file in files[:15]:  # Limit to 15 files to avoid huge bodies
                        filename = file.get('filename', '')
                        status = file.get('status', '')
                        pr_body += f"* {status}: `{filename}` (+{file.get('additions', 0)}/-{file.get('deletions', 0)})\n"
                    
                    if len(files) > 15:
                        pr_body += f"\n*... and {len(files) - 15} more files*\n\n"
                    else:
                        pr_body += "\n"
                    
                    # Add diff information for up to 5 files
                    diff_count = 0
                    for file in files:
                        if diff_count >= 5:
                            break
                        
                        if file.get('patch'):
                            filename = file.get('filename', '')
                            pr_body += f"**Diff for `{filename}`:**\n"
                            pr_body += "```diff\n"
                            pr_body += file.get('patch', '')
                            pr_body += "\n```\n\n"
                            diff_count += 1
                    
                    if diff_count < len(files):
                        pr_body += f"*Diffs for {len(files) - diff_count} more files are not shown*\n\n"
                else:
                    logger.warning(f"No file changes found for PR #{pr['number']} - API returned empty list")
            except Exception as e:
                logger.error(f"Error fetching file changes for PR #{pr['number']}: {e}")
            
            # Skip if we've already processed this GitHub PR number in this run
            if pr['number'] in existing_gh_numbers:
                logger.debug(f"Skipping already processed GitHub PR #{pr['number']}")
                skipped_count += 1
                continue
            
            # Check if issue already exists in Gitea by GitHub PR number
            if pr['number'] in existing_issues:
                # Update existing issue
                gitea_issue_number = existing_issues[pr['number']]
                update_url = f"{gitea_api_url}/{gitea_issue_number}"
                
                # Prepare issue data
                issue_data = {
                    'title': pr_title,
                    'body': pr_body,
                }
                
                # Handle state properly for Gitea API
                if pr['state'] == 'closed':
                    issue_data['closed'] = True
                
                try:
                    # Don't use Sudo parameter as it's causing 404 errors when the user doesn't exist in Gitea
                    update_response = requests.patch(update_url, headers=gitea_headers, json=issue_data)
                    update_response.raise_for_status()
                    updated_count += 1
                    logger.debug(f"Updated PR as issue in Gitea: {pr_title} (state: {pr['state']})")
                    
                    # Mark as processed
                    existing_gh_numbers.add(pr['number'])
                    
                    # Mirror comments for this PR
                    mirror_github_issue_comments(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, pr['number'], gitea_issue_number, github_token)
                    
                    # Mirror review comments for this PR
                    mirror_github_pr_review_comments(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, pr['number'], gitea_issue_number, github_token)
                except Exception as e:
                    logger.error(f"Error updating PR as issue in Gitea: {e}")
                    skipped_count += 1
            else:
                # Look for an existing issue with the exact PR number marker in the title
                pr_number_marker = f"[GH-PR-{pr['number']}]"
                found_matching_issue = False
                
                for existing_title, gitea_num in existing_titles.items():
                    if pr_number_marker in existing_title:
                        # Found a title with the correct PR number, update it
                        update_url = f"{gitea_api_url}/{gitea_num}"
                        
                        # Prepare issue data
                        issue_data = {
                            'title': pr_title,
                            'body': pr_body,
                        }
                        
                        # Handle state properly for Gitea API
                        if pr['state'] == 'closed':
                            issue_data['closed'] = True
                        
                        try:
                            update_response = requests.patch(update_url, headers=gitea_headers, json=issue_data)
                            update_response.raise_for_status()
                            updated_count += 1
                            logger.debug(f"Updated PR as issue in Gitea by title marker: {pr_title} (state: {pr['state']})")
                            
                            # Mark as processed and update our mappings
                            existing_gh_numbers.add(pr['number'])
                            existing_issues[pr['number']] = gitea_num
                            
                            # Mirror comments for this PR
                            mirror_github_issue_comments(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, pr['number'], gitea_num, github_token)
                            
                            # Mirror review comments for this PR
                            mirror_github_pr_review_comments(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, pr['number'], gitea_num, github_token)
                            
                            found_matching_issue = True
                            break
                        except Exception as e:
                            logger.error(f"Error updating PR as issue in Gitea: {e}")
                            # Don't increment skipped_count here, we'll try to create it instead
                
                if found_matching_issue:
                    continue
                
                # Create new issue for PR
                issue_data = {
                    'title': pr_title,
                    'body': pr_body,
                }
                
                # Handle state properly for Gitea API
                if pr['state'] == 'closed':
                    issue_data['closed'] = True
                
                try:
                    # Don't use Sudo parameter as it's causing 404 errors when the user doesn't exist in Gitea
                    create_response = requests.post(gitea_api_url, headers=gitea_headers, json=issue_data)
                    create_response.raise_for_status()
                    
                    # Add the newly created issue to our mapping to avoid duplicates in the same run
                    new_issue = create_response.json()
                    existing_issues[pr['number']] = new_issue['number']
                    existing_titles[pr_title] = new_issue['number']
                    existing_gh_numbers.add(pr['number'])
                    
                    created_count += 1
                    logger.debug(f"Created PR as issue in Gitea: {pr_title} (state: {pr['state']})")
                    
                    # Mirror comments for this PR
                    mirror_github_issue_comments(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, pr['number'], new_issue['number'], github_token)
                    
                    # Mirror review comments for this PR
                    mirror_github_pr_review_comments(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, pr['number'], new_issue['number'], github_token)
                except Exception as e:
                    logger.error(f"Error creating PR as issue in Gitea: {e}")
                    skipped_count += 1
        except Exception as e:
            logger.error(f"Error processing PR #{pr.get('number', 'unknown')}: {e}")
            skipped_count += 1
    
    logger.info(f"Pull requests mirroring summary: {created_count} created, {updated_count} updated, {skipped_count} skipped")
    return True

def mirror_github_pr_review_comments(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_pr_number, gitea_issue_number, github_token=None):
    """Mirror review comments from a GitHub PR to a Gitea issue"""
    logger.info(f"Mirroring review comments for PR #{github_pr_number} from GitHub to Gitea issue #{gitea_issue_number}")
    
    # GitHub API headers
    github_headers = {}
    if github_token:
        github_headers['Authorization'] = f'token {github_token}'
    
    # Gitea API headers
    gitea_headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    try:
        # Get PR reviews from GitHub
        reviews_url = f"https://api.github.com/repos/{github_repo}/pulls/{github_pr_number}/reviews"
        reviews_response = requests.get(reviews_url, headers=github_headers)
        reviews_response.raise_for_status()
        reviews = reviews_response.json()
        
        if not reviews:
            logger.info(f"No reviews found for PR #{github_pr_number}")
            return True
        
        logger.info(f"Found {len(reviews)} reviews for PR #{github_pr_number}")
        
        # Get review comments from GitHub
        comments_url = f"https://api.github.com/repos/{github_repo}/pulls/{github_pr_number}/comments"
        comments_response = requests.get(comments_url, headers=github_headers)
        comments_response.raise_for_status()
        review_comments = comments_response.json()
        
        logger.info(f"Found {len(review_comments)} review comments for PR #{github_pr_number}")
        
        # Get existing comments in Gitea to avoid duplicates
        gitea_api_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/issues/{gitea_issue_number}/comments"
        
        try:
            # Get all comments with pagination
            gitea_comments = []
            gitea_page = 1
            
            while True:
                gitea_comments_response = requests.get(
                    gitea_api_url, 
                    headers=gitea_headers, 
                    params={'page': gitea_page, 'limit': 50}
                )
                gitea_comments_response.raise_for_status()
                
                page_comments = gitea_comments_response.json()
                if not page_comments:
                    break  # No more comments
                    
                gitea_comments.extend(page_comments)
                
                # Check if there are more pages
                if len(page_comments) < 50:
                    break
                    
                gitea_page += 1
            
            # Create a set of comment fingerprints to avoid duplicates
            existing_comment_fingerprints = set()
            
            for comment in gitea_comments:
                if comment['body'] and ('*Mirrored from GitHub review by @' in comment['body'] or 
                                        '*Mirrored from GitHub review comment by @' in comment['body']):
                    # Extract the GitHub comment fingerprint
                    try:
                        body_lines = comment['body'].split('\n')
                        for i, line in enumerate(body_lines):
                            if '*Mirrored from GitHub review' in line:
                                # Get the author from this line
                                author = line.split('@')[1].split('*')[0]
                                # Get the content from the next lines
                                content_start = i + 3  # Skip the author line, created at line, and blank line
                                if content_start < len(body_lines):
                                    content = '\n'.join(body_lines[content_start:])
                                    content_preview = content[:50]
                                    fingerprint = f"{author}:{content_preview}"
                                    existing_comment_fingerprints.add(fingerprint)
                                break
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to extract GitHub review comment fingerprint: {e}")
            
            # First, mirror the reviews
            created_count = 0
            skipped_count = 0
            
            for review in reviews:
                try:
                    # Skip reviews without a body
                    if not review.get('body'):
                        continue
                    
                    # Create a fingerprint for this review
                    author = review['user']['login']
                    content = review['body']
                    content_preview = content[:50]
                    fingerprint = f"{author}:{content_preview}"
                    
                    # Skip if we've already processed this review
                    if fingerprint in existing_comment_fingerprints:
                        logger.debug(f"Skipping already processed GitHub review by @{author}")
                        skipped_count += 1
                        continue
                    
                    # Format the review body
                    review_state = review.get('state', 'COMMENTED').upper()
                    comment_body = f"*Mirrored from GitHub review by @{author}*\n\n"
                    comment_body += f"**Review state: {review_state}**\n\n"
                    comment_body += f"**Created at: {review.get('submitted_at', 'unknown time')}**\n\n"
                    
                    # Process the content to ensure proper formatting
                    processed_content = content
                    
                    # Minimal processing for quoted content
                    if processed_content:
                        # First, normalize line endings to just \n (no \r)
                        processed_content = processed_content.replace('\r\n', '\n').replace('\r', '\n')
                        
                        # Only ensure quotes have a space after '>'
                        lines = processed_content.split('\n')
                        for i in range(len(lines)):
                            if lines[i].startswith('>') and not lines[i].startswith('> ') and len(lines[i]) > 1:
                                lines[i] = '> ' + lines[i][1:]
                        
                        processed_content = '\n'.join(lines)
                    
                    # Add the processed content
                    if processed_content:
                        comment_body += processed_content
                    
                    # Create comment in Gitea
                    comment_data = {
                        'body': comment_body
                    }
                    
                    try:
                        create_response = requests.post(gitea_api_url, headers=gitea_headers, json=comment_data)
                        create_response.raise_for_status()
                        
                        created_count += 1
                        logger.info(f"Created review comment in Gitea issue #{gitea_issue_number} by @{author}")
                        
                        # Add to our set of processed comments
                        existing_comment_fingerprints.add(fingerprint)
                    except Exception as e:
                        logger.error(f"Error creating review comment in Gitea: {e}")
                        logger.error(f"Response status: {getattr(create_response, 'status_code', 'unknown')}")
                        logger.error(f"Response text: {getattr(create_response, 'text', 'unknown')}")
                        skipped_count += 1
                except Exception as e:
                    logger.error(f"Error processing review: {e}")
                    skipped_count += 1
            
            # Then, mirror the review comments (inline comments on code)
            for comment in review_comments:
                try:
                    # Create a fingerprint for this comment
                    author = comment['user']['login']
                    content = comment['body'] or ""
                    content_preview = content[:50]
                    fingerprint = f"{author}:{content_preview}"
                    
                    # Skip if we've already processed this comment
                    if fingerprint in existing_comment_fingerprints:
                        logger.debug(f"Skipping already processed GitHub review comment by @{author}")
                        skipped_count += 1
                        continue
                    
                    # Format the comment body
                    path = comment.get('path', 'unknown file')
                    position = comment.get('position', 'unknown position')
                    comment_body = f"*Mirrored from GitHub review comment by @{author}*\n\n"
                    comment_body += f"**Created at: {comment.get('created_at', 'unknown time')}**\n\n"
                    comment_body += f"**File: `{path}`**\n\n"
                    
                    # Add diff context if available
                    if comment.get('diff_hunk'):
                        comment_body += "**Code context:**\n```diff\n"
                        comment_body += comment['diff_hunk']
                        comment_body += "\n```\n\n"
                    
                    # Process the content to ensure proper formatting
                    processed_content = content
                    
                    # Minimal processing for quoted content
                    if processed_content:
                        # First, normalize line endings to just \n (no \r)
                        processed_content = processed_content.replace('\r\n', '\n').replace('\r', '\n')
                        
                        # Only ensure quotes have a space after '>'
                        lines = processed_content.split('\n')
                        for i in range(len(lines)):
                            if lines[i].startswith('>') and not lines[i].startswith('> ') and len(lines[i]) > 1:
                                lines[i] = '> ' + lines[i][1:]
                        
                        processed_content = '\n'.join(lines)
                    
                    # Add the processed content
                    if processed_content:
                        comment_body += processed_content
                    
                    # Create comment in Gitea
                    comment_data = {
                        'body': comment_body
                    }
                    
                    try:
                        create_response = requests.post(gitea_api_url, headers=gitea_headers, json=comment_data)
                        create_response.raise_for_status()
                        
                        created_count += 1
                        logger.info(f"Created review comment in Gitea issue #{gitea_issue_number} by @{author}")
                        
                        # Add to our set of processed comments
                        existing_comment_fingerprints.add(fingerprint)
                    except Exception as e:
                        logger.error(f"Error creating review comment in Gitea: {e}")
                        logger.error(f"Response status: {getattr(create_response, 'status_code', 'unknown')}")
                        logger.error(f"Response text: {getattr(create_response, 'text', 'unknown')}")
                        skipped_count += 1
                except Exception as e:
                    logger.error(f"Error processing review comment: {e}")
                    skipped_count += 1
            
            logger.info(f"Review comments mirroring summary for PR #{github_pr_number}: {created_count} created, {skipped_count} skipped")
            return True
            
        except Exception as e:
            logger.warning(f"Error getting existing comments from Gitea: {e}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error mirroring review comments: {e}")
        return False 