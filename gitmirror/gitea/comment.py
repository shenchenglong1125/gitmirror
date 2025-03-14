import logging
import requests

logger = logging.getLogger('github-gitea-mirror')

def mirror_github_issue_comments(gitea_token, gitea_url, gitea_owner, gitea_repo, github_repo, github_issue_number, gitea_issue_number, github_token=None):
    """Mirror comments from a GitHub issue to a Gitea issue"""
    logger.info(f"Mirroring comments for issue #{github_issue_number} from GitHub to Gitea issue #{gitea_issue_number}")
    
    # GitHub API headers
    github_headers = {}
    if github_token:
        github_headers['Authorization'] = f'token {github_token}'
    
    # Gitea API headers
    gitea_headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    # Get comments from GitHub
    github_api_url = f"https://api.github.com/repos/{github_repo}/issues/{github_issue_number}/comments"
    params = {
        'per_page': 100,  # Maximum allowed by GitHub API
    }
    
    try:
        # Paginate through all comments
        page = 1
        all_comments = []
        
        while True:
            params['page'] = page
            logger.debug(f"Fetching GitHub comments page {page} for issue #{github_issue_number}")
            response = requests.get(github_api_url, headers=github_headers, params=params)
            response.raise_for_status()
            
            comments = response.json()
            if not comments:
                logger.debug(f"No more comments found on page {page}")
                break  # No more comments
                
            logger.debug(f"Found {len(comments)} comments on page {page}")
            all_comments.extend(comments)
            
            # Check if there are more pages
            if len(comments) < params['per_page']:
                break
                
            page += 1
        
        logger.info(f"Found {len(all_comments)} comments for GitHub issue #{github_issue_number}")
        
        if not all_comments:
            logger.info(f"No comments to mirror for GitHub issue #{github_issue_number}")
            return True
        
        # Get existing comments in Gitea to avoid duplicates
        gitea_api_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/issues/{gitea_issue_number}/comments"
        
        try:
            # Get all comments with pagination
            gitea_comments = []
            gitea_page = 1
            
            while True:
                logger.debug(f"Fetching Gitea comments page {gitea_page} for issue #{gitea_issue_number}")
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
                if comment['body'] and '*Mirrored from GitHub comment by @' in comment['body']:
                    # Extract the GitHub comment fingerprint
                    try:
                        body_lines = comment['body'].split('\n')
                        for i, line in enumerate(body_lines):
                            if '*Mirrored from GitHub comment by @' in line:
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
                        logger.warning(f"Failed to extract GitHub comment fingerprint: {e}")
            
            # Mirror comments
            created_count = 0
            skipped_count = 0
            
            for comment in all_comments:
                try:
                    # Create a fingerprint for this comment
                    author = comment['user']['login']
                    content = comment['body'] or ""
                    content_preview = content[:50]
                    fingerprint = f"{author}:{content_preview}"
                    
                    # Skip if we've already processed this comment
                    if fingerprint in existing_comment_fingerprints:
                        logger.debug(f"Skipping already processed GitHub comment by @{author}")
                        skipped_count += 1
                        continue
                    
                    # Format the comment body
                    comment_body = f"*Mirrored from GitHub comment by @{author}*\n\n"
                    comment_body += f"**Created at: {comment['created_at']}**\n\n"
                    
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
                        logger.info(f"Created comment in Gitea issue #{gitea_issue_number} by @{author}")
                        
                        # Add to our set of processed comments
                        existing_comment_fingerprints.add(fingerprint)
                    except Exception as e:
                        logger.error(f"Error creating comment in Gitea: {e}")
                        logger.error(f"Response status: {getattr(create_response, 'status_code', 'unknown')}")
                        logger.error(f"Response text: {getattr(create_response, 'text', 'unknown')}")
                        skipped_count += 1
                except Exception as e:
                    logger.error(f"Error processing comment: {e}")
                    skipped_count += 1
            
            logger.info(f"Comments mirroring summary for issue #{github_issue_number}: {created_count} created, {skipped_count} skipped")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting existing comments from Gitea: {e}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting comments from GitHub: {e}")
        return False 