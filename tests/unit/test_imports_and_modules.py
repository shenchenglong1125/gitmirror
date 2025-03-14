import pytest
import os
import logging
from unittest.mock import patch

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestImportsAndModules:
    """Tests for module imports and basic functionality."""

    def test_all_imports(self):
        """Test that all modules can be imported."""
        # Main package
        import gitmirror
        
        # Subpackages
        import gitmirror.github
        import gitmirror.gitea
        import gitmirror.utils
        
        # Modules
        import gitmirror.github.api
        import gitmirror.utils.logging
        import gitmirror.utils.config
        import gitmirror.mirror
        import gitmirror.cli
        import gitmirror.web
        
        # Refactored modules
        import gitmirror.gitea.repository
        import gitmirror.gitea.release
        import gitmirror.gitea.wiki
        import gitmirror.gitea.comment
        import gitmirror.gitea.issue
        import gitmirror.gitea.pr
        import gitmirror.gitea.metadata
        
        # If we got here without errors, all imports were successful
        assert True

    def test_repository_module(self):
        """Test the repository module."""
        from gitmirror.gitea.repository import get_gitea_repos
        
        # Verify the function is callable
        assert callable(get_gitea_repos)

    def test_metadata_module(self):
        """Test the metadata module."""
        from gitmirror.gitea.metadata import mirror_github_metadata
        
        # Verify the function is callable
        assert callable(mirror_github_metadata)

    def test_wiki_module(self):
        """Test the wiki module."""
        from gitmirror.gitea.wiki import mirror_github_wiki
        
        # Verify the function is callable
        assert callable(mirror_github_wiki)

    def test_issue_module(self):
        """Test the issue module."""
        from gitmirror.gitea.issue import mirror_github_issues, delete_all_issues
        
        # Verify the functions are callable
        assert callable(mirror_github_issues)
        assert callable(delete_all_issues)

    def test_pr_module(self):
        """Test the PR module."""
        from gitmirror.gitea.pr import mirror_github_prs, mirror_github_pr_review_comments
        
        # Verify the functions are callable
        assert callable(mirror_github_prs)
        assert callable(mirror_github_pr_review_comments)

    def test_comment_module(self):
        """Test the comment module."""
        from gitmirror.gitea.comment import mirror_github_issue_comments
        
        # Verify the function is callable
        assert callable(mirror_github_issue_comments)

    def test_release_module(self):
        """Test the release module."""
        from gitmirror.gitea.release import (
            check_gitea_release_exists,
            create_gitea_release,
            delete_release,
            mirror_release_asset,
            verify_gitea_release
        )
        
        # Verify the functions are callable
        assert callable(check_gitea_release_exists)
        assert callable(create_gitea_release)
        assert callable(delete_release)
        assert callable(mirror_release_asset)
        assert callable(verify_gitea_release) 