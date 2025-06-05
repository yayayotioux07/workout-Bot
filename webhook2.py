from flask import Flask, request
import requests
import psycopg2

app = Flask(__name__)

ACCESS_TOKEN = "EAAlZAL7lHsgwBOxNHV4R2bcXDjSzoK7vzjT78JZBZBTGWafb4bQdeZCNmjZCudreZAn5YhcnjV19824KKcI74IMuXIURmnNqslHPNYVZAwB9rgYKNOuBHThcKfFeL3LcYZC64JlqvwQUpqUiCENrRZBjVrm1bZBlcLg2nVYMgdp7QYAz8afoyD3UCGWaCWTcejOZBQZB89BFbXBZB4rdt19A27bggHFIgZC9HPZB82CABkZD"
PHONE_NUMBER_ID = "666580599871427"
VERIFY_TOKEN = "fitbuddy_verify"

DB_HOST = "aws-0-us-west-1.pooler.supabase.com"
DB_NAME = "postgres"
DB_USER = "postgres.tbhkoezbwkzwvgaibspw"
DB_PASSWORD = "Key25one!38"
DB_PORT = "5432"

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
    requests.post(url, headers=headers, json=payload)

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
    requests.post(url, headers=headers, json=payload)

def send_interactive(payload):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    requests.post(url, headers=headers, json=payload)

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
    text = {
        "en": "You're already registered. Would you like to re-register or continue with workouts?",
        "es": "Ya estás registrado. ¿Deseas volver a registrar o continuar con entrenamientos?"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text[lang]},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "re_register", "title": "Re-register"}},
                    {"type": "reply", "reply": {"id": "continue", "title": "Continue"}}
                ]
            }
        }
    }
    send_interactive(payload)

def send_reset_options(to, lang):
    text = {
        "en": "Would you like to Start Over or Log Out?",
        "es": "¿Quieres empezar de nuevo o cerrar sesión?"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text[lang]},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "start_over", "title": "Start Over"}},
                    {"type": "reply", "reply": {"id": "log_out", "title": "Log Out Session"}}
                ]
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
        print("❌ DB error:", e)
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
            SELECT name_en, name_es, equipment, image_url FROM exercises 
            WHERE LOWER(muscle_group) = LOWER(%s)
            ORDER BY name_en  -- Add ordering to get consistent results
        """, (muscle_group,))  # Removed language filter to get all exercises
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print("❌ Exercise query error:", e)
        return []

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
    print("📩 New message received:", data)

    try:
        message_entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in message_entry:
            return "ok", 200

        message = message_entry["messages"][0]
        sender = message["from"]
        msg_type = message["type"]
        user = get_user(sender)

        # Reset if new session or greeting
        if msg_type == "text":
            text = message["text"]["body"].strip().lower()
            if text in ["hi", "hello", "hola", "hey"]:
                # Clear existing state for new session
                user_states.pop(sender, None)
                
                # Check if user exists and has language
                if user and user[4] and user[3]:  # Has language and is registered
                    lang = user[4]
                    user_states[sender] = {"lang": lang}
                    send_registration_options(sender, lang)
                else:  # New user or no language preference
                    user_states[sender] = {"awaiting_language": True}
                    send_language_buttons(sender)
                return "ok", 200

        # Initialize user state if new user
        if sender not in user_states:
            user = get_user(sender)
            if user and user[4] and not user_states.get(sender, {}).get("awaiting_language"):  # Check awaiting_language
                user_states[sender] = {
                    "lang": user[4],
                    "registered": user[3]
                }
            else:  # New user or awaiting language selection
                if not user_states.get(sender, {}).get("awaiting_language"):  # Only send if not already awaiting
                    user_states[sender] = {"awaiting_language": True}
                    send_language_buttons(sender)
                return "ok", 200

        # Handle interactive messages
        if msg_type == "interactive":
            reply_id = message["interactive"]["button_reply"]["id"]

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
                # Clear existing state and set awaiting_language
                user_states[sender] = {"awaiting_language": True}
                send_language_buttons(sender)
                return "ok", 200

            elif reply_id == "continue":
                # Get language from user state
                lang = user_states[sender].get("lang")
                if not lang:  # Fallback if language not set
                    user_states[sender] = {"awaiting_language": True}
                    send_language_buttons(sender)
                    return "ok", 200
                
                msg = {
                    "en": "💪 Reply with a muscle group:\n- Chest\n- Back\n- Arms\n- Shoulders\n- Legs\n- Abdomen",
                    "es": "💪 Responde con un grupo muscular:\n- Pecho\n- Espalda\n- Brazos\n- Hombros\n- Piernas\n- Abdomen"
                }
                send_message(sender, msg[lang])
                user_states[sender]["expecting_muscle"] = True
                return "ok", 200

            elif reply_id == "start_over":
                # Get language from user state
                lang = user_states[sender].get("lang")
                if not lang:  # Fallback if language not set
                    user_states[sender] = {"awaiting_language": True}
                    send_language_buttons(sender)
                    return "ok", 200
                
                msg = {
                    "en": "💪 Reply with a muscle group:\n- Chest\n- Back\n- Arms\n- Shoulders\n- Legs\n- Abdomen",
                    "es": "💪 Responde con un grupo muscular:\n- Pecho\n- Espalda\n- Brazos\n- Hombros\n- Piernas\n- Abdomen"
                }
                send_message(sender, msg[lang])
                user_states[sender]["expecting_muscle"] = True
                return "ok", 200

            elif reply_id == "log_out":
                send_message(sender, "👋 Have a good one.")
                user_states.pop(sender, None)

            return "ok", 200

        # Handle text messages
        if msg_type == "text":
            text = message["text"]["body"].strip().lower()
            if "step" in user_states[sender]:
                # Get language from user state
                lang = user_states[sender].get("lang")
                if not lang:
                    send_language_buttons(sender)
                    return "ok", 200
                    
                if user_states[sender]["step"] == "name":
                    user_states[sender]["name"] = text
                    user_states[sender]["step"] = "email"
                    send_message(sender, "📧 What's your email?" if lang == "en" else "📧 ¿Cuál es tu correo electrónico?")
                elif user_states[sender]["step"] == "email":
                    name = user_states[sender].get("name")
                    save_user(sender, name=name, email=text, registered=True, language=lang)
                    
                    # Send registration confirmation with muscle groups
                    msg = {
                        "en": "✅ You're registered!\n\n💪 Choose a muscle group:\n- Chest\n- Back\n- Arms\n- Shoulders\n- Legs\n- Abdomen",
                        "es": "✅ ¡Estás registrado!\n\n💪 Elige un grupo muscular:\n- Pecho\n- Espalda\n- Brazos\n- Hombros\n- Piernas\n- Abdomen"
                    }
                    send_message(sender, msg[lang])
                    
                    # Update user state to expect muscle input
                    user_states[sender] = {
                        "lang": lang,
                        "expecting_muscle": True
                    }
                    # Remove send_reset_options here to wait for muscle group input
                    user_states[sender].pop("step", None)

            elif user_states[sender].get("expecting_muscle"):
                # Get language from user state
                lang = user_states[sender].get("lang")
                if not lang:
                    send_language_buttons(sender)
                    return "ok", 200

                muscle_groups = {
                    "en": ["chest", "back", "arms", "shoulders", "legs", "abdomen"],
                    "es": ["pecho", "espalda", "brazos", "hombros", "piernas", "abdomen"]
                }
                
                if text in muscle_groups[lang]:  # Use lang instead of user_states[sender]["lang"]
                    rows = get_exercises_by_muscle(text, lang)
                    if rows:
                        # First send all exercise images
                        for name_en, name_es, equipment, image_url in rows:
                            try:
                                name = name_en if lang == "en" else name_es
                                caption = f"{name}\nEquipment: {equipment}"
                                send_image(sender, image_url, caption)
                            except Exception as e:
                                print(f"❌ Error sending exercise: {e}")
                        
                        # Only after all images are sent, show reset options
                        send_reset_options(sender, lang)
                    else:
                        msg = {
                            "en": "❌ No exercises found for that muscle group.",
                            "es": "❌ No se encontraron ejercicios para ese grupo muscular."
                        }
                        send_message(sender, msg[lang])
                        send_reset_options(sender, lang)
                else:
                    msg = {
                        "en": "❌ Invalid muscle group. Please choose from:\n- Chest\n- Back\n- Arms\n- Shoulders\n- Legs\n- Abdomen",
                        "es": "❌ Grupo muscular inválido. Por favor elige de:\n- Pecho\n- Espalda\n- Brazos\n- Hombros\n- Piernas\n- Abdomen"
                    }
                    send_message(sender, msg[lang])
                return "ok", 200

    except Exception as e:
        print("❌ Error:", e)

    return "ok", 200

if __name__ == "__main__":
    app.run(port=5000)
