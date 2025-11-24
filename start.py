import os
import subprocess
import sys
from multiprocessing import Process

def run_webapp():
    """Run the web application"""
    port = int(os.environ.get('PORT', 5000))
    os.system(f'gunicorn webapp:app --bind 0.0.0.0:{port}')

def run_webhook():
    """Run the webhook server"""
    import webhook2
    # webhook2 will run on port 5001 internally
    webhook2.app.run(host='0.0.0.0', port=5001, debug=False)

if __name__ == '__main__':
    # Start webapp in main process (for Railway's health checks)
    port = int(os.environ.get('PORT', 5000))
    
    # Start webhook in background
    webhook_process = Process(target=run_webhook)
    webhook_process.start()
    
    print(f"🚀 Starting Web App on port {port}")
    print(f"🚀 Starting Webhook on port 5001")
    
    # Run webapp in foreground
    os.system(f'gunicorn webapp:app --bind 0.0.0.0:{port} --workers 2')