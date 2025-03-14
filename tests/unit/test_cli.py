import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from gitmirror.cli import main

class TestCLI:
    """Test cases for CLI functionality."""

    @patch('gitmirror.cli.mirror_repository')
    @patch('gitmirror.cli.process_all_repositories')
    @patch('os.getenv')
    def test_main_with_repo_args(
        self,
        mock_getenv,
        mock_process_all,
        mock_mirror_repository
    ):
        """Test main function with repository arguments."""
        # Set up mocks
        mock_getenv.side_effect = lambda key, default=None: {
            'GITHUB_TOKEN': 'mock_github_token',
            'GITEA_TOKEN': 'mock_gitea_token',
            'GITEA_URL': 'http://mock.gitea.url'
        }.get(key, default)
        
        mock_mirror_repository.return_value = True
        
        # Set up command line arguments
        test_args = ['cli.py', 'owner/repo', 'gitea_owner', 'gitea_repo']
        with patch.object(sys, 'argv', test_args):
            # Patch sys.exit to avoid exiting the test
            with patch('sys.exit') as mock_exit:
                # Call the function
                main()
        
        # Assertions
        mock_mirror_repository.assert_called_once_with(
            'mock_github_token',
            'mock_gitea_token',
            'http://mock.gitea.url',
            'owner/repo',
            'gitea_owner',
            'gitea_repo',
            mirror_metadata=False,
            force_recreate=False
        )
        mock_exit.assert_called_once_with(0)

    @patch('gitmirror.cli.process_all_repositories')
    @patch('os.getenv')
    def test_main_without_args(
        self,
        mock_getenv,
        mock_process_all
    ):
        """Test main function without arguments (auto-discovery mode)."""
        # Set up mocks
        mock_getenv.side_effect = lambda key, default=None: {
            'GITHUB_TOKEN': 'mock_github_token',
            'GITEA_TOKEN': 'mock_gitea_token',
            'GITEA_URL': 'http://mock.gitea.url'
        }.get(key, default)
        
        mock_process_all.return_value = True
        
        # Set up command line arguments
        test_args = ['cli.py']
        with patch.object(sys, 'argv', test_args):
            # Patch sys.exit to avoid exiting the test
            with patch('sys.exit') as mock_exit:
                # Call the function
                main()
        
        # Assertions
        mock_process_all.assert_called_once_with(
            'mock_github_token',
            'mock_gitea_token',
            'http://mock.gitea.url',
            force_recreate=False,
            mirror_metadata=False
        )
        mock_exit.assert_called_once_with(0)

    @patch('os.getenv')
    def test_main_missing_env_vars(self, mock_getenv):
        """Test main function with missing environment variables."""
        # Set up mock to return empty string for GITEA_URL
        mock_getenv.side_effect = lambda key, default=None: {
            'GITHUB_TOKEN': 'mock_github_token',
            'GITEA_TOKEN': 'mock_gitea_token',
            'GITEA_URL': ''
        }.get(key, default)
        
        # Set up command line arguments
        test_args = ['cli.py', 'owner/repo', 'gitea_owner', 'gitea_repo']
        with patch.object(sys, 'argv', test_args):
            # Patch sys.exit to avoid exiting the test
            with patch('sys.exit') as mock_exit:
                # We need to patch the load_config function to avoid file system operations
                with patch('gitmirror.cli.load_config') as mock_load_config:
                    # Configure the mock to return a dictionary with empty GITEA_URL
                    mock_load_config.return_value = {
                        'github_token': 'mock_github_token',
                        'gitea_token': 'mock_gitea_token',
                        'gitea_url': ''
                    }
                    
                    # Patch mirror_repository to avoid file system operations
                    with patch('gitmirror.cli.mirror_repository') as mock_mirror_repository:
                        # Call the function
                        main()

                        # Assertions
                        # Check that sys.exit was called with 1 at some point
                        assert mock_exit.call_count > 0
                        assert 1 in [args[0] for args, _ in mock_exit.call_args_list]

    @patch('gitmirror.cli.mirror_repository')
    @patch('os.getenv')
    def test_main_with_force_recreate(
        self,
        mock_getenv,
        mock_mirror_repository
    ):
        """Test main function with --force-recreate flag."""
        # Set up mocks
        mock_getenv.side_effect = lambda key, default=None: {
            'GITHUB_TOKEN': 'mock_github_token',
            'GITEA_TOKEN': 'mock_gitea_token',
            'GITEA_URL': 'http://mock.gitea.url'
        }.get(key, default)
        
        mock_mirror_repository.return_value = True
        
        # Set up command line arguments
        test_args = ['cli.py', 'owner/repo', 'gitea_owner', 'gitea_repo', '--force-recreate']
        with patch.object(sys, 'argv', test_args):
            # Patch sys.exit to avoid exiting the test
            with patch('sys.exit') as mock_exit:
                # Call the function
                main()
        
        # Assertions
        mock_mirror_repository.assert_called_once_with(
            'mock_github_token',
            'mock_gitea_token',
            'http://mock.gitea.url',
            'owner/repo',
            'gitea_owner',
            'gitea_repo',
            mirror_metadata=False,
            force_recreate=True
        )
        mock_exit.assert_called_once_with(0)
        
    @patch('gitmirror.cli.mirror_repository')
    @patch('os.getenv')
    def test_main_with_mirror_metadata(
        self,
        mock_getenv,
        mock_mirror_repository
    ):
        """Test main function with --mirror-metadata flag."""
        # Set up mocks
        mock_getenv.side_effect = lambda key, default=None: {
            'GITHUB_TOKEN': 'mock_github_token',
            'GITEA_TOKEN': 'mock_gitea_token',
            'GITEA_URL': 'http://mock.gitea.url'
        }.get(key, default)
        
        mock_mirror_repository.return_value = True
        
        # Set up command line arguments
        test_args = ['cli.py', 'owner/repo', 'gitea_owner', 'gitea_repo', '--mirror-metadata']
        with patch.object(sys, 'argv', test_args):
            # Patch sys.exit to avoid exiting the test
            with patch('sys.exit') as mock_exit:
                # Call the function
                main()
        
        # Assertions
        mock_mirror_repository.assert_called_once_with(
            'mock_github_token',
            'mock_gitea_token',
            'http://mock.gitea.url',
            'owner/repo',
            'gitea_owner',
            'gitea_repo',
            mirror_metadata=True,
            force_recreate=False
        )
        mock_exit.assert_called_once_with(0) 