import pytest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock
from gitmirror.mirror import mirror_repository
from gitmirror.utils.config import get_repo_config, save_repo_config
from gitmirror.github.api import get_github_releases
from gitmirror.gitea.repository import get_gitea_repos
from gitmirror.gitea.issue import mirror_github_issues
from gitmirror.gitea.metadata import mirror_github_metadata

class TestMirrorIntegration:
    """Integration tests for mirror functionality."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary directory for config files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_config_dir = os.environ.get('GITMIRROR_CONFIG_DIR')
            os.environ['GITMIRROR_CONFIG_DIR'] = temp_dir
            yield temp_dir
            if original_config_dir:
                os.environ['GITMIRROR_CONFIG_DIR'] = original_config_dir
            else:
                os.environ.pop('GITMIRROR_CONFIG_DIR', None)
    
    @patch('gitmirror.mirror.mirror_github_metadata')
    @patch('gitmirror.mirror.create_gitea_release')
    @patch('gitmirror.mirror.get_github_releases')
    @patch('gitmirror.mirror.trigger_mirror_sync')
    @patch('gitmirror.mirror.create_or_update_repo')
    def test_mirror_repository_integration(
        self,
        mock_create_or_update_repo,
        mock_trigger_mirror_sync,
        mock_get_github_releases,
        mock_create_gitea_release,
        mock_mirror_github_metadata,
        temp_config_dir
    ):
        """Test the integration of mirror_repository with its components."""
        # Set up mocks
        mock_create_or_update_repo.return_value = True
        mock_trigger_mirror_sync.return_value = True
        
        mock_release = MagicMock()
        mock_release.tag_name = "v1.0.0"
        mock_get_github_releases.return_value = [mock_release]
        
        mock_mirror_github_metadata.return_value = {
            "overall_success": True,
            "has_errors": False,
            "components": {}
        }
        
        # Create a test config
        config = {
            'mirror_metadata': True,
            'mirror_issues': True,
            'mirror_pull_requests': True,
            'mirror_labels': True,
            'mirror_milestones': True,
            'mirror_wiki': True,
            'mirror_releases': True
        }
        save_repo_config('owner/repo', 'gitea_owner', 'gitea_repo', config)
        
        # Call the function
        result = mirror_repository(
            'github_token',
            'gitea_token',
            'http://gitea.example.com',
            'owner/repo',
            'gitea_owner',
            'gitea_repo',
            force_recreate=False
        )
        
        # Assertions
        assert result == True
        mock_create_or_update_repo.assert_called_once_with(
            'gitea_token',
            'http://gitea.example.com',
            'gitea_owner',
            'gitea_repo',
            'owner/repo',
            'github_token',
            force_recreate=False,
            mirror_options={
                'mirror_issues': True,
                'mirror_pull_requests': True,
                'mirror_labels': True,
                'mirror_milestones': True,
                'mirror_wiki': True,
                'mirror_releases': True
            }
        )
        mock_trigger_mirror_sync.assert_called_once()
        mock_get_github_releases.assert_called_once()
        mock_create_gitea_release.assert_called_once()
        mock_mirror_github_metadata.assert_called_once()
        
        # Verify config was updated
        updated_config = get_repo_config('owner/repo', 'gitea_owner', 'gitea_repo')
        assert 'last_mirror_timestamp' in updated_config
        assert 'last_mirror_date' in updated_config
    
    @patch('gitmirror.gitea.issue.requests.get')
    @patch('gitmirror.gitea.issue.requests.post')
    def test_issues_mirroring_integration(self, mock_post, mock_get, temp_config_dir):
        """Test the integration of GitHub issues API with Gitea issues API."""
        # Set up GitHub API mock
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
                'html_url': 'https://github.com/owner/repo/issues/1',
                'milestone': None,
                'assignees': [],
                'closed_at': None
            }
        ]
        
        # Set up Gitea API mock
        gitea_response = MagicMock()
        gitea_response.status_code = 201
        gitea_response.json.return_value = {
            'id': 1,
            'number': 1,
            'title': 'Test Issue',
            'body': 'This is a test issue',
            'state': 'open'
        }
        
        # Set up GitHub comments API mock
        github_comments_response = MagicMock()
        github_comments_response.status_code = 200
        github_comments_response.json.return_value = []
        
        # Set up Gitea issues API mock
        gitea_issues_response = MagicMock()
        gitea_issues_response.status_code = 200
        gitea_issues_response.json.return_value = []  # No existing issues
        
        # Configure mocks
        mock_get.side_effect = [github_response, gitea_issues_response, github_comments_response, gitea_issues_response]
        mock_post.return_value = gitea_response
        
        # Set environment variables
        os.environ['GITHUB_TOKEN'] = 'github_token'
        os.environ['GITEA_TOKEN'] = 'gitea_token'
        os.environ['GITEA_URL'] = 'http://gitea.example.com'
        
        # Call the function
        result = mirror_github_issues('gitea_token', 'http://gitea.example.com', 'gitea_owner', 'gitea_repo', 'owner/repo', 'github_token')
        
        # Assertions
        assert result == True
        mock_get.assert_called()
        mock_post.assert_called_once()
        
        # Clean up
        os.environ.pop('GITHUB_TOKEN', None)
        os.environ.pop('GITEA_TOKEN', None)
        os.environ.pop('GITEA_URL', None)
    
    @patch('gitmirror.gitea.repository.requests.get')
    def test_repo_config_integration(self, mock_get, temp_config_dir):
        """Test the integration of repo config with Gitea API."""
        # Set up mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'id': 1,
                'name': 'repo1',
                'owner': {'username': 'owner1'},
                'description': 'Test repository 1',
                'mirror': True,
                'original_url': 'https://github.com/github_owner1/github_repo1',
                'mirror_interval': '8h0m0s'
            }
        ]
        mock_get.return_value = mock_response
        
        # Create a test config
        config = {
            'mirror_metadata': True,
            'mirror_issues': True,
            'mirror_pull_requests': True,
            'mirror_labels': True,
            'mirror_milestones': True,
            'mirror_wiki': True,
            'mirror_releases': True
        }
        save_repo_config('github_owner1/github_repo1', 'owner1', 'repo1', config)
        
        # Get repos from Gitea
        repos = get_gitea_repos('token', 'http://gitea.example.com')
        
        # Get config for the repo
        repo_config = get_repo_config('github_owner1/github_repo1', 'owner1', 'repo1')
        
        # Assertions
        assert len(repos) == 1
        assert repos[0]['gitea_owner'] == 'owner1'
        assert repos[0]['gitea_repo'] == 'repo1'
        assert repos[0]['github_repo'] == 'github_owner1/github_repo1'
        assert repo_config['mirror_metadata'] == True
        assert repo_config['mirror_issues'] == True
        
        # Modify config
        repo_config['mirror_issues'] = False
        save_repo_config('github_owner1/github_repo1', 'owner1', 'repo1', repo_config)
        
        # Get updated config
        updated_config = get_repo_config('github_owner1/github_repo1', 'owner1', 'repo1')
        
        # Assertions
        assert updated_config['mirror_issues'] == False 