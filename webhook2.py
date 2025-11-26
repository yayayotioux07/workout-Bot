from flask import Flask, request
import requests
import psycopg2
import threading
import time
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import os
from dotenv import load_dotenv
import json
import secrets  # Make sure this line exists

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Use environment variables instead of hardcoded values
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT")

user_states = {}

def connect_db():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
        port=DB_PORT
    )

def send_message(to, text):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    print("➡️ Sending text:", json.dumps(payload, indent=2))
    resp = requests.post(url, headers=headers, json=payload)
    print("⬅️ WhatsApp API response:", resp.status_code, resp.text)


def send_image(to, image_url, caption):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }
    print("➡️ Sending image:", json.dumps(payload, indent=2))
    resp = requests.post(url, headers=headers, json=payload)
    print("⬅️ WhatsApp API response:", resp.status_code, resp.text)


def send_interactive(payload):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    print("➡️ Sending interactive:", json.dumps(payload, indent=2))
    resp = requests.post(url, headers=headers, json=payload)
    print("⬅️ WhatsApp API response:", resp.status_code, resp.text)


def send_language_buttons(to):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "🌐 Please choose your language:"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "lang_en", "title": "English"}},
                    {"type": "reply", "reply": {"id": "lang_es", "title": "Español"}}
                ]
            }
        }
    }
    send_interactive(payload)

def send_registration_options(to, lang):
    """Send main menu after user is already registered"""
    text = {
        "en": "Welcome back! 👋",
        "es": "¡Bienvenido de nuevo! 👋"
    }
    send_message(to, text[lang])
    # Show main menu
    send_workout_logging_options(to, lang)

def send_reset_options(to, lang):
    text = {
        "en": "Would you like to Start Over or Log Out?",
        "es": "¿Quieres empezar de nuevo o cerrar sesión?"
    }
    
    buttons = {
        "en": [
            {"type": "reply", "reply": {"id": "start_over", "title": "Start Over"}},
            {"type": "reply", "reply": {"id": "log_out", "title": "Log Out Session"}}
        ],
        "es": [
            {"type": "reply", "reply": {"id": "start_over", "title": "Empezar de Nuevo"}},
            {"type": "reply", "reply": {"id": "log_out", "title": "Cerrar Sesión"}}
        ]
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text[lang]},
            "action": {
                "buttons": buttons[lang]
            }
        }
    }
    send_interactive(payload)

def get_user(wa_id):
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT wa_id, name, email, registered, language FROM users WHERE wa_id = %s", (wa_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return user
    except Exception as e:
        print(f"❌ DB error in get_user: {e}")
        import traceback
        traceback.print_exc()  # Print full error trace
        return None

def save_user(wa_id, name=None, email=None, registered=False, language=None):
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT wa_id FROM users WHERE wa_id = %s", (wa_id,))
        if cur.fetchone():
            cur.execute("UPDATE users SET name=%s, email=%s, registered=%s, language=%s WHERE wa_id=%s",
                        (name, email, registered, language, wa_id))
        else:
            cur.execute("INSERT INTO users (wa_id, name, email, registered, language) VALUES (%s, %s, %s, %s, %s)",
                        (wa_id, name, email, registered, language))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("❌ DB error:", e)

def get_exercises_by_muscle(muscle_group, lang):
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT name_en, name_es, equipment, image_url, gif_url FROM exercises 
            WHERE LOWER(muscle_group) = LOWER(%s)
            ORDER BY name_en
        """, (muscle_group,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print("❌ Exercise query error:", e)
        return []

def generate_web_login_token(wa_id):
    """Generate a secure token for web login"""
    token = secrets.token_urlsafe(32)
    expiry_timestamp = int(time.time()) + 3600  # 1 hour
    
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        # Create table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS login_tokens (
                token VARCHAR(64) PRIMARY KEY,
                wa_id VARCHAR(20) NOT NULL,
                expires_at INTEGER NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Clean up old expired tokens
        current_time = int(time.time())
        cur.execute("""
            DELETE FROM login_tokens 
            WHERE expires_at < %s OR (used = TRUE AND created_at < NOW() - INTERVAL '7 days')
        """, (current_time,))
        
        # Insert new token
        cur.execute("""
            INSERT INTO login_tokens (token, wa_id, expires_at)
            VALUES (%s, %s, %s)
        """, (token, wa_id, expiry_timestamp))
        
        conn.commit()
        
        print(f"✅ Token generated for {wa_id}: {token[:10]}...")
        
        cur.close()
        conn.close()
        
        return token
        
    except Exception as e:
        print(f"❌ Error generating token: {e}")
        import traceback
        traceback.print_exc()
        return None

async def send_image_async(session, to, image_url, caption):
    """Send image using aiohttp"""
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }
    
    try:
        async with session.post(url, headers=headers, json=payload) as response:
            return response.status == 200
    except Exception as e:
        print(f"❌ Error sending image: {e}")
        return False

def send_workout_logging_options(to, lang):
    """Send main menu options"""
    text = {
        "en": "💪 What would you like to do?\n\nType 'logout' anytime to end your session.",
        "es": "💪 ¿Qué te gustaría hacer?\n\nEscribe 'logout' en cualquier momento para cerrar sesión."
    }
    
    buttons = {
        "en": [
            {"type": "reply", "reply": {"id": "view_exercises", "title": "View Exercises"}},
            {"type": "reply", "reply": {"id": "view_web", "title": "Open Dashboard"}},
            {"type": "reply", "reply": {"id": "reregister", "title": "Re-Register"}}
        ],
        "es": [
            {"type": "reply", "reply": {"id": "view_exercises", "title": "Ver Ejercicios"}},
            {"type": "reply", "reply": {"id": "view_web", "title": "Abrir Dashboard"}},
            {"type": "reply", "reply": {"id": "reregister", "title": "Re-Registrarse"}}
        ]
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text[lang]},
            "action": {
                "buttons": buttons[lang]
            }
        }
    }
    send_interactive(payload)

async def send_exercises_async(sender, rows, lang):
    """Send exercises asynchronously with GIF links - SEQUENTIAL VERSION"""
    async with aiohttp.ClientSession() as session:
        sent_images = set()
        success_count = 0
        
        for row in rows:
            # Check if user is still logged in
            if sender not in user_states:
                print(f"⚠️ User {sender} logged out, stopping exercise sending")
                return
            
            # Handle both 4 and 5 column formats
            if len(row) == 5:
                name_en, name_es, equipment, image_url, gif_url = row
            else:
                name_en, name_es, equipment, image_url = row
                gif_url = None
                
            if image_url not in sent_images:
                name = name_en if lang == "en" else name_es
                
                # Create caption with proper format
                if gif_url:
                    gif_text = {
                        "en": "Animated GIF",
                        "es": "GIF Animado"
                    }
                    caption = f"{name}\nEquipment: {equipment}\n{gif_text[lang]}: {gif_url}"
                else:
                    caption = f"{name}\nEquipment: {equipment}"
                
                # Send image and WAIT for it to complete
                result = await send_image_async(session, sender, image_url, caption)
                if result:
                    success_count += 1
                    
                sent_images.add(image_url)
                
                # Delay between each image to avoid rate limits
                await asyncio.sleep(0.5)  # Half second between each
        
        print(f"✅ Sent {success_count}/{len(sent_images)} exercises")
        
        # Only send logging options if user is still logged in
        if sender in user_states:
            # Small delay before buttons
            await asyncio.sleep(1.0)
            send_workout_logging_options(sender, lang)  # CHANGED THIS LINE

def send_exercises_with_async(sender, rows, lang):
    """Wrapper to run async function in thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(send_exercises_async(sender, rows, lang))
    finally:
        loop.close()

def send_exercises_with_delay(sender, rows, lang):
    """Send exercises with proper delays and then send reset options"""
    sent_images = set()
    for row in rows:
        if len(row) == 5:
            name_en, name_es, equipment, image_url, gif_url = row
        else:
            name_en, name_es, equipment, image_url = row
            gif_url = None
            
        if image_url not in sent_images:
            try:
                name = name_en if lang == "en" else name_es
                
                # Create caption with proper format
                if gif_url:
                    gif_text = {
                        "en": "Animated GIF",
                        "es": "GIF Animado"
                    }
                    caption = f"{name}\nEquipment: {equipment}\n{gif_text[lang]}: {gif_url}"
                else:
                    caption = f"{name}\nEquipment: {equipment}"
                
                send_image(sender, image_url, caption)
                sent_images.add(image_url)
                time.sleep(2)  # Delay between each image
            except Exception as e:
                print(f"❌ Error sending exercise: {e}")
    
    # Send reset options after all images
    time.sleep(1)
    send_reset_options(sender, lang)

# Create a global session and thread pool
session = None
executor = ThreadPoolExecutor(max_workers=5)

async def init_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()

async def send_exercises_fast(sender, rows, lang):
    """Ultra-fast exercise sending with pre-initialized session"""
    global session
    
    # Ensure session is ready
    await init_session()
    
    sent_images = set()
    tasks = []
    
    for row in rows:
        # Check if user is still logged in
        if sender not in user_states:
            return
        
        # Handle both 4 and 5 column formats
        if len(row) == 5:
            name_en, name_es, equipment, image_url, gif_url = row
        else:
            name_en, name_es, equipment, image_url = row
            gif_url = None
            
        if image_url not in sent_images:
            name = name_en if lang == "en" else name_es
            
            # Create caption with proper format
            if gif_url:
                gif_text = {
                    "en": "Animated GIF",
                    "es": "GIF Animado"
                }
                caption = f"{name}\nEquipment: {equipment}\n{gif_text[lang]}: {gif_url}"
            else:
                caption = f"{name}\nEquipment: {equipment}"
            
            # Create task immediately
            task = send_image_async(session, sender, image_url, caption)
            tasks.append(task)
            sent_images.add(image_url)
    
    # Send all images simultaneously
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for result in results if result is True)
        print(f"✅ Sent {success_count}/{len(tasks)} exercises")
    
    # Send reset options
    if sender in user_states:
        await asyncio.sleep(0.1)
        send_reset_options(sender, lang)

def send_exercises_ultra_fast(sender, rows, lang):
    """Ultra-fast wrapper using existing event loop if possible"""
    try:
        # Try to use existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule on existing loop
            asyncio.create_task(send_exercises_fast(sender, rows, lang))
        else:
            loop.run_until_complete(send_exercises_fast(sender, rows, lang))
    except RuntimeError:
        # No event loop, create new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(send_exercises_fast(sender, rows, lang))
        finally:
            loop.close()

@app.route('/webhook', methods=['GET'])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Unauthorized", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print("=" * 50)
    print("📩 INCOMING WEBHOOK REQUEST")
    print("=" * 50)
    print("Full data:", json.dumps(data, indent=2))
    print("=" * 50)

    try:
        message_entry = data["entry"][0]["changes"][0]["value"]
        
        # Check if this is a status update (not an actual message)
        if "statuses" in message_entry:
            print("📊 Status update received, ignoring...")
            return "ok", 200
            
        if "messages" not in message_entry:
            print("⚠️ No messages in entry")
            return "ok", 200

        message = message_entry["messages"][0]
        sender = message["from"]
        msg_type = message["type"]
        
        print(f"👤 Sender: {sender}, Type: {msg_type}")
        
        user = get_user(sender)
        print(f"📊 User data: {user}")

        # Extract text early
        text = ""
        if msg_type == "text":
            text = message["text"]["body"].strip().lower()
            print(f"💬 Text received: '{text}'")

        # Handle greetings FIRST
        if msg_type == "text" and text in ["hi", "hello", "hola", "hey"]:
            print(f"👋 Processing greeting: '{text}'")
            user_states.pop(sender, None)
            
            if user and user[4] and user[3]:  # Has language and is registered
                lang = user[4]
                user_states[sender] = {"lang": lang}
                print(f"✅ Sending registration options to existing user (lang: {lang})")
                send_registration_options(sender, lang)
            else:  # New user or no language preference
                user_states[sender] = {"awaiting_language": True}
                print("✅ Sending language buttons to new user")
                send_language_buttons(sender)
            return "ok", 200

        # Handle interactive messages
        if msg_type == "interactive":
            # Handle both button replies and list replies
            if "button_reply" in message["interactive"]:
                reply_id = message["interactive"]["button_reply"]["id"]
            elif "list_reply" in message["interactive"]:
                reply_id = message["interactive"]["list_reply"]["id"]
            else:
                return "ok", 200
            
            print(f"🔘 Interactive reply: {reply_id}")

            if reply_id.startswith("lang_"):
                lang = reply_id[-2:]
                save_user(sender, language=lang)
                user_states[sender] = {
                    "lang": lang,
                    "step": "name"
                }
                send_message(sender, "📝 What's your name?" if lang == "en" else "📝 ¿Cuál es tu nombre?")
                return "ok", 200

            elif reply_id == "re_register":
                user_states[sender] = {"awaiting_language": True}
                send_language_buttons(sender)
                return "ok", 200

            # ADD THESE NEW HANDLERS
            elif reply_id == "log_workout":
                lang = user_states.get(sender, {}).get("lang")
                if not lang and user:
                    lang = user[4]
                
                # Generate web token instead of asking for text input
                token = generate_web_login_token(sender)
                
                if token:
                    web_url = f"{os.getenv('WEB_APP_URL', 'http://localhost:5001')}/login/{token}"
                    
                    msg = {
                        "en": f"🌐 *Log Your Workout*\n\n{web_url}\n\n⏰ Link expires in 1 hour\n\n📝 Track sets, reps, weight, and view your progress!",
                        "es": f"🌐 *Registra Tu Entrenamiento*\n\n{web_url}\n\n⏰ Enlace expira en 1 hora\n\n📝 ¡Rastrea series, reps, peso y ve tu progreso!"
                    }
                    send_message(sender, msg[lang])
                else:
                    msg = {
                        "en": "❌ Error generating login link. Please try again.",
                        "es": "❌ Error generando enlace. Por favor intenta de nuevo."
                    }
                    send_message(sender, msg[lang])
                
                return "ok", 200

            elif reply_id == "view_web":
                lang = user_states.get(sender, {}).get("lang")
                if not lang and user:
                    lang = user[4]
                
                token = generate_web_login_token(sender)
                
                if token:
                    web_url = f"{os.getenv('WEB_APP_URL', 'http://localhost:5001')}/login/{token}"
                    
                    msg = {
                        "en": f"🌐 *Access Your Workout Tracker*\n\n{web_url}\n\n⏰ Link expires in 1 hour\n\n📊 View history, analytics, and personal records!\n\n💬 Type 'hi' to start a new chat session.",
                        "es": f"🌐 *Accede a Tu Rastreador*\n\n{web_url}\n\n⏰ Enlace expira en 1 hora\n\n📊 ¡Ve historial, análisis y récords personales!\n\n💬 Escribe 'hi' para iniciar una nueva sesión de chat."
                    }
                    send_message(sender, msg[lang])
                    
                    # LOG OUT THE BOT SESSION - Clear user state
                    user_states.pop(sender, None)
                    print(f"🚪 User {sender} logged out of bot session after requesting tracker")
                else:
                    msg = {
                        "en": "❌ Error generating login link. Please try again.",
                        "es": "❌ Error generando enlace. Por favor intenta de nuevo."
                    }
                    send_message(sender, msg[lang])
                
                return "ok", 200

            elif reply_id == "log_out":
                lang = user_states.get(sender, {}).get("lang", "en")
                msg = {
                    "en": "👋 Logged out successfully! Type 'hi' anytime to start again.",
                    "es": "👋 ¡Sesión cerrada exitosamente! Escribe 'hi' en cualquier momento para empezar de nuevo."
                }
                send_message(sender, msg[lang])
                user_states.pop(sender, None)
                return "ok", 200
            
            elif reply_id == "reregister":
                lang = user_states.get(sender, {}).get("lang")
                if not lang and user:
                    lang = user[4]
                
                # Reset user state for re-registration
                user_states[sender] = {
                    "lang": lang,
                    "step": "name"
                }
                
                msg = {
                    "en": "Let's update your information! 📝\n\nWhat's your name?",
                    "es": "¡Actualicemos tu información! 📝\n\n¿Cuál es tu nombre?"
                }
                send_message(sender, msg[lang])
                return "ok", 200
            
            elif reply_id == "view_exercises":
                lang = user_states.get(sender, {}).get("lang")
                if not lang and user:
                    lang = user[4]
                
                # Set state to expecting muscle group selection
                user_states[sender] = {
                    "lang": lang,
                    "expecting_muscle": True
                }
                
                # Send muscle group selection
                text = {
                    "en": "💪 Choose a muscle group to view exercises:\n\n• Chest\n• Back\n• Biceps\n• Triceps\n• Shoulders\n• Legs\n• Abs",
                    "es": "💪 Elige un grupo muscular para ver ejercicios:\n\n• Pecho\n• Espalda\n• Bíceps\n• Tríceps\n• Hombros\n• Piernas\n• Abdominales"
                }
                send_message(sender, text[lang])
                return "ok", 200

        # Initialize user state for new users
        if sender not in user_states:
            print("⚠️ User not in states, initializing...")
            if user and user[4]:  # Has language set
                user_states[sender] = {
                    "lang": user[4],
                    "registered": user[3]
                }
                send_registration_options(sender, user[4])
            else:
                user_states[sender] = {"awaiting_language": True}
                send_language_buttons(sender)
            return "ok", 200

        # Handle registration steps - MOVED OUTSIDE the previous block
        if msg_type == "text" and "step" in user_states[sender]:
            lang = user_states[sender].get("lang")
            
            if user_states[sender]["step"] == "name":
                user_states[sender]["name"] = text
                user_states[sender]["step"] = "email"
                send_message(sender, "📧 What's your email?" if lang == "en" else "📧 ¿Cuál es tu correo electrónico?")
                return "ok", 200
                
            elif user_states[sender]["step"] == "email":
                name = user_states[sender].get("name")
                save_user(sender, name=name, email=text, registered=True, language=lang)
                
                text_msg = {
                    "en": "✅ You're registered!\n\n💪 Choose a muscle group:\n- Chest\n- Back\n- Biceps\n- Triceps\n- Shoulders\n- Legs\n- Abs",
                    "es": "✅ ¡Estás registrado!\n\n💪 Elige un grupo muscular:\n- Pecho\n- Espalda\n- Biceps\n- Triceps\n- Hombros\n- Piernas\n- Abdominales"
                }
                
                buttons = {
                    "en": [
                        {"type": "reply", "reply": {"id": "view_web", "title": "Open Tracker"}}
                    ],
                    "es": [
                        {"type": "reply", "reply": {"id": "view_web", "title": "Abrir Tracker"}}
                    ]
                }
                
                payload = {
                    "messaging_product": "whatsapp",
                    "to": sender,
                    "type": "interactive",
                    "interactive": {
                        "type": "button",
                        "body": {"text": text_msg[lang]},
                        "action": {
                            "buttons": buttons[lang]
                        }
                    }
                }
                send_interactive(payload)
                
                user_states[sender] = {
                    "lang": lang,
                    "expecting_muscle": True,
                    "registered": True
                }
                return "ok", 200

        # Handle logout command via text
        if msg_type == "text" and text.lower() in ["logout", "log out", "salir", "cerrar sesión", "cerrar sesion"]:
            lang = user_states.get(sender, {}).get("lang", "en")
            msg = {
                "en": "👋 Logged out successfully! Type 'hi' anytime to start again.",
                "es": "👋 ¡Sesión cerrada exitosamente! Escribe 'hi' en cualquier momento para empezar de nuevo."
            }
            send_message(sender, msg[lang])
            user_states.pop(sender, None)
            return "ok", 200

        # Handle muscle group selection - MOVED OUTSIDE and changed to if
        if msg_type == "text" and user_states[sender].get("expecting_muscle"):
            lang = user_states[sender].get("lang")
            print(f"🏋️ Processing muscle group: '{text}' in language: {lang}")
            
            # ADD THIS: Check for tracker command
            if text in ["tracker", "web", "website", "dashboard", "panel", "rastreador"]:
                token = generate_web_login_token(sender)
                
                if token:
                    web_url = f"{os.getenv('WEB_APP_URL', 'http://localhost:5001')}/login/{token}"
                    
                    msg = {
                        "en": f"🌐 *Access Your Workout Tracker*\n\n{web_url}\n\n⏰ Link expires in 1 hour\n\n📝 Log workouts, track progress, and view analytics!\n\n💬 Type 'hi' to start a new chat session.",
                        "es": f"🌐 *Accede a Tu Rastreador de Entrenamientos*\n\n{web_url}\n\n⏰ Enlace expira en 1 hora\n\n📝 ¡Registra entrenamientos, rastrea progreso y ve análisis!\n\n💬 Escribe 'hi' para iniciar una nueva sesión de chat."
                    }
                    send_message(sender, msg[lang])
                    
                    # LOG OUT THE BOT SESSION - Clear user state
                    user_states.pop(sender, None)
                    print(f"🚪 User {sender} logged out of bot session after requesting tracker")
                else:
                    msg = {
                        "en": "❌ Error generating login link. Please try again.",
                        "es": "❌ Error generando enlace. Por favor intenta de nuevo."
                    }
                    send_message(sender, msg[lang])
                
                return "ok", 200
            
            muscle_groups = {
                "en": ["chest", "back", "biceps", "triceps", "shoulders", "legs", "abs"],
                "es": ["pecho", "espalda", "biceps", "triceps", "hombros", "piernas", "abdominales"]
            }
            
            muscle_mapping = {
                "pecho": "chest",
                "espalda": "back", 
                "hombros": "shoulders",
                "piernas": "legs",
                "abdominales": "abs"
            }
            
            if text in muscle_groups[lang]:
                db_muscle = muscle_mapping.get(text, text)
                print(f"🔍 Searching database for: {db_muscle}")
                rows = get_exercises_by_muscle(db_muscle, lang)
                
                if rows:
                    print(f"✅ Found {len(rows)} exercises")
                    thread = threading.Thread(target=send_exercises_with_async, args=(sender, rows, lang))
                    thread.start()
                    
                    msg = {
                        "en": f"📦 Sending {len(rows)} exercises for {text.capitalize()}...",
                        "es": f"📦 Enviando {len(rows)} ejercicios para {text.capitalize()}..."
                    }
                    send_message(sender, msg[lang])
                else:
                    print("❌ No exercises found")
                    msg = {
                        "en": "❌ No exercises found for that muscle group.",
                        "es": "❌ No se encontraron ejercicios para ese grupo muscular."
                    }
                    send_message(sender, msg[lang])
                    send_reset_options(sender, lang)
            else:
                print(f"❌ Invalid input: '{text}'")
                msg = {
                    "en": "❌ Please choose:\n• Muscle group (chest, back, biceps, triceps, shoulders, legs, abs)\n• 'tracker' - Open workout tracker",
                    "es": "❌ Por favor elige:\n• Grupo muscular (pecho, espalda, biceps, triceps, hombros, piernas, abdominales)\n• 'tracker' - Abrir rastreador"
                }
                send_message(sender, msg[lang])
            return "ok", 200

    except Exception as e:
        print(f"❌ Error in webhook: {e}")
        import traceback
        traceback.print_exc()

    return "ok", 200

def validate_token():
    """Validate WhatsApp access token on startup"""
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print("✅ WhatsApp token is valid")
            return True
        else:
            print(f"❌ Invalid token: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error validating token: {e}")
        return False

# Validate on startup