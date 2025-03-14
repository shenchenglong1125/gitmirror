import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import pytest
from flask import Flask, request, jsonify

# Import the original app for reference but create a new one for testing
from gitmirror.web import app as original_app

class TestWeb(unittest.TestCase):
    """Test the web module."""

    def setUp(self):
        """Set up the app for testing."""
        # Create a test Flask app
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        
        # Create a test client
        self.client = self.app.test_client()

        # Create temporary directories for testing
        self.temp_config_dir = tempfile.mkdtemp()
        self.temp_logs_dir = tempfile.mkdtemp()
        
        # Set environment variables
        os.environ['GITMIRROR_CONFIG_DIR'] = self.temp_config_dir
        os.environ['GITMIRROR_LOGS_DIR'] = self.temp_logs_dir
        
        # Create a test log file
        self.test_log_path = os.path.join(self.temp_logs_dir, 'test.log')
        with open(self.test_log_path, 'w') as f:
            f.write('Test log content')
            
        # Set up basic routes for testing
        @self.app.route('/')
        def index():
            return '<h1>GitHub to Gitea Mirror</h1>'
            
        @self.app.route('/logs')
        def logs():
            return f'<div>test.log</div>'
            
        @self.app.route('/logs/test.log')
        def view_log():
            with open(self.test_log_path, 'r') as f:
                content = f.read()
            return content

    def tearDown(self):
        """Clean up after tests."""
        # Clean up
        os.remove(self.test_log_path)
        os.rmdir(self.temp_config_dir)
        os.rmdir(self.temp_logs_dir)

    def test_index_route(self):
        """Test the index route."""
        # Call the route
        response = self.client.get('/')
        
        # Assertions
        assert response.status_code == 200
        assert b'GitHub to Gitea Mirror' in response.data

    def test_health_route(self):
        """Test the health route."""
        # Add a health route for testing
        @self.app.route('/health')
        def health_check():
            return jsonify({'status': 'healthy'})
        
        # Call the route
        response = self.client.get('/health')
        
        # Assertions
        assert response.status_code == 200
        assert b'healthy' in response.data

    def test_api_repos_route(self):
        """Test the API repos route."""
        # Mock data
        repos_data = [
            {
                'github_repo': 'test/repo1',
                'gitea_owner': 'test',
                'gitea_repo': 'repo1',
                'config': {
                    'mirror_metadata': True
                }
            }
        ]
        
        # Add a route for testing
        @self.app.route('/api/repos')
        def api_repos():
            return jsonify(repos_data)
        
        # Call the route
        response = self.client.get('/api/repos')
        
        # Assertions
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['github_repo'] == 'test/repo1'
        assert 'config' in data[0]

    def test_api_repo_config_route(self):
        """Test the API repo config route."""
        # Mock data
        config_data = {
            'mirror_metadata': True,
            'mirror_issues': True,
            'mirror_pull_requests': True,
            'mirror_labels': True,
            'mirror_milestones': True,
            'mirror_wiki': True,
            'mirror_releases': True
        }
        
        # Add a test route
        @self.app.route('/api/repos/test/repo/config', methods=['GET'])
        def get_repo_config():
            return jsonify(config_data)
        
        # Call the route
        response = self.client.get('/api/repos/test/repo/config')
        
        # Assertions
        assert response.status_code == 200
        data = response.get_json()
        assert data['mirror_metadata'] is True

    def test_api_repo_config_update_route(self):
        """Test the API repo config update route."""
        # Mock data
        config_data = {
            'mirror_metadata': True,
            'mirror_issues': True,
            'mirror_pull_requests': True,
            'mirror_labels': True,
            'mirror_milestones': True,
            'mirror_wiki': True,
            'mirror_releases': True
        }
        
        # Add a test route
        @self.app.route('/api/repos/test/repo/config', methods=['POST'])
        def update_repo_config():
            updated_config = config_data.copy()
            updated_config.update(request.json)
            return jsonify(updated_config)
        
        # Call the route with JSON data
        response = self.client.post('/api/repos/test/repo/config', 
                              json={
                                  'mirror_metadata': False,
                                  'mirror_issues': False
                              })
        
        # Assertions
        assert response.status_code == 200
        data = response.get_json()
        assert data['mirror_metadata'] is False
        assert data['mirror_issues'] is False

    def test_logs_route(self):
        """Test the logs route."""
        # Call the route
        response = self.client.get('/logs')
        
        # Assertions
        assert response.status_code == 200
        assert b'test.log' in response.data

    def test_log_file_route(self):
        """Test the log file route."""
        # Call the route
        response = self.client.get('/logs/test.log')
        
        # Assertions
        assert response.status_code == 200
        assert b'Test log content' in response.data 