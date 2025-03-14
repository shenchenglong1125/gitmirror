import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock, mock_open
from gitmirror.mirror import (
    mirror_repository,
    get_repo_config,
    save_repo_config
)
from gitmirror.github.api import get_github_releases
from gitmirror.gitea.repository import get_gitea_repos, create_or_update_repo, trigger_mirror_sync
from gitmirror.gitea.release import create_gitea_release
from gitmirror.gitea.metadata import mirror_github_metadata

class TestMirror:
    """Test cases for mirror functionality."""

    @patch('gitmirror.mirror.mirror_github_metadata')
    @patch('gitmirror.mirror.create_gitea_release')
    @patch('gitmirror.mirror.get_github_releases')
    @patch('gitmirror.mirror.trigger_mirror_sync')
    @patch('gitmirror.mirror.create_or_update_repo')
    @patch('gitmirror.mirror.get_repo_config')
    @patch('gitmirror.mirror.save_repo_config')
    def test_mirror_repository(
        self,
        mock_save_repo_config,
        mock_get_repo_config,
        mock_create_or_update_repo,
        mock_trigger_mirror_sync,
        mock_get_github_releases,
        mock_create_gitea_release,
        mock_mirror_github_metadata
    ):
        """Test the mirror_repository function."""
        # Set up mocks
        mock_get_repo_config.return_value = {
            'mirror_metadata': True,
            'mirror_issues': True,
            'mirror_pull_requests': True,
            'mirror_labels': True,
            'mirror_milestones': True,
            'mirror_wiki': True,
            'mirror_releases': True
        }
        
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
        
        # Check that save_repo_config was called with updated config
        saved_config = mock_save_repo_config.call_args[0][3]
        assert "last_mirror_timestamp" in saved_config
        assert "last_mirror_date" in saved_config

    @patch('gitmirror.mirror.create_or_update_repo')
    @patch('gitmirror.mirror.get_repo_config')
    def test_mirror_repository_failure(
        self,
        mock_get_repo_config,
        mock_create_or_update_repo
    ):
        """Test mirroring a repository with a failure."""
        # Set up mocks
        mock_get_repo_config.return_value = {
            'mirror_metadata': True,
            'mirror_issues': True,
            'mirror_pull_requests': True,
            'mirror_labels': True,
            'mirror_milestones': True,
            'mirror_wiki': True,
            'mirror_releases': True
        }
        
        mock_create_or_update_repo.return_value = False
        
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
        assert result == False
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

    @patch('gitmirror.utils.config.get_config_dir')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='{"mirror_metadata": true}')
    def test_get_repo_config(self, mock_file, mock_exists, mock_get_config_dir):
        """Test the get_repo_config function."""
        # Set up mocks
        mock_exists.return_value = True
        mock_get_config_dir.return_value = '/tmp/config'
        
        # Call the function
        config = get_repo_config('owner/repo', 'gitea_owner', 'gitea_repo')
        
        # Assertions
        assert config['mirror_metadata'] == True
        mock_file.assert_called_once()

    @patch('gitmirror.utils.config.get_repo_config_path')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_repo_config(self, mock_file, mock_get_repo_config_path):
        """Test the save_repo_config function."""
        # Set up config
        config = {
            'mirror_metadata': True,
            'mirror_issues': True,
            'mirror_pull_requests': True,
            'mirror_labels': True,
            'mirror_milestones': True,
            'mirror_wiki': True,
            'mirror_releases': True
        }
        
        # Set up mocks
        mock_get_repo_config_path.return_value = '/tmp/config/owner_repo_gitea_owner_gitea_repo.json'
        
        # Call the function
        result = save_repo_config('owner/repo', 'gitea_owner', 'gitea_repo', config)
        
        # Assertions
        assert result == True
        mock_file.assert_called_once_with('/tmp/config/owner_repo_gitea_owner_gitea_repo.json', 'w')
        mock_file().write.assert_called() 