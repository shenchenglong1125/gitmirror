import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock

from gitmirror.utils.config import (
    load_config, 
    get_default_config, 
    save_default_config, 
    get_repo_config, 
    save_repo_config,
    get_all_repo_configs
)

class TestConfig(unittest.TestCase):
    """Test the configuration module"""
    
    def setUp(self):
        """Set up test environment"""
        # Create a temporary directory for config files
        self.temp_dir = tempfile.mkdtemp()
        self.patcher = patch('gitmirror.utils.config.get_config_dir')
        self.mock_get_config_dir = self.patcher.start()
        self.mock_get_config_dir.return_value = self.temp_dir
        
    def tearDown(self):
        """Clean up test environment"""
        self.patcher.stop()
        shutil.rmtree(self.temp_dir)
    
    @patch('gitmirror.utils.config.load_dotenv')
    @patch('gitmirror.utils.config.os.getenv')
    def test_load_config(self, mock_getenv, mock_load_dotenv):
        """Test loading configuration from environment variables"""
        # Mock environment variables
        mock_getenv.side_effect = lambda key, default=None: {
            'GITHUB_TOKEN': 'test_github_token',
            'GITEA_TOKEN': 'test_gitea_token',
            'GITEA_URL': 'https://test-gitea.com'
        }.get(key, default)
        
        # Call the function
        config = load_config()
        
        # Verify the result
        self.assertEqual(config['github_token'], 'test_github_token')
        self.assertEqual(config['gitea_token'], 'test_gitea_token')
        self.assertEqual(config['gitea_url'], 'https://test-gitea.com')
        
        # Verify load_dotenv was called
        mock_load_dotenv.assert_called_once()
    
    def test_get_default_config(self):
        """Test getting default configuration"""
        # Create a default config file
        default_config = {
            'mirror_metadata': True,
            'mirror_issues': True,
            'mirror_pull_requests': False
        }
        
        os.makedirs(self.temp_dir, exist_ok=True)
        with open(os.path.join(self.temp_dir, 'default.json'), 'w') as f:
            json.dump(default_config, f)
        
        # Call the function
        config = get_default_config()
        
        # Verify the result
        self.assertEqual(config['mirror_metadata'], True)
        self.assertEqual(config['mirror_issues'], True)
        self.assertEqual(config['mirror_pull_requests'], False)
    
    def test_save_repo_config(self):
        """Test saving repository configuration"""
        # Test data
        github_repo = 'owner/repo'
        gitea_owner = 'gitea_owner'
        gitea_repo = 'gitea_repo'
        config = {
            'mirror_metadata': True,
            'mirror_releases': False
        }
        
        # Call the function
        result = save_repo_config(github_repo, gitea_owner, gitea_repo, config)
        
        # Verify the result
        self.assertTrue(result)
        
        # Verify the file was created
        config_path = os.path.join(self.temp_dir, f"{github_repo.replace('/', '_')}_{gitea_owner}_{gitea_repo}.json")
        self.assertTrue(os.path.exists(config_path))
        
        # Verify the content
        with open(config_path, 'r') as f:
            saved_config = json.load(f)
        
        self.assertEqual(saved_config['mirror_metadata'], True)
        self.assertEqual(saved_config['mirror_releases'], False)
    
    def test_get_repo_config(self):
        """Test getting repository configuration"""
        # Test data
        github_repo = 'owner/repo'
        gitea_owner = 'gitea_owner'
        gitea_repo = 'gitea_repo'
        config = {
            'mirror_metadata': True,
            'mirror_releases': False
        }
        
        # Create a config file
        os.makedirs(self.temp_dir, exist_ok=True)
        config_path = os.path.join(self.temp_dir, f"{github_repo.replace('/', '_')}_{gitea_owner}_{gitea_repo}.json")
        with open(config_path, 'w') as f:
            json.dump(config, f)
        
        # Call the function
        result = get_repo_config(github_repo, gitea_owner, gitea_repo)
        
        # Verify the result
        self.assertEqual(result['mirror_metadata'], True)
        self.assertEqual(result['mirror_releases'], False)

if __name__ == '__main__':
    unittest.main() 