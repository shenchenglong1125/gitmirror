import sys
import json
import argparse
import logging
from .utils.logging import setup_logging
from .utils.config import load_config
from .mirror import mirror_repository, process_all_repositories
from .gitea.repository import get_gitea_repos

def main():
    """Main entry point for the CLI"""
    # Set up logging before anything else
    logger = setup_logging()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Set up GitHub to Gitea pull mirrors')
    parser.add_argument('github_repo', nargs='?', help='GitHub repository in the format owner/repo or full URL')
    parser.add_argument('gitea_owner', nargs='?', help='Gitea owner username')
    parser.add_argument('gitea_repo', nargs='?', help='Gitea repository name')
    parser.add_argument('--list-repos', action='store_true', help='List mirrored repositories as JSON and exit')
    parser.add_argument('--force-recreate', action='store_true', help='Force recreation of repositories as mirrors')
    parser.add_argument('--mirror-metadata', action='store_true', help='Enable mirroring of issues, PRs, labels, milestones, and wikis')
    args = parser.parse_args()
    
    # Load configuration
    config = load_config()
    github_token = config['github_token']
    gitea_token = config['gitea_token']
    gitea_url = config['gitea_url']
    
    if not all([github_token, gitea_token, gitea_url]):
        logger.error("Missing required environment variables")
        logger.error("Please set GITHUB_TOKEN, GITEA_TOKEN, and GITEA_URL")
        sys.exit(1)
    
    # Handle --list-repos flag
    if args.list_repos:
        repos = get_gitea_repos(gitea_token, gitea_url)
        if repos:
            print(json.dumps(repos))
        else:
            print("[]")
        sys.exit(0)
    
    # Determine if metadata should be mirrored
    mirror_metadata = args.mirror_metadata
    if args.mirror_metadata:
        logger.info("Enabling metadata mirroring (issues, PRs, labels, milestones, wikis)")
    else:
        logger.info("Metadata mirroring is disabled (use --mirror-metadata to enable)")
    
    # Check if specific repository is provided
    if args.github_repo and args.gitea_owner and args.gitea_repo:
        logger.info(f"Single repository mode: {args.github_repo} -> {args.gitea_owner}/{args.gitea_repo}")
        success = mirror_repository(
            github_token, 
            gitea_token, 
            gitea_url, 
            args.github_repo, 
            args.gitea_owner, 
            args.gitea_repo,
            mirror_metadata=mirror_metadata,
            force_recreate=args.force_recreate
        )
        sys.exit(0 if success else 1)
    else:
        # No arguments provided, fetch all mirrored repositories from Gitea
        success = process_all_repositories(
            github_token, 
            gitea_token, 
            gitea_url, 
            force_recreate=args.force_recreate,
            mirror_metadata=mirror_metadata
        )
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 