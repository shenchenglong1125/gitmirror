import pytest
import logging
from unittest.mock import patch, MagicMock, call
import requests
import subprocess
from gitmirror.gitea.wiki import mirror_github_wiki, check_git_installed

class TestGiteaWiki:
    """Tests for the Gitea wiki module"""
    
    def test_check_git_installed_success(self):
        """Test check_git_installed when git is installed"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock()
            result = check_git_installed()
            assert result is True
            mock_run.assert_called_once_with(["git", "--version"], check=True, capture_output=True)
    
    def test_check_git_installed_failure(self):
        """Test check_git_installed when git is not installed"""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.SubprocessError()
            result = check_git_installed()
            assert result is False
            mock_run.assert_called_once_with(["git", "--version"], check=True, capture_output=True)
    
    def test_mirror_github_wiki_no_git(self):
        """Test mirror_github_wiki when git is not installed"""
        with patch('gitmirror.gitea.wiki.check_git_installed', return_value=False):
            result = mirror_github_wiki('gitea_token', 'gitea_url', 'gitea_owner', 'gitea_repo', 'github_repo')
            assert result is False
    
    def test_mirror_github_wiki_no_wiki(self):
        """Test mirror_github_wiki when the repository doesn't have a wiki"""
        with patch('gitmirror.gitea.wiki.check_git_installed', return_value=True):
            with patch('requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.raise_for_status.return_value = None
                mock_response.json.return_value = {'has_wiki': False}
                mock_get.return_value = mock_response
                
                result = mirror_github_wiki('gitea_token', 'gitea_url', 'gitea_owner', 'gitea_repo', 'github_repo')
                assert result is False
    
    def test_mirror_github_wiki_wiki_not_initialized(self):
        """Test mirror_github_wiki when the wiki is enabled but not initialized"""
        with patch('gitmirror.gitea.wiki.check_git_installed', return_value=True):
            with patch('requests.get') as mock_get:
                # First call to check if wiki is enabled
                first_response = MagicMock()
                first_response.raise_for_status.return_value = None
                first_response.json.return_value = {'has_wiki': True}
                
                # Second call to check wiki contents (404 - not found)
                second_response = MagicMock()
                second_response.status_code = 404
                
                # Third call to check wiki repo directly (404 - not found)
                third_response = MagicMock()
                third_response.status_code = 404
                
                mock_get.side_effect = [first_response, second_response, third_response]
                
                result = mirror_github_wiki('gitea_token', 'gitea_url', 'gitea_owner', 'gitea_repo', 'github_repo')
                assert result is False
    
    def test_mirror_github_wiki_success(self, caplog):
        """Test mirror_github_wiki when successful"""
        caplog.set_level(logging.INFO)
        
        with patch('gitmirror.gitea.wiki.check_git_installed', return_value=True):
            with patch('requests.get') as mock_get:
                # First call to check if wiki is enabled
                first_response = MagicMock()
                first_response.raise_for_status.return_value = None
                first_response.json.return_value = {'has_wiki': True}
                
                # Second call to check wiki contents (200 - found)
                second_response = MagicMock()
                second_response.status_code = 200
                
                # Additional calls for repository checks
                repo_response = MagicMock()
                repo_response.status_code = 404  # Wiki repo doesn't exist yet
                
                # Final call for main repo info
                main_repo_response = MagicMock()
                main_repo_response.status_code = 200
                main_repo_response.json.return_value = {'description': ''}
                
                mock_get.side_effect = [first_response, second_response, repo_response, main_repo_response]
                
                with patch('requests.post') as mock_post:
                    create_response = MagicMock()
                    create_response.status_code = 201
                    mock_post.return_value = create_response
                    
                    with patch('tempfile.TemporaryDirectory'):
                        with patch('subprocess.run') as mock_run:
                            mock_run.return_value = MagicMock()
                            
                            with patch('os.path.exists', return_value=True):
                                with patch('gitmirror.gitea.wiki.update_repo_description') as mock_update:
                                    mock_update.return_value = True
                                    
                                    result = mirror_github_wiki('gitea_token', 'gitea_url', 'gitea_owner', 'gitea_repo', 'github_repo', 'github_token')
                                    assert result is True
                                    
                                    # Check that token masking is used in logs
                                    assert "Using GitHub token (masked: *****token)" in caplog.text
    
    def test_token_masking_in_logs(self, caplog):
        """Test that GitHub token is masked in logs"""
        caplog.set_level(logging.INFO)
        
        with patch('gitmirror.gitea.wiki.check_git_installed', return_value=True):
            with patch('requests.get') as mock_get:
                # First call to check if wiki is enabled
                first_response = MagicMock()
                first_response.raise_for_status.return_value = None
                first_response.json.return_value = {'has_wiki': True}
                
                # Second call to check wiki contents (200 - found)
                second_response = MagicMock()
                second_response.status_code = 200
                
                mock_get.side_effect = [first_response, second_response]
                
                github_token = "github_token_value_that_should_be_masked"
                
                with patch('tempfile.TemporaryDirectory'):
                    # Just run the function and check that the token is masked in logs
                    result = mirror_github_wiki('gitea_token', 'gitea_url', 'gitea_owner', 'gitea_repo', 'github_repo', github_token)
                    
                    # Check that token is masked in logs
                    assert github_token not in caplog.text
                    assert "*****" in caplog.text 