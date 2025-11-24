import os
from flask import request

# Import webapp first
import webapp

# Get the Flask app from webapp
app = webapp.app

# Now we need to manually add webhook routes
# Import the necessary functions from webhook2
from webhook2 import connect_db, send_message, get_user, user_states
import json

@app.route('/webhook', methods=['GET'])
def webhook_verify():
    """Verify webhook for WhatsApp"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    print("=" * 50)
    print("🔍 WEBHOOK VERIFICATION REQUEST")
    print(f"Mode: {mode}")
    print(f"Token: {token}")
    print(f"Challenge: {challenge}")
    print("=" * 50)
    
    verify_token = os.getenv('WHATSAPP_VERIFY_TOKEN', 'fitbuddy_verify')
    
    if mode == 'subscribe' and token == verify_token:
        print("✅ Webhook verified!")
        return challenge, 200
    else:
        print("❌ Webhook verification failed")
        return "Forbidden", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming WhatsApp messages"""
    data = request.get_json()
    print("📩 Received webhook POST")
    print(json.dumps(data, indent=2))
    
    # For now, just acknowledge receipt
    # You can add your webhook2.py logic here later
    return "ok", 200

# Health check
@app.route('/health')
def health():
    return {"status": "healthy"}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print("=" * 50)
    print(f"🚀 Starting Combined App on port {port}")
    print(f"📍 Webhook GET: /webhook")
    print(f"📍 Webhook POST: /webhook")
    print(f"📍 Dashboard: /dashboard")
    print(f"📍 Health: /health")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)