import os
from webhook import app
from waitress import serve
import logging
from logging.handlers import RotatingFileHandler
from time import strftime
import sys

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(
    '[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))

# Configure file handler with UTF-8 encoding
file_handler = RotatingFileHandler(
    'logs/server.log',
    maxBytes=10000000,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    '[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))

# Set up root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler]
)

# Server configuration
SERVER_CONFIG = {
    'host': '0.0.0.0',  # Listen on all available interfaces
    'port': 5000,
    'threads': 4,  # Number of worker threads
    'connection_limit': 1000,
    'cleanup_interval': 30,
    'channel_timeout': 300
}

if __name__ == '__main__':
    try:
        logging.info('Starting WhatsApp Workout Bot Server...')
        logging.info(f'Server Configuration: {SERVER_CONFIG}')
        
        serve(
            app,
            host=SERVER_CONFIG['host'],
            port=SERVER_CONFIG['port'],
            threads=SERVER_CONFIG['threads'],
            connection_limit=SERVER_CONFIG['connection_limit'],
            cleanup_interval=SERVER_CONFIG['cleanup_interval'],
            channel_timeout=SERVER_CONFIG['channel_timeout'],
        )
    except Exception as e:
        logging.error(f'Server error: {e}')
        sys.exit(1)
