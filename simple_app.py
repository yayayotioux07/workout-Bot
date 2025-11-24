import os
from flask import Flask
from flask_cors import CORS

# Import the actual Flask apps
import webhook2
import webapp

# Use webapp's app as the base (it has sessions configured)
app = webapp.app

# Add CORS
CORS(app)

# Add webhook routes from webhook2
app.add_url_rule('/webhook', 'webhook_get', webhook2.webhook_verify, methods=['GET'])
app.add_url_rule('/webhook', 'webhook_post', webhook2.webhook, methods=['POST'])

# webapp routes are already in webapp.app, so they're automatically included

# Health check
@app.route('/health')
def health():
    return {"status": "healthy"}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print("=" * 50)
    print(f"🚀 Starting Combined App on port {port}")
    print(f"📍 Webhook: /webhook")
    print(f"📍 Dashboard: /dashboard")
    print(f"📍 Health: /health")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False)