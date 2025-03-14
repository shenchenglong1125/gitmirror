import os
import pytest
import logging
from unittest.mock import MagicMock, patch

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@pytest.fixture
def mock_github_token():
    """Fixture to provide a mock GitHub token."""
    return "mock_github_token"

@pytest.fixture
def mock_gitea_token():
    """Fixture to provide a mock Gitea token."""
    return "mock_gitea_token"

@pytest.fixture
def mock_gitea_url():
    """Fixture to provide a mock Gitea URL."""
    return "http://mock.gitea.url"

@pytest.fixture
def mock_github_repo():
    """Fixture to provide a mock GitHub repository."""
    return "mock_owner/mock_repo"

@pytest.fixture
def mock_gitea_owner():
    """Fixture to provide a mock Gitea owner."""
    return "mock_gitea_owner"

@pytest.fixture
def mock_gitea_repo():
    """Fixture to provide a mock Gitea repository."""
    return "mock_gitea_repo"

@pytest.fixture
def mock_repo_config():
    """Fixture to provide a mock repository configuration."""
    return {
        "mirror_metadata": True,
        "mirror_issues": True,
        "mirror_pull_requests": True,
        "mirror_labels": True,
        "mirror_milestones": True,
        "mirror_wiki": True,
        "mirror_releases": True
    }

@pytest.fixture
def mock_github_release():
    """Fixture to provide a mock GitHub release."""
    release = MagicMock()
    release.tag_name = "v1.0.0"
    release.name = "Release 1.0.0"
    release.body = "Release notes for 1.0.0"
    release.draft = False
    release.prerelease = False
    release.created_at = "2023-01-01T00:00:00Z"
    release.published_at = "2023-01-01T00:00:00Z"
    release.assets = []
    return release

@pytest.fixture
def mock_github_api_responses():
    """Fixture to provide mock responses for GitHub API calls."""
    return {
        "releases": [
            {
                "tag_name": "v1.0.0",
                "name": "Release 1.0.0",
                "body": "Release notes for 1.0.0",
                "draft": False,
                "prerelease": False,
                "created_at": "2023-01-01T00:00:00Z",
                "published_at": "2023-01-01T00:00:00Z",
                "assets": []
            }
        ],
        "issues": [
            {
                "number": 1,
                "title": "Test Issue",
                "body": "This is a test issue",
                "state": "open",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
                "labels": [],
                "user": {"login": "test_user"}
            }
        ],
        "pull_requests": [
            {
                "number": 2,
                "title": "Test PR",
                "body": "This is a test PR",
                "state": "open",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
                "labels": [],
                "user": {"login": "test_user"},
                "head": {"ref": "feature-branch"},
                "base": {"ref": "main"}
            }
        ],
        "labels": [
            {
                "name": "bug",
                "color": "ff0000",
                "description": "Bug report"
            }
        ],
        "milestones": [
            {
                "title": "v1.0",
                "description": "Version 1.0 milestone",
                "state": "open",
                "due_on": "2023-12-31T00:00:00Z"
            }
        ],
        "has_wiki": True
    }

@pytest.fixture
def mock_gitea_api_responses():
    """Fixture to provide mock responses for Gitea API calls."""
    return {
        "repos": [
            {
                "name": "mock_gitea_repo",
                "owner": {"login": "mock_gitea_owner"},
                "mirror": True,
                "description": '{"github_repo": "mock_owner/mock_repo"}'
            }
        ],
        "releases": [],
        "issues": [],
        "labels": [],
        "milestones": []
    }

@pytest.fixture
def mock_environment(monkeypatch):
    """Fixture to set up a mock environment for testing."""
    # Mock environment variables
    monkeypatch.setenv("GITHUB_TOKEN", "mock_github_token")
    monkeypatch.setenv("GITEA_TOKEN", "mock_gitea_token")
    monkeypatch.setenv("GITEA_URL", "http://mock.gitea.url")
    
    # Create a temporary directory for test data
    os.makedirs("./test_data", exist_ok=True)
    
    yield
    
    # Clean up
    import shutil
    if os.path.exists("./test_data"):
        shutil.rmtree("./test_data") 