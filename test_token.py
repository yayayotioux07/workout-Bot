from webhook2 import generate_web_login_token, connect_db

# Test token generation
test_wa_id = "666580599871427"  # Replace with your WhatsApp number
token = generate_web_login_token(test_wa_id)

if token:
    print(f"✅ Token generated: {token}")
    print(f"🔗 Test URL: http://localhost:5001/login/{token}")
    
    # Verify in database
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM login_tokens WHERE token = %s", (token,))
    result = cur.fetchone()
    print(f"📊 Database entry: {result}")
    cur.close()
    conn.close()
else:
    print("❌ Token generation failed")