import os
import json
import logging
import subprocess
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_caching import Cache
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

from .utils.logging import setup_logging
from .utils.config import (
    load_config, 
    get_default_config, 
    save_default_config, 
    get_repo_config, 
    save_repo_config,
    get_all_repo_configs,
    get_config_dir
)
from .gitea.repository import get_gitea_repos, check_repo_exists, is_repo_mirror, is_repo_empty, create_or_update_repo
from .gitea.metadata import mirror_github_metadata, delete_all_issues_and_prs
from .mirror import mirror_repository, process_all_repositories

# Set up logging
logger = setup_logging(service_name='web')

# Create Flask app
app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates'))
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_key')

# Configure caching
cache = Cache(app, config={
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 300  # 5 minutes
})

# Global variables
scheduler = None
config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
config = {
    'scheduler_enabled': False,
    'mirror_interval': 8,  # Default to 8 hours
    'last_run': None,
    'next_run': None,
    'log_level': 'INFO'  # Default log level
}

def load_app_config():
    """Load application configuration from file"""
    global config
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                loaded_config = json.load(f)
                config.update(loaded_config)
                logger.info(f"Loaded configuration from {config_file}")
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")

def save_app_config():
    """Save application configuration to file"""
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)
            logger.info(f"Saved configuration to {config_file}")
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")

def run_mirror_script():
    """Run the mirror script as a scheduled task"""
    try:
        # Update last run time
        config['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_app_config()
        
        # Load configuration from environment variables
        env_config = load_config()
        github_token = env_config['github_token']
        gitea_token = env_config['gitea_token']
        gitea_url = env_config['gitea_url']
        
        # Run process_all_repositories directly
        success = process_all_repositories(
            github_token,
            gitea_token,
            gitea_url,
            mirror_metadata=None  # Use repository-specific configuration
        )
        
        logger.info(f"Scheduled mirror script completed with success={success}")
        return success
    except Exception as e:
        logger.error(f"Error running scheduled mirror script: {e}")
        return False

def start_scheduler():
    """Start the scheduler"""
    global scheduler
    
    if scheduler is None:
        scheduler = BackgroundScheduler()
        
    # Clear any existing jobs
    scheduler.remove_all_jobs()
    
    if config['scheduler_enabled']:
        # Convert hours to seconds
        interval_seconds = config['mirror_interval'] * 3600
        
        # Add the job
        scheduler.add_job(
            func=run_mirror_script,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id='mirror_job',
            name='Mirror GitHub to Gitea',
            replace_existing=True
        )
        
        # Calculate next run time
        next_run = int(time.time()) + interval_seconds
        config['next_run'] = next_run
        save_app_config()
        
        # Start the scheduler if it's not already running
        if not scheduler.running:
            scheduler.start()
            logger.info(f"Scheduler started with interval of {config['mirror_interval']} hours")
    else:
        # Stop the scheduler if it's running
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Scheduler stopped")

def stop_scheduler():
    """Stop the scheduler"""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")

@app.context_processor
def inject_current_year():
    """Inject current year into templates"""
    return {
        'current_year': datetime.now().year,
        'gitea_url': os.getenv('GITEA_URL', ''),
        'config': config
    }

@app.template_filter('timestamp_to_datetime')
def timestamp_to_datetime(timestamp):
    """Convert timestamp to formatted datetime string"""
    if timestamp is None:
        return "Never"
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

# Helper functions for common operations
def get_log_files(sort_by_newest=True):
    """Get all log files from the logs directory
    
    Args:
        sort_by_newest: Whether to sort by modification time (newest first)
        
    Returns:
        List of dictionaries with log file information
    """
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    log_files = []
    
    if os.path.exists(log_dir):
        for file in os.listdir(log_dir):
            if file.endswith('.log'):
                file_path = os.path.join(log_dir, file)
                file_size = os.path.getsize(file_path)
                file_mtime = os.path.getmtime(file_path)
                
                log_files.append({
                    'name': file,
                    'filename': file,
                    'path': file_path,
                    'size': file_size / 1024,  # Size in KB
                    'mtime': datetime.fromtimestamp(file_mtime),
                    'date': datetime.fromtimestamp(file_mtime)
                })
    
    # Sort by modification time (newest first) if requested
    if sort_by_newest:
        log_files.sort(key=lambda x: x['mtime'], reverse=True)
    
    return log_files

def validate_log_filename(filename):
    """Validate a log filename to prevent directory traversal
    
    Args:
        filename: The filename to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    return '..' not in filename and filename.endswith('.log')

def get_log_file_path(filename):
    """Get the full path to a log file
    
    Args:
        filename: The log filename
        
    Returns:
        str: The full path to the log file
    """
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    return os.path.join(log_dir, filename)

@app.route('/')
def index():
    """Home page"""
    # Get log files for the home page
    log_files = get_log_files(sort_by_newest=True)
    
    return render_template('index.html', log_files=log_files)

@app.route('/repos')
def repos():
    """Repositories page"""
    # Load configuration from environment variables
    env_config = load_config()
    github_token = env_config['github_token']
    gitea_token = env_config['gitea_token']
    gitea_url = env_config['gitea_url']
    
    logger.info("Accessing repositories page")
    
    # Get mirrored repositories
    repos = get_gitea_repos(gitea_token, gitea_url)
    logger.info(f"Found {len(repos)} repositories")
    
    for repo in repos:
        logger.info(f"Repository: {repo['gitea_owner']}/{repo['gitea_repo']} -> {repo['github_repo']}")
    
    return render_template('repos.html', repos=repos, gitea_url=gitea_url)

@app.route('/run', methods=['GET', 'POST'])
def run_now():
    """Run mirror script page"""
    if request.method == 'POST':
        # Get form data
        mirror_type = request.form.get('mirror_type', 'all')
        mirror_metadata = 'mirror_metadata' in request.form
        mirror_releases = 'mirror_releases' in request.form
        
        # Generate a unique log filename based on timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f"mirror_{timestamp}.log"
        
        if mirror_type == 'specific':
            # Get form data for specific repository
            github_repo = request.form.get('github_repo', '').strip()
            gitea_owner = request.form.get('gitea_owner', '').strip()
            gitea_repo = request.form.get('gitea_repo', '').strip()
            
            # Validate inputs
            if not all([github_repo, gitea_owner, gitea_repo]):
                flash("All fields are required for specific repository", "error")
                return redirect(url_for('run_mirror'))
            
            # Include repository info in log filename
            log_filename = f"mirror_{gitea_owner}_{gitea_repo}_{timestamp}.log"
            
            # Load configuration from environment variables
            env_config = load_config()
            github_token = env_config['github_token']
            gitea_token = env_config['gitea_token']
            gitea_url = env_config['gitea_url']
            
            # Get repository-specific configuration if mirror_metadata is not explicitly set
            repo_config = get_repo_config(github_repo, gitea_owner, gitea_repo)
            if 'mirror_metadata' not in request.form:
                mirror_metadata = repo_config.get('mirror_metadata', False)
            if 'mirror_releases' not in request.form:
                mirror_releases = repo_config.get('mirror_releases', False)
            
            # Run in a separate thread to avoid blocking the response
            def run_specific_mirror():
                # Get repository configuration
                repo_config = get_repo_config(github_repo, gitea_owner, gitea_repo)
                
                # Update repository config with the form values for this run
                temp_config = repo_config.copy()
                temp_config['mirror_metadata'] = mirror_metadata
                temp_config['mirror_releases'] = mirror_releases
                
                success = mirror_repository(
                    github_token,
                    gitea_token,
                    gitea_url,
                    github_repo,
                    gitea_owner,
                    gitea_repo,
                    mirror_metadata=mirror_metadata,
                    repo_config=temp_config
                )
                logger.info(f"Mirror script for {github_repo} completed with success={success}")
            
            thread = threading.Thread(target=run_specific_mirror)
            thread.daemon = True
            thread.start()
            
            flash(f"Mirror script started for {gitea_owner}/{gitea_repo}", "success")
        else:
            # Run for all repositories
            def run_all_mirrors():
                # Load configuration from environment variables
                env_config = load_config()
                github_token = env_config['github_token']
                gitea_token = env_config['gitea_token']
                gitea_url = env_config['gitea_url']
                
                # Run process_all_repositories directly instead of using run_mirror_script
                success = process_all_repositories(
                    github_token,
                    gitea_token,
                    gitea_url,
                    mirror_metadata=mirror_metadata,
                    mirror_releases=mirror_releases
                )
                logger.info(f"Mirror script for all repositories completed with success={success}")
            
            thread = threading.Thread(target=run_all_mirrors)
            thread.daemon = True
            thread.start()
            
            flash("Mirror script started for all repositories", "success")
        
        # Wait a moment for the log file to be created
        time.sleep(1)
        
        # Find the most recent log file
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        latest_log = None
        latest_time = 0
        
        if os.path.exists(log_dir):
            for file in os.listdir(log_dir):
                if file.endswith('.log'):
                    file_path = os.path.join(log_dir, file)
                    file_mtime = os.path.getmtime(file_path)
                    if file_mtime > latest_time:
                        latest_time = file_mtime
                        latest_log = file
        
        # Redirect to the log page if we found a log file
        if latest_log:
            return redirect(url_for('view_log', filename=latest_log))
        else:
            # Fallback to the logs page if we couldn't find a specific log
            return redirect(url_for('logs'))
    
    # Handle GET requests with query parameters
    elif request.method == 'GET' and request.args:
        # Check if we have query parameters for a specific repository
        mirror_type = request.args.get('mirror_type')
        github_repo = request.args.get('github_repo', '').strip()
        gitea_owner = request.args.get('gitea_owner', '').strip()
        gitea_repo = request.args.get('gitea_repo', '').strip()
        
        # Check for metadata mirroring options
        mirror_issues = request.args.get('mirror_issues') == 'true'
        mirror_prs = request.args.get('mirror_prs') == 'true'
        mirror_labels = request.args.get('mirror_labels') == 'true'
        mirror_milestones = request.args.get('mirror_milestones') == 'true'
        mirror_wiki = request.args.get('mirror_wiki') == 'true'
        
        # If any of the specific mirror options are provided, use them
        if any([mirror_issues, mirror_prs, mirror_labels, mirror_milestones, mirror_wiki]):
            mirror_metadata = True
        else:
            mirror_metadata = request.args.get('mirror_metadata') == 'true'
        
        # If we have a specific repository to mirror
        if mirror_type == 'github' and all([github_repo, gitea_owner, gitea_repo]):
            # Load configuration from environment variables
            env_config = load_config()
            github_token = env_config['github_token']
            gitea_token = env_config['gitea_token']
            gitea_url = env_config['gitea_url']
            
            # Get repository-specific configuration
            repo_config = get_repo_config(github_repo, gitea_owner, gitea_repo)
            
            # Update repository config with query parameters if provided
            if any([mirror_issues, mirror_prs, mirror_labels, mirror_milestones, mirror_wiki]):
                repo_config['mirror_issues'] = mirror_issues
                repo_config['mirror_pull_requests'] = mirror_prs
                repo_config['mirror_labels'] = mirror_labels
                repo_config['mirror_milestones'] = mirror_milestones
                repo_config['mirror_wiki'] = mirror_wiki
                
                # Save the updated configuration
                save_repo_config(github_repo, gitea_owner, gitea_repo, repo_config)
                logger.info(f"Updated configuration for {gitea_owner}/{gitea_repo}: {repo_config}")
            
            # Run in a separate thread to avoid blocking the response
            def run_specific_mirror():
                success = mirror_repository(
                    github_token,
                    gitea_token,
                    gitea_url,
                    github_repo,
                    gitea_owner,
                    gitea_repo,
                    mirror_metadata=mirror_metadata
                )
                logger.info(f"Mirror script for {github_repo} completed with success={success}")
            
            thread = threading.Thread(target=run_specific_mirror)
            thread.daemon = True
            thread.start()
            
            flash("Mirror script started for specific repository", "success")
            return redirect(url_for('index'))
    
    return render_template('run.html')

@app.route('/logs')
def logs():
    """Logs page"""
    log_files = get_log_files(sort_by_newest=True)
    
    # Log the number of log files found
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    logger.info(f"Found {len(log_files)} log files in {log_dir}")
    
    return render_template('logs.html', log_files=log_files)

@app.route('/logs/<filename>')
def view_log(filename):
    """View log file"""
    # Validate the filename to prevent directory traversal
    if not validate_log_filename(filename):
        logger.warning(f"Invalid log filename requested: {filename}")
        flash("Invalid log filename", "danger")
        return redirect(url_for('logs'))
    
    file_path = get_log_file_path(filename)
    
    if not os.path.exists(file_path):
        logger.warning(f"Log file not found: {file_path}")
        flash("Log file not found", "danger")
        return redirect(url_for('logs'))
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        return render_template('log.html', filename=filename, log_content=content)
    except Exception as e:
        logger.error(f"Error reading log file {file_path}: {e}")
        flash(f"Error reading log file: {e}", "danger")
        return redirect(url_for('logs'))

@app.route('/api/logs/<filename>')
def api_log_content(filename):
    """API endpoint to get log content"""
    # Validate the filename to prevent directory traversal
    if not validate_log_filename(filename):
        logger.warning(f"Invalid log filename requested via API: {filename}")
        return jsonify({'error': 'Invalid log filename'}), 400
    
    file_path = get_log_file_path(filename)
    
    if not os.path.exists(file_path):
        logger.warning(f"Log file not found via API: {file_path}")
        return jsonify({'error': 'Log file not found'}), 404
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        return jsonify({'content': content})
    except Exception as e:
        logger.error(f"Error reading log file via API {file_path}: {e}")
        return jsonify({'error': f'Error reading log file: {e}'}), 500

@app.route('/config', methods=['GET', 'POST'])
def config_page():
    """Configuration page"""
    if request.method == 'POST':
        try:
            # Get form data
            mirror_interval = int(request.form.get('mirror_interval', 8))
            scheduler_enabled = 'scheduler_enabled' in request.form
            log_level = request.form.get('log_level', 'INFO')
            
            # Validate input
            if mirror_interval < 1:
                return "Mirror interval must be at least 1 hour", 400
                
            # Validate log level
            valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if log_level not in valid_log_levels:
                return f"Invalid log level. Must be one of: {', '.join(valid_log_levels)}", 400
            
            # Update configuration
            config['mirror_interval'] = mirror_interval
            config['scheduler_enabled'] = scheduler_enabled
            config['log_level'] = log_level
            
            # Save configuration
            save_app_config()
            
            # Restart scheduler with new settings
            start_scheduler()
            
            # Update logging level
            root_logger = logging.getLogger()
            numeric_level = getattr(logging, log_level.upper(), None)
            if isinstance(numeric_level, int):
                root_logger.setLevel(numeric_level)
                logger.info(f"Logging level updated to {log_level}")
            
            flash('Configuration saved successfully', 'success')
            return redirect(url_for('config_page'))
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            flash(f"Error updating configuration: {e}", 'danger')
            return redirect(url_for('config_page'))
    
    # Prepare data for the template
    next_run = None
    if config['scheduler_enabled'] and config.get('next_run'):
        next_run = datetime.fromtimestamp(config['next_run'])
    
    # Pass the valid log levels to the template
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    
    return render_template('config.html', 
                          config=config, 
                          next_run=next_run,
                          valid_log_levels=valid_log_levels)

@app.route('/api/run-now', methods=['POST'])
def api_run_now():
    """Run mirror script immediately via API"""
    data = request.get_json(silent=True) or {}
    mirror_metadata = data.get('mirror_metadata')
    mirror_releases = data.get('mirror_releases')
    
    def run_in_thread():
        env_config = load_config()
        github_token = env_config['github_token']
        gitea_token = env_config['gitea_token']
        gitea_url = env_config['gitea_url']
        success = process_all_repositories(
            github_token,
            gitea_token,
            gitea_url,
            mirror_metadata=mirror_metadata,
            mirror_releases=mirror_releases
        )
        logger.info(f"Mirror script completed with success={success}")
    
    thread = threading.Thread(target=run_in_thread)
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': 'Mirror script started'})

@app.route('/add', methods=['GET', 'POST'])
def add_repository():
    """Add repository page"""
    if request.method == 'POST':
        try:
            # Get form data
            github_repo = request.form.get('github_repo', '').strip()
            gitea_owner = request.form.get('gitea_owner', '').strip()
            gitea_repo = request.form.get('gitea_repo', '').strip()
            
            # Get mirroring options
            mirror_metadata = 'mirror_metadata' in request.form
            mirror_issues = 'mirror_issues' in request.form
            mirror_pull_requests = 'mirror_pull_requests' in request.form
            mirror_labels = 'mirror_labels' in request.form
            mirror_milestones = 'mirror_milestones' in request.form
            mirror_wiki = 'mirror_wiki' in request.form
            mirror_releases = 'mirror_releases' in request.form
            force_recreate = 'force_recreate' in request.form
            
            # Create config object
            config = {
                'mirror_metadata': mirror_metadata,
                'mirror_issues': mirror_issues,
                'mirror_pull_requests': mirror_pull_requests,
                'mirror_labels': mirror_labels,
                'mirror_milestones': mirror_milestones,
                'mirror_wiki': mirror_wiki,
                'mirror_releases': mirror_releases
            }
            
            # Create mirror options object for repository creation
            mirror_options = {
                'mirror_issues': mirror_issues,
                'mirror_pull_requests': mirror_pull_requests,
                'mirror_labels': mirror_labels,
                'mirror_milestones': mirror_milestones,
                'mirror_wiki': mirror_wiki,
                'mirror_releases': mirror_releases
            }
            
            # Validate input
            if not all([github_repo, gitea_owner, gitea_repo]):
                flash("All fields are required", "danger")
                return render_template('add_repo.html', 
                                      github_repo=github_repo,
                                      gitea_owner=gitea_owner,
                                      gitea_repo=gitea_repo,
                                      config=config)
            
            # Load configuration from environment variables
            env_config = load_config()
            github_token = env_config['github_token']
            gitea_token = env_config['gitea_token']
            gitea_url = env_config['gitea_url']
            
            # Save the repository configuration
            save_repo_config(github_repo, gitea_owner, gitea_repo, config)
            
            # Create the repository in Gitea without mirroring content
            success = create_or_update_repo(
                gitea_token,
                gitea_url,
                gitea_owner,
                gitea_repo,
                github_repo,
                github_token=github_token,
                force_recreate=force_recreate,
                skip_mirror=True,  # Skip the immediate mirroring
                mirror_options=mirror_options  # Pass the mirror options
            )
            
            if success:
                flash("Repository successfully added! You can now trigger a mirror manually or wait for the next scheduled mirror.", "success")
                return redirect(url_for('repo_config', gitea_owner=gitea_owner, gitea_repo=gitea_repo))
            else:
                # Check if the repository exists but is not a mirror
                repo_exists = check_repo_exists(gitea_token, gitea_url, gitea_owner, gitea_repo)
                
                if repo_exists:
                    is_mirror = is_repo_mirror(gitea_token, gitea_url, gitea_owner, gitea_repo)
                    is_empty = is_repo_empty(gitea_token, gitea_url, gitea_owner, gitea_repo)
                    
                    if not is_mirror and is_empty:
                        flash("Repository exists but is not a mirror. You can force recreate it as a mirror.", "warning")
                        return render_template('add_repo.html', 
                                              github_repo=github_repo,
                                              gitea_owner=gitea_owner,
                                              gitea_repo=gitea_repo,
                                              config=config,
                                              show_force_recreate=True)
                    elif not is_mirror and not is_empty:
                        flash("Repository exists, has content, and is not a mirror. If you really want to mirror TO this repository, you need to manually delete it from Gitea first and then try again.", "danger")
                    else:
                        flash("Failed to add repository. Check logs for details.", "danger")
                else:
                    flash("Failed to add repository. Check logs for details.", "danger")
                
                return render_template('add_repo.html', 
                                      github_repo=github_repo,
                                      gitea_owner=gitea_owner,
                                      gitea_repo=gitea_repo,
                                      config=config)
        except Exception as e:
            logger.error(f"Error adding repository: {e}")
            flash(f"Error adding repository: {str(e)}", "danger")
            return render_template('add_repo.html')
    
    return render_template('add_repo.html')

@app.route('/repos/<gitea_owner>/<gitea_repo>/config', methods=['GET', 'POST'])
def repo_config(gitea_owner, gitea_repo):
    """Repository configuration page"""
    # Load configuration from environment variables
    gitea_url = os.getenv('GITEA_URL', 'http://localhost:3000')
    gitea_token = os.getenv('GITEA_TOKEN', '')
    
    logger.info(f"Accessing repository configuration for {gitea_owner}/{gitea_repo}")
    
    # Get all repositories
    repos = get_gitea_repos(gitea_token, gitea_url)
    
    # Find the repository
    repo = None
    for r in repos:
        if r['gitea_owner'] == gitea_owner and r['gitea_repo'] == gitea_repo:
            repo = r
            break
    
    if not repo:
        logger.warning(f"Repository not found: {gitea_owner}/{gitea_repo}")
        flash('Repository not found', 'danger')
        return redirect(url_for('repos'))
    
    github_repo = repo['github_repo']
    logger.info(f"Found repository: {gitea_owner}/{gitea_repo} -> {github_repo}")
    
    # Handle form submission
    if request.method == 'POST':
        # Get form data
        mirror_metadata = 'mirror_metadata' in request.form
        mirror_issues = 'mirror_issues' in request.form
        mirror_pull_requests = 'mirror_pull_requests' in request.form
        mirror_labels = 'mirror_labels' in request.form
        mirror_milestones = 'mirror_milestones' in request.form
        mirror_wiki = 'mirror_wiki' in request.form
        mirror_releases = 'mirror_releases' in request.form
        
        # Create config object
        config = {
            'mirror_metadata': mirror_metadata,
            'mirror_issues': mirror_issues,
            'mirror_pull_requests': mirror_pull_requests,
            'mirror_labels': mirror_labels,
            'mirror_milestones': mirror_milestones,
            'mirror_wiki': mirror_wiki,
            'mirror_releases': mirror_releases
        }
        
        logger.info(f"Saving configuration for {gitea_owner}/{gitea_repo}: {config}")
        
        # Save config
        if save_repo_config(github_repo, gitea_owner, gitea_repo, config):
            logger.info(f"Configuration saved successfully for {gitea_owner}/{gitea_repo}")
            flash('Configuration saved successfully', 'success')
        else:
            logger.error(f"Error saving configuration for {gitea_owner}/{gitea_repo}")
            flash('Error saving configuration', 'danger')
        
        return redirect(url_for('repo_config', gitea_owner=gitea_owner, gitea_repo=gitea_repo))
    
    # Get current config
    config = get_repo_config(github_repo, gitea_owner, gitea_repo)
    logger.info(f"Current configuration for {gitea_owner}/{gitea_repo}: {config}")
    
    # Add detailed logging for debugging
    logger.debug(f"mirror_releases setting: {config.get('mirror_releases', False)}")
    logger.debug(f"Type of mirror_releases: {type(config.get('mirror_releases', False))}")
    logger.debug(f"All config keys: {list(config.keys())}")
    
    return render_template('repo_config.html', 
                          gitea_owner=gitea_owner, 
                          gitea_repo=gitea_repo,
                          github_repo=github_repo,
                          gitea_url=gitea_url,
                          config=config)

@app.route('/api/repo-config', methods=['GET'])
def api_repo_configs():
    """API endpoint to get all repository configurations"""
    configs = get_all_repo_configs()
    return jsonify(configs)

@app.route('/api/repo-config/default', methods=['POST'])
def api_default_config():
    """API endpoint to update the default repository configuration"""
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    
    data = request.get_json()
    if save_default_config(data):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to save default configuration'}), 500

@app.route('/api/repo-config/<path:github_repo>/<gitea_owner>/<gitea_repo>', methods=['POST'])
def api_repo_config(github_repo, gitea_owner, gitea_repo):
    """API endpoint to update a repository configuration"""
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    
    data = request.get_json()
    if save_repo_config(github_repo, gitea_owner, gitea_repo, data):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to save repository configuration'}), 500

@app.route('/repos/<gitea_owner>/<gitea_repo>/delete-issues', methods=['POST'])
def delete_repo_issues(gitea_owner, gitea_repo):
    """Delete all issues and PRs for a repository"""
    # Load configuration from environment variables
    env_config = load_config()
    gitea_token = env_config['gitea_token']
    gitea_url = env_config['gitea_url']
    
    logger.info(f"Received request to delete all issues and PRs for {gitea_owner}/{gitea_repo}")
    
    # Verify confirmation
    confirmation = request.form.get('confirmation', '').strip()
    if confirmation.lower() != f"{gitea_owner}/{gitea_repo}".lower():
        logger.warning(f"Invalid confirmation for deleting issues: {confirmation}")
        flash('Invalid confirmation. Please type the repository name correctly.', 'danger')
        return redirect(url_for('repo_config', gitea_owner=gitea_owner, gitea_repo=gitea_repo))
    
    # Generate a unique log filename based on timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"delete_issues_{gitea_owner}_{gitea_repo}_{timestamp}.log"
    
    # Run the deletion
    success, deleted_count, failed_count = delete_all_issues_and_prs(
        gitea_token, 
        gitea_url, 
        gitea_owner, 
        gitea_repo
    )
    
    if success:
        logger.info(f"Successfully deleted/closed {deleted_count} issues/PRs for {gitea_owner}/{gitea_repo}")
        flash(f'Successfully deleted/closed {deleted_count} issues/PRs. {failed_count} failed.', 'success')
    else:
        logger.error(f"Failed to delete issues/PRs for {gitea_owner}/{gitea_repo}")
        flash('Failed to delete issues/PRs. Check the logs for details.', 'danger')
    
    # Wait a moment for the log file to be created
    time.sleep(1)
    
    # Find the most recent log file
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    latest_log = None
    latest_time = 0
    
    if os.path.exists(log_dir):
        for file in os.listdir(log_dir):
            if file.endswith('.log'):
                file_path = os.path.join(log_dir, file)
                file_mtime = os.path.getmtime(file_path)
                if file_mtime > latest_time:
                    latest_time = file_mtime
                    latest_log = file
    
    # Redirect to the log page if we found a log file
    if latest_log:
        return redirect(url_for('view_log', filename=latest_log))
    else:
        # Fallback to the repository configuration page if we couldn't find a specific log
        return redirect(url_for('repo_config', gitea_owner=gitea_owner, gitea_repo=gitea_repo))

@app.route('/api/repos')
@cache.cached(timeout=60)  # Cache for 1 minute
def api_repos():
    """API endpoint to get repositories"""
    # Load configuration from environment variables
    env_config = load_config()
    github_token = env_config['github_token']
    gitea_token = env_config['gitea_token']
    gitea_url = env_config['gitea_url']
    
    # Get repositories from Gitea
    repos = get_gitea_repos(gitea_token, gitea_url)
    
    # Get repository-specific configurations
    repo_configs = get_all_repo_configs()
    
    # Add configuration to each repository
    for repo in repos:
        github_repo = repo.get('github_repo', '')
        gitea_owner = repo.get('gitea_owner', '')
        gitea_repo = repo.get('gitea_repo', '')
        
        # Get the configuration for this repository
        config_key = f"{github_repo}:{gitea_owner}/{gitea_repo}"
        if config_key in repo_configs:
            repo['config'] = repo_configs[config_key]
    
    return jsonify(repos)

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    # Check if we can access the logs directory
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    logs_accessible = os.path.exists(log_dir) and os.access(log_dir, os.R_OK | os.W_OK)
    
    # Check if we can access the config directory
    config_dir = get_config_dir()
    config_accessible = os.path.exists(config_dir) and os.access(config_dir, os.R_OK | os.W_OK)
    
    # Check if the scheduler is running
    scheduler_running = scheduler is not None and scheduler.running
    
    # Check environment variables
    env_config = load_config()
    env_vars_set = all([
        env_config.get('gitea_token'),
        env_config.get('gitea_url')
    ])
    
    # Determine overall health
    is_healthy = logs_accessible and config_accessible and env_vars_set
    
    health_data = {
        'status': 'healthy' if is_healthy else 'unhealthy',
        'timestamp': datetime.now().isoformat(),
        'checks': {
            'logs_directory': 'accessible' if logs_accessible else 'inaccessible',
            'config_directory': 'accessible' if config_accessible else 'inaccessible',
            'scheduler': 'running' if scheduler_running else 'stopped',
            'environment_variables': 'configured' if env_vars_set else 'incomplete'
        },
        'version': '1.0.0'  # Add your version here
    }
    
    status_code = 200 if is_healthy else 503
    return jsonify(health_data), status_code

def main():
    """Main entry point for the web UI"""
    # Load application configuration
    load_app_config()
    
    # Set up logging with configured log level
    global logger
    logger = setup_logging(config['log_level'])
    logger.info(f"Logging level set to {config['log_level']}")
    
    # Start scheduler
    start_scheduler()
    
    # Register function to stop scheduler on exit
    atexit.register(stop_scheduler)
    
    # Disable Flask's default access logs
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)  # Only show errors, not access logs
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    main()
