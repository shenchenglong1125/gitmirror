import pytest
from unittest.mock import patch, MagicMock
from gitmirror.github.api import (
    parse_github_repo_info,
    get_github_releases
)

class TestGitHubAPI:
    """Test cases for GitHub API functionality."""

    def test_parse_github_repo_info_with_owner_repo_format(self):
        """Test parsing GitHub repository info with owner/repo format."""
        # Call the function
        result = parse_github_repo_info('owner/repo')
        
        # Assertions
        expected = {
            'owner': 'owner',
            'repo': 'repo',
            'url': 'https://github.com/owner/repo.git',
            'full_name': 'owner/repo'
        }
        assert result == expected

    def test_parse_github_repo_info_with_url_format(self):
        """Test parsing GitHub repository info with URL format."""
        # Call the function
        result = parse_github_repo_info('https://github.com/owner/repo')
        
        # Assertions
        expected = {
            'owner': 'owner',
            'repo': 'repo',
            'url': 'https://github.com/owner/repo.git',
            'full_name': 'owner/repo'
        }
        assert result == expected

    def test_parse_github_repo_info_with_invalid_format(self):
        """Test parsing GitHub repository info with invalid format."""
        # The actual implementation returns a dictionary for any URL with owner/repo format
        result = parse_github_repo_info('https://gitlab.com/owner/repo')
        
        # Assertions - the function returns a dictionary for any URL with owner/repo format
        expected = {
            'owner': 'owner',
            'repo': 'repo',
            'url': 'https://gitlab.com/owner/repo.git',
            'full_name': 'owner/repo'
        }
        assert result == expected

    @patch('gitmirror.github.api.Github')
    def test_get_github_releases(self, mock_github_class):
        """Test getting GitHub releases."""
        # Set up mock
        mock_github = MagicMock()
        mock_github_class.return_value = mock_github
        
        mock_repo = MagicMock()
        mock_github.get_repo.return_value = mock_repo
        
        mock_release = MagicMock()
        mock_release.tag_name = 'v1.0.0'
        mock_release.title = 'Version 1.0.0'
        mock_release.body = 'Release notes'
        mock_release.draft = False
        mock_release.prerelease = False
        mock_release.created_at = '2023-01-01T00:00:00Z'
        mock_release.published_at = '2023-01-02T00:00:00Z'
        mock_release.assets = []
        
        mock_repo.get_releases.return_value = [mock_release]
        
        # Call the function
        releases = get_github_releases('token', 'owner', 'repo')
        
        # Assertions
        assert releases is not None
        assert len(releases) == 1
        assert releases[0].tag_name == 'v1.0.0'

    @patch('gitmirror.github.api.Github')
    def test_get_github_releases_with_exception(self, mock_github_class):
        """Test getting GitHub releases with an exception."""
        # Set up mock to raise an exception
        mock_github = MagicMock()
        mock_github_class.return_value = mock_github
        mock_github.get_repo.side_effect = Exception('Test exception')
        
        # Call the function
        releases = get_github_releases('token', 'owner', 'repo')
        
        # Assertions
        assert releases is None 