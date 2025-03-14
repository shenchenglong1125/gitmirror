import pytest
from unittest.mock import patch, MagicMock
from gitmirror.gitea.metadata import (
    mirror_github_labels,
    mirror_github_milestones
)
from gitmirror.gitea.issue import mirror_github_issues
from gitmirror.gitea.release import create_gitea_release
from gitmirror.gitea.repository import get_gitea_repos

class TestGiteaApi:
    """Test cases for Gitea API functionality."""

    @patch('gitmirror.gitea.issue.requests.get')
    @patch('gitmirror.gitea.issue.requests.post')
    def test_mirror_github_issues(self, mock_post, mock_get):
        """Test mirroring issues from GitHub to Gitea."""
        # Set up mock for GitHub API
        github_response = MagicMock()
        github_response.status_code = 200
        github_response.json.return_value = [
            {
                'number': 1,
                'title': 'Test Issue',
                'body': 'This is a test issue',
                'state': 'open',
                'user': {'login': 'testuser'},
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-01-02T00:00:00Z',
                'labels': [{'name': 'bug'}],
                'comments_url': 'https://api.github.com/repos/owner/repo/issues/1/comments',
                'html_url': 'https://github.com/owner/repo/issues/1'
            }
        ]

        # Set up mock for Gitea API
        gitea_response = MagicMock()
        gitea_response.status_code = 201
        gitea_response.json.return_value = {
            'id': 1,
            'number': 1,
            'title': 'Test Issue',
            'body': 'This is a test issue',
            'state': 'open'
        }

        # Set up mock for GitHub comments API
        github_comments_response = MagicMock()
        github_comments_response.status_code = 200
        github_comments_response.json.return_value = []

        # Configure mocks
        mock_get.side_effect = [github_response, github_comments_response]
        mock_post.return_value = gitea_response

        # Call the function
        result = mirror_github_issues('token', 'http://gitea.example.com', 'gitea_owner', 'gitea_repo', 'owner/repo', 'github_token')

        # Assertions
        assert result == True

    @patch('gitmirror.gitea.metadata.requests.get')
    @patch('gitmirror.gitea.metadata.requests.post')
    def test_mirror_github_labels(self, mock_post, mock_get):
        """Test mirroring labels from GitHub to Gitea."""
        # Set up mock for GitHub API
        github_response = MagicMock()
        github_response.status_code = 200
        github_response.json.return_value = [
            {
                'name': 'bug',
                'color': 'ff0000',
                'description': 'Bug label'
            }
        ]

        # Set up mock for Gitea API - get existing labels
        gitea_get_response = MagicMock()
        gitea_get_response.status_code = 200
        gitea_get_response.json.return_value = []

        # Set up mock for Gitea API - create label
        gitea_post_response = MagicMock()
        gitea_post_response.status_code = 201
        gitea_post_response.json.return_value = {
            'id': 1,
            'name': 'bug',
            'color': 'ff0000',
            'description': 'Bug label'
        }

        # Configure mocks
        mock_get.side_effect = [github_response, gitea_get_response]
        mock_post.return_value = gitea_post_response

        # Call the function
        result = mirror_github_labels('token', 'http://gitea.example.com', 'gitea_owner', 'gitea_repo', 'owner/repo', 'github_token')

        # Assertions
        assert result == True

    @patch('gitmirror.gitea.metadata.requests.get')
    @patch('gitmirror.gitea.metadata.requests.post')
    def test_mirror_github_milestones(self, mock_post, mock_get):
        """Test mirroring milestones from GitHub to Gitea."""
        # Set up mock for GitHub API
        github_response = MagicMock()
        github_response.status_code = 200
        github_response.json.return_value = [
            {
                'title': 'v1.0',
                'description': 'Version 1.0',
                'state': 'open',
                'due_on': '2023-12-31T00:00:00Z'
            }
        ]

        # Set up mock for Gitea API - get existing milestones
        gitea_get_response = MagicMock()
        gitea_get_response.status_code = 200
        gitea_get_response.json.return_value = []

        # Set up mock for Gitea API - create milestone
        gitea_post_response = MagicMock()
        gitea_post_response.status_code = 201
        gitea_post_response.json.return_value = {
            'id': 1,
            'title': 'v1.0',
            'description': 'Version 1.0',
            'state': 'open',
            'due_on': '2023-12-31T00:00:00Z'
        }

        # Configure mocks
        mock_get.side_effect = [github_response, gitea_get_response]
        mock_post.return_value = gitea_post_response

        # Call the function
        result = mirror_github_milestones('token', 'http://gitea.example.com', 'gitea_owner', 'gitea_repo', 'owner/repo', 'github_token')

        # Assertions
        assert result == True

    @patch('gitmirror.gitea.release.check_gitea_release_exists')
    @patch('gitmirror.gitea.release.requests.post')
    def test_create_gitea_release(self, mock_post, mock_check_exists):
        """Test creating a release in Gitea."""
        # Set up mocks
        mock_check_exists.return_value = False

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'id': 1,
            'tag_name': 'v1.0.0',
            'name': 'Version 1.0.0',
            'body': 'Release notes',
            'draft': False,
            'prerelease': False
        }
        mock_post.return_value = mock_response

        # Set up release data
        release = MagicMock()
        release.tag_name = 'v1.0.0'
        release.title = 'Version 1.0.0'
        release.body = 'Release notes'
        release.draft = False
        release.prerelease = False
        release.created_at = '2023-01-01T00:00:00Z'
        release.published_at = '2023-01-02T00:00:00Z'
        release.assets = []

        # Call the function - the actual implementation doesn't return a value
        result = create_gitea_release('token', 'http://gitea.example.com', 'owner', 'repo', release)

        # Assertions - we just check that the function completed without errors
        mock_post.assert_called_once()
        assert mock_post.call_args[1]['json']['tag_name'] == 'v1.0.0'

    @patch('gitmirror.gitea.release.check_gitea_release_exists')
    @patch('gitmirror.gitea.release.requests.post')
    def test_create_gitea_release_error(self, mock_post, mock_check_exists):
        """Test error handling when creating a release in Gitea."""
        # Set up mocks
        mock_check_exists.return_value = False

        mock_response = MagicMock()
        mock_response.status_code = 400
        # Configure the raise_for_status method to raise an exception
        mock_response.raise_for_status.side_effect = Exception("Bad request")
        mock_post.return_value = mock_response

        # Set up release data
        release = MagicMock()
        release.tag_name = 'v1.0.0'
        release.title = 'Version 1.0.0'
        release.body = 'Release notes'
        release.draft = False
        release.prerelease = False
        release.created_at = '2023-01-01T00:00:00Z'
        release.published_at = '2023-01-02T00:00:00Z'
        release.assets = []

        # Call the function - should handle the exception gracefully
        with pytest.raises(Exception):
            create_gitea_release('token', 'http://gitea.example.com', 'owner', 'repo', release)

    @patch('gitmirror.gitea.repository.requests.get')
    @patch('gitmirror.gitea.repository.get_repo_config')
    def test_get_gitea_repos(self, mock_get_repo_config, mock_get):
        """Test getting repositories from Gitea."""
        # Set up mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'id': 1,
                'name': 'repo1',
                'owner': {'username': 'owner1'},
                'description': 'Mirror of github_owner1/github_repo1',
                'mirror': True,
                'original_url': 'https://github.com/github_owner1/github_repo1',
                'mirror_interval': '8h0m0s'
            }
        ]
        mock_get.return_value = mock_response

        # Mock the get_repo_config function to avoid file system operations
        mock_get_repo_config.return_value = {}

        # Call the function
        repos = get_gitea_repos('token', 'http://gitea.example.com')

        # Assertions
        assert len(repos) == 1
        assert repos[0]['gitea_owner'] == 'owner1'
        assert repos[0]['gitea_repo'] == 'repo1'
        assert repos[0]['github_repo'] == 'github_owner1/github_repo1'
        assert repos[0]['is_mirror'] == True
        assert repos[0]['mirror_interval'] == '8h0m0s'

    @patch('gitmirror.gitea.repository.requests.get')
    def test_get_gitea_repos_error(self, mock_get):
        """Test error handling when getting repositories from Gitea."""
        # Set up mock
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_get.return_value = mock_response

        # Call the function
        repos = get_gitea_repos('token', 'http://gitea.example.com')

        # Assertions
        assert repos == [] 