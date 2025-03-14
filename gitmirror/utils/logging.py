import os
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logging(log_level='INFO'):
    """Set up logging configuration with log rotation
    
    Args:
        log_level (str): The logging level to use (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        logging.Logger: The configured logger
    """
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(log_dir, f'mirror-{timestamp}.log')
    
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        print(f"Invalid log level: {log_level}, defaulting to INFO")
        numeric_level = logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            # Use RotatingFileHandler instead of FileHandler for log rotation
            RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,  # Keep 5 backup files
            ),
            logging.StreamHandler()
        ]
    )
    
    # Set requests and urllib3 logging to WARNING to reduce noise
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return logging.getLogger('github-gitea-mirror')

def get_current_log_filename(logger):
    """Get the current log file name from the logger handlers
    
    Args:
        logger: The logger instance to check for handlers
        
    Returns:
        str: The basename of the log file, or a fallback name if not found
    """
    try:
        # Check for both RotatingFileHandler and regular FileHandler
        for handler in logger.handlers:
            if hasattr(handler, 'baseFilename'):
                return os.path.basename(handler.baseFilename)
                
        # If no handler with baseFilename is found, use a fallback
        timestamp = datetime.now().strftime('%Y-%m-%d')
        fallback_name = f'mirror-{timestamp}.log'
        logger.info(f"Using fallback log filename: {fallback_name}")
        return fallback_name
    except Exception as e:
        logger.warning(f"Could not determine log file: {e}")
        # Fallback to a date-based log filename
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d')
            fallback_name = f'mirror-{timestamp}.log'
            logger.info(f"Using fallback log filename after error: {fallback_name}")
            return fallback_name
        except Exception:
            logger.error("Failed to set fallback log filename")
            return "unknown.log" 