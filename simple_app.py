import os
from flask import request
import requests
import json

# Import webapp first
import webapp

# Get the Flask app from webapp
app = webapp.app

# Import necessary functions from webhook2
from webhook2 import (
    connect_db, send_message, send_interactive, get_user,
    send_language_buttons, send_registration_options,
    send_workout_logging_options, generate_web_login_token,
    send_exercises_fast,  # ✅ Add this import
    user_states
)

# Define get_exercises here
def get_exercises(muscle_group, language='en'):
    """Get exercises for a muscle group"""
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        # Use LOWER() for case-insensitive matching
        cur.execute("""
            SELECT name_en, name_es, image_url
            FROM exercises
            WHERE LOWER(muscle_group) = LOWER(%s)
            ORDER BY name_en
        """, (muscle_group,))
        
        exercises = cur.fetchall()
        
        print(f"🔍 Query: muscle_group = '{muscle_group}', Lang = '{language}', Found: {len(exercises)} exercises")
        
        cur.close()
        conn.close()
        
        # Format exercises based on language
        result = []
        for ex in exercises:
            name = ex[0] if language == 'en' else ex[1]
            result.append({
                'name': name,
                'image_url': ex[2],
                'description': ''
            })
        
        return result
        
    except Exception as e:
        print(f"❌ Error getting exercises: {e}")
        import traceback
        traceback.print_exc()
        return []

def send_exercise_images(sender, exercises, muscle_group):
    """Send exercise images synchronously"""
    import requests
    import time
    
    access_token = os.getenv('WHATSAPP_ACCESS_TOKEN')
    phone_number_id = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
    url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    print(f"📤 Sending {len(exercises)} exercise images...")
    
    for i, exercise in enumerate(exercises, 1):
        try:
            if not exercise.get('image_url'):
                print(f"⚠️ Skipping exercise {i}: No image URL")
                continue
                
            payload = {
                "messaging_product": "whatsapp",
                "to": sender,
                "type": "image",
                "image": {
                    "link": exercise['image_url'],
                    "caption": f"{i}. {exercise['name']}"
                }
            }
            
            response = requests.post(url, headers=headers, json=payload)
            
            # ✅ Show the full response for errors
            if response.status_code == 200:
                print(f"✅ Sent image {i}/{len(exercises)}: {exercise['name']}")
            else:
                print(f"❌ FAILED image {i}/{len(exercises)}: {exercise['name']}")
                print(f"   Status: {response.status_code}")
                print(f"   URL: {exercise['image_url']}")
                print(f"   Error: {response.text}")
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"❌ Exception on image {i}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"🎉 Finished sending {len(exercises)} images!")

@app.route('/webhook', methods=['GET'])
def webhook_verify():
    """Verify webhook for WhatsApp"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
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
    print("=" * 50)
    print("📩 INCOMING WEBHOOK REQUEST")
    print("=" * 50)
    
    try:
        message_entry = data["entry"][0]["changes"][0]["value"]
        
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

        # Extract text
        text = ""
        if msg_type == "text":
            text = message["text"]["body"].strip().lower()
            print(f"💬 Text received: '{text}'")

        # Get language
        lang = "en"
        if sender in user_states and "lang" in user_states[sender]:
            lang = user_states[sender]["lang"]
        elif user and user[4]:
            lang = user[4]

        # Handle greetings
        if msg_type == "text" and text in ["hi", "hello", "hola", "hey"]:
            print(f"👋 Processing greeting: '{text}'")
            user_states.pop(sender, None)
            
            if user and user[4] and user[3]:
                lang = user[4]
                user_states[sender] = {"lang": lang}
                print(f"✅ Sending registration options to existing user (lang: {lang})")
                send_registration_options(sender, lang)
            else:
                user_states[sender] = {"awaiting_language": True}
                print("✅ Sending language buttons to new user")
                send_language_buttons(sender)
            return "ok", 200

        # Handle tracker command
        if msg_type == "text" and text in ["tracker", "web", "website", "dashboard", "panel", "rastreador"]:
            token = generate_web_login_token(sender)
            
            if token:
                web_url = f"{os.getenv('WEB_APP_URL')}/login/{token}"
                
                msg = {
                    "en": f"🌐 *Access Your Workout Tracker*\n\n{web_url}\n\n⏰ Link expires in 1 hour\n\n📝 Log workouts, track progress, and view analytics!\n\n💬 Type 'hi' to start a new chat session.",
                    "es": f"🌐 *Accede a Tu Rastreador de Entrenamientos*\n\n{web_url}\n\n⏰ Enlace expira en 1 hora\n\n📝 ¡Registra entrenamientos, rastrea progreso y ve análisis!\n\n💬 Escribe 'hi' para iniciar una nueva sesión de chat."
                }
                send_message(sender, msg[lang])
                
                user_states.pop(sender, None)
            else:
                msg = {
                    "en": "❌ Error generating login link. Please try again.",
                    "es": "❌ Error generando enlace. Por favor intenta de nuevo."
                }
                send_message(sender, msg[lang])
            
            return "ok", 200

        # Handle muscle group selection
        if msg_type == "text" and user_states.get(sender, {}).get("expecting_muscle"):
            lang = user_states[sender].get("lang", "en")
            
            # Combined muscle map - accepts both languages, returns DB value based on user's lang
            muscle_translations = {
                # English inputs
                "chest": {"en": "chest", "es": "pecho"},
                "back": {"en": "back", "es": "espalda"},
                "biceps": {"en": "biceps", "es": "biceps"},
                "triceps": {"en": "triceps", "es": "triceps"},
                "shoulders": {"en": "shoulders", "es": "hombros"},
                "legs": {"en": "legs", "es": "pierna"},  # ✅ Changed to 'pierna' (singular)
                "abs": {"en": "abs", "es": "abdominales"},
                # Spanish inputs
                "pecho": {"en": "chest", "es": "pecho"},
                "espalda": {"en": "back", "es": "espalda"},
                "bíceps": {"en": "biceps", "es": "biceps"},
                "hombros": {"en": "shoulders", "es": "hombros"},
                "piernas": {"en": "legs", "es": "pierna"},  # ✅ Maps 'piernas' to 'pierna' in DB
                "pierna": {"en": "legs", "es": "pierna"},   # ✅ Also accept singular
                "abdominales": {"en": "abs", "es": "abdominales"}
            }
            
            # Get the muscle group in the database language
            muscle_info = muscle_translations.get(text)
            
            if muscle_info:
                # Use the database value based on user's language
                muscle_db_value = muscle_info[lang]
                
                print(f"🗺️ Text: '{text}', Lang: '{lang}' → DB value: '{muscle_db_value}'")
                print(f"💪 Searching for muscle group: {muscle_db_value}")
                
                exercises = get_exercises(muscle_db_value, lang)
                
                if exercises:
                    user_states[sender]["selected_muscle"] = muscle_db_value
                    user_states[sender]["expecting_muscle"] = False
                    
                    print(f"📋 Found {len(exercises)} exercises for {muscle_db_value}")
                    
                    # ✅ Use synchronous function
                    send_exercise_images(sender, exercises, muscle_db_value)
                    
                    send_workout_logging_options(sender, lang)
                else:
                    # If no exercises found, show what's actually in the database
                    try:
                        conn = connect_db()
                        cur = conn.cursor()
                        cur.execute("SELECT DISTINCT muscle_group FROM exercises ORDER BY muscle_group")
                        db_muscles = [row[0] for row in cur.fetchall()]
                        cur.close()
                        conn.close()
                        print(f"🔍 Available muscle groups in DB: {db_muscles}")
                    except Exception as e:
                        print(f"❌ Debug query failed: {e}")
                    
                    msg = {
                        "en": f"❌ No exercises found for {muscle_db_value}. Try another muscle group.",
                        "es": f"❌ No se encontraron ejercicios para {muscle_db_value}. Prueba otro grupo muscular."
                    }
                    send_message(sender, msg[lang])
            else:
                msg = {
                    "en": "❌ Invalid muscle group. Please choose: Chest, Back, Biceps, Triceps, Shoulders, Legs, or Abs",
                    "es": "❌ Grupo muscular inválido. Elige: Pecho, Espalda, Biceps, Triceps, Hombros, Piernas o Abdominales"
                }
                send_message(sender, msg[lang])
            
            return "ok", 200

        # Handle button responses
        if msg_type == "interactive":
            button_reply = message["interactive"]
            reply_id = button_reply["button_reply"]["id"]
            
            print(f"🔘 Button clicked: {reply_id}")
            
            if reply_id in ["lang_en", "lang_es"]:
                selected_lang = "en" if reply_id == "lang_en" else "es"
                user_states[sender] = {"lang": selected_lang, "awaiting_language": False}
                
                send_registration_options(sender, selected_lang)
                return "ok", 200
                
            elif reply_id == "continue":
                lang = user_states.get(sender, {}).get("lang")
                if not lang and user:
                    lang = user[4]
                    
                if not lang:
                    user_states[sender] = {"awaiting_language": True}
                    send_language_buttons(sender)
                    return "ok", 200
                
                msg = {
                    "en": "💪 Reply with a muscle group:\n- Chest\n- Back\n- Biceps\n- Triceps\n- Shoulders\n- Legs\n- Abs\n\n📊 Or type 'tracker' to log workouts",
                    "es": "💪 Responde con un grupo muscular:\n- Pecho\n- Espalda\n- Biceps\n- Triceps\n- Hombros\n- Piernas\n- Abdominales\n\n📊 O escribe 'tracker' para abrir el rastreador"
                }
                send_message(sender, msg[lang])
                user_states[sender] = {
                    "lang": lang,
                    "expecting_muscle": True
                }
                return "ok", 200
            
            # ✅ ADD THIS NEW HANDLER
            elif reply_id == "start_over":
                lang = user_states.get(sender, {}).get("lang", "en")
                if not lang and user:
                    lang = user[4]
                
                print(f"🔄 Starting over for user {sender}")
                
                # Reset user state but keep language
                user_states[sender] = {
                    "lang": lang,
                    "expecting_muscle": True
                }
                
                msg = {
                    "en": "💪 Reply with a muscle group:\n- Chest\n- Back\n- Biceps\n- Triceps\n- Shoulders\n- Legs\n- Abs\n\n📊 Or type 'tracker' to log workouts",
                    "es": "💪 Responde con un grupo muscular:\n- Pecho\n- Espalda\n- Biceps\n- Triceps\n- Hombros\n- Piernas\n- Abdominales\n\n📊 O escribe 'tracker' para abrir el rastreador"
                }
                send_message(sender, msg[lang])
                return "ok", 200
                
            elif reply_id == "view_web":
                lang = user_states.get(sender, {}).get("lang")
                if not lang and user:
                    lang = user[4]
                
                token = generate_web_login_token(sender)
                
                if token:
                    web_url = f"{os.getenv('WEB_APP_URL')}/login/{token}"
                    
                    msg = {
                        "en": f"🌐 *Access Your Workout Tracker*\n\n{web_url}\n\n⏰ Link expires in 1 hour\n\n📊 View history, analytics, and personal records!\n\n💬 Type 'hi' to start a new chat session.",
                        "es": f"🌐 *Accede a Tu Rastreador*\n\n{web_url}\n\n⏰ Enlace expira en 1 hora\n\n📊 ¡Ve historial, análisis y récords personales!\n\n💬 Escribe 'hi' para iniciar una nueva sesión de chat."
                    }
                    send_message(sender, msg[lang])
                    
                    user_states.pop(sender, None)
                else:
                    msg = {
                        "en": "❌ Error generating login link. Please try again.",
                        "es": "❌ Error generando enlace. Por favor intenta de nuevo."
                    }
                    send_message(sender, msg[lang])
                
                return "ok", 200

        return "ok", 200
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        import traceback
        traceback.print_exc()
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