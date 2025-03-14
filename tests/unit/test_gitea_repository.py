import pytest
from unittest.mock import patch, MagicMock
from gitmirror.gitea.repository import (
    get_gitea_repos,
    create_or_update_repo,
    trigger_mirror_sync
)
from gitmirror.gitea.repository import get_repo_config

class TestGiteaRepository:
    """Test cases for Gitea repository functionality."""

    @patch('gitmirror.gitea.repository.requests.get')
    @patch('gitmirror.gitea.repository.get_repo_config')
    def test_get_gitea_repos_success(self, mock_get_repo_config, mock_get):
        """Test getting repositories from Gitea successfully."""
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
                'original_url': 'https://github.com/github_owner1/github_repo1'
            },
            {
                'id': 2,
                'name': 'repo2',
                'owner': {'username': 'owner2'},
                'description': 'Mirror of github_owner2/github_repo2',
                'mirror': True,
                'original_url': 'https://github.com/github_owner2/github_repo2'
            }
        ]
        mock_get.return_value = mock_response
        
        # Mock the get_repo_config function to avoid file system operations
        mock_get_repo_config.return_value = {}
        
        # Call the function
        repos = get_gitea_repos('token', 'http://mock.gitea.url')
        
        # Assertions
        assert len(repos) == 2
        assert repos[0]["gitea_repo"] == "repo1"
        assert repos[0]["gitea_owner"] == "owner1"
        assert repos[0]["github_repo"] == "github_owner1/github_repo1"
        assert repos[0]["is_mirror"] == True

    @patch('gitmirror.gitea.repository.requests.get')
    def test_get_gitea_repos_with_error(self, mock_get):
        """Test getting repositories from Gitea with an error."""
        # Set up mock
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        # Call the function
        repos = get_gitea_repos('token', 'http://mock.gitea.url')
        
        # Assertions
        assert repos == []

    @patch('gitmirror.gitea.repository.requests.get')
    def test_get_gitea_repos_with_exception(self, mock_get):
        """Test getting repositories from Gitea with an exception."""
        # Set up mock to raise an exception
        mock_get.side_effect = Exception('Test exception')
        
        # Call the function
        repos = get_gitea_repos('token', 'http://mock.gitea.url')
        
        # Assertions
        assert repos == []

    @patch('gitmirror.gitea.repository.requests.patch')
    @patch('gitmirror.gitea.repository.requests.get')
    @patch('gitmirror.gitea.repository.get_repo_config')
    def test_create_or_update_repo_existing(self, mock_get_repo_config, mock_get, mock_patch):
        """Test updating an existing Gitea repository."""
        # Set up mock responses for the repository check
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        # The API returns a dictionary, not a list
        mock_get_response.json.return_value = {
            "id": 1,
            "name": "mock_repo",
            "owner": {"login": "mock_owner"},
            "mirror": False
        }
        
        # Set up mock for commits check
        mock_commits_response = MagicMock()
        mock_commits_response.status_code = 200
        mock_commits_response.json.return_value = []  # Empty repository
        
        # Configure the get mock to return different responses for different URLs
        def get_side_effect(url, **kwargs):
            if url.endswith('/mock_repo'):
                return mock_get_response
            elif url.endswith('/commits'):
                return mock_commits_response
            return MagicMock()
        
        mock_get.side_effect = get_side_effect

        # Mock the delete response
        mock_delete_response = MagicMock()
        mock_delete_response.status_code = 204
        
        # Mock the post response for creating a new repository
        mock_post_response = MagicMock()
        mock_post_response.status_code = 201
        
        # Mock the get_repo_config function
        mock_get_repo_config.return_value = {}

        # Mock the delete and post requests
        with patch('gitmirror.gitea.repository.requests.delete') as mock_delete:
            mock_delete.return_value = mock_delete_response
            
            with patch('gitmirror.gitea.repository.requests.post') as mock_post:
                mock_post.return_value = mock_post_response
                
                # Call the function with force_recreate=True
                result = create_or_update_repo(
                    "mock_token",
                    "http://mock.gitea.url",
                    "mock_owner",
                    "mock_repo",
                    "github_owner/github_repo",
                    "mock_github_token",
                    force_recreate=True
                )

        # Assertions
        assert result == True
        mock_delete.assert_called_once()
        mock_post.assert_called_once()
        
        # Check that the JSON payload contains the expected fields
        json_payload = mock_post.call_args[1]["json"]
        assert "repo_name" in json_payload
        assert json_payload["repo_name"] == "mock_repo"
        assert json_payload["mirror"] == True
        assert "description" in json_payload
        assert "Mirror of github_owner/github_repo" in json_payload["description"]

    @patch('gitmirror.gitea.repository.requests.post')
    @patch('gitmirror.gitea.repository.requests.get')
    def test_create_or_update_repo_new(self, mock_get, mock_post):
        """Test creating a new Gitea repository."""
        # Set up mock responses
        mock_get_response = MagicMock()
        mock_get_response.status_code = 404
        mock_get.return_value = mock_get_response

        mock_post_response = MagicMock()
        mock_post_response.status_code = 201
        mock_post.return_value = mock_post_response

        # Call the function
        result = create_or_update_repo(
            "mock_token",
            "http://mock.gitea.url",
            "mock_owner",
            "mock_repo",
            "github_owner/github_repo",
            "mock_github_token",
            force_recreate=False
        )

        # Assertions
        mock_get.assert_called_once()
        mock_post.assert_called_once()

        # Check that the JSON payload contains the expected fields
        json_payload = mock_post.call_args[1]["json"]
        assert "repo_name" in json_payload
        assert json_payload["repo_name"] == "mock_repo"
        assert "mirror" in json_payload
        assert json_payload["mirror"] == True
        assert "description" in json_payload
        assert "Mirror of github_owner/github_repo" in json_payload["description"]

    @patch('gitmirror.gitea.repository.requests.post')
    def test_trigger_mirror_sync_success(self, mock_post):
        """Test triggering mirror sync successfully."""
        # Set up mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Call the function
        result = trigger_mirror_sync('token', 'http://mock.gitea.url', 'owner', 'repo')
        
        # Assertions
        assert result == True
        mock_post.assert_called_once()
        
        # Check that the request was made with the correct URL and headers
        args, kwargs = mock_post.call_args
        assert args[0] == 'http://mock.gitea.url/api/v1/repos/owner/repo/mirror-sync'
        assert kwargs['headers']['Authorization'] == 'token token'
        assert kwargs['headers']['Content-Type'] == 'application/json'

    @patch('gitmirror.gitea.repository.requests.post')
    def test_trigger_mirror_sync_failure(self, mock_post):
        """Test triggering mirror sync with a failure."""
        # Set up mock
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_post.return_value = mock_response
        
        # Call the function
        result = trigger_mirror_sync('token', 'http://mock.gitea.url', 'owner', 'repo')
        
        # Assertions
        assert result == False
        mock_post.assert_called_once()
        
        # Check that the request was made with the correct URL and headers
        args, kwargs = mock_post.call_args
        assert args[0] == 'http://mock.gitea.url/api/v1/repos/owner/repo/mirror-sync'
        assert kwargs['headers']['Authorization'] == 'token token'
        assert kwargs['headers']['Content-Type'] == 'application/json' 