"""
Combined Flask app that handles both webhook and web interface
"""
import os
from flask import Flask, request, session, redirect, url_for, jsonify
from flask_cors import CORS
import psycopg2
import time
import secrets

# Import ONLY what exists in webhook2
from webhook2 import (
    connect_db, 
    send_message, 
    send_interactive, 
    get_user,
    send_language_buttons, 
    send_registration_options,
    send_exercise_list, 
    send_workout_logging_options,
    save_workout, 
    check_and_update_pr, 
    generate_web_login_token,
    user_states
)

# Import from webapp
from webapp import (
    render_home, 
    render_error, 
    render_dashboard, 
    render_exercises,
    get_exercises  # ✅ This is in webapp.py, not webhook2.py
)

# Create Flask app
app = Flask(__name__)
CORS(app)
app.secret_key = os.urandom(24)

# ========================================
# WEBHOOK ROUTES (from webhook2.py)
# ========================================

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

        # Extract text early
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

        # Handle greetings FIRST
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
                print(f"🚪 User {sender} logged out of bot session after requesting tracker")
            else:
                msg = {
                    "en": "❌ Error generating login link. Please try again.",
                    "es": "❌ Error generando enlace. Por favor intenta de nuevo."
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
                    print(f"🚪 User {sender} logged out of bot session after requesting tracker")
                else:
                    msg = {
                        "en": "❌ Error generating login link. Please try again.",
                        "es": "❌ Error generando enlace. Por favor intenta de nuevo."
                    }
                    send_message(sender, msg[lang])
                
                return "ok", 200

        # Handle muscle group selection
        if msg_type == "text" and user_states.get(sender, {}).get("expecting_muscle"):
            lang = user_states[sender].get("lang")
            
            muscle_map = {
                "chest": "chest", "pecho": "chest",
                "back": "back", "espalda": "back",
                "biceps": "biceps", "bíceps": "biceps",
                "triceps": "triceps", "tríceps": "triceps",
                "shoulders": "shoulders", "hombros": "shoulders",
                "legs": "legs", "piernas": "legs",
                "abs": "abs", "abdominales": "abs"
            }
            
            muscle = muscle_map.get(text)
            
            if muscle:
                exercises = get_exercises(muscle, lang)
                
                if exercises:
                    user_states[sender]["selected_muscle"] = muscle
                    user_states[sender]["expecting_muscle"] = False
                    
                    send_exercise_list(sender, exercises, muscle, lang)
                    send_workout_logging_options(sender, lang)
                else:
                    msg = {
                        "en": f"No exercises found for {muscle}. Try another muscle group.",
                        "es": f"No se encontraron ejercicios para {muscle}. Prueba otro grupo muscular."
                    }
                    send_message(sender, msg[lang])
            else:
                msg = {
                    "en": "❌ Invalid muscle group. Please choose: Chest, Back, Biceps, Triceps, Shoulders, Legs, or Abs",
                    "es": "❌ Grupo muscular inválido. Elige: Pecho, Espalda, Biceps, Triceps, Hombros, Piernas o Abdominales"
                }
                send_message(sender, msg[lang])
            
            return "ok", 200

        return "ok", 200
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return "ok", 200

# ========================================
# WEB APP ROUTES (from webapp.py)
# ========================================

@app.route('/')
def home():
    """Landing page"""
    return render_home()

@app.route('/login/<token>')
def web_login(token):
    """Handle one-time token login from WhatsApp"""
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT wa_id, expires_at, used FROM login_tokens
            WHERE token = %s
        """, (token,))
        
        result = cur.fetchone()
        
        if not result:
            cur.close()
            conn.close()
            return render_error("Invalid Login Link", "This login link is not valid. Please request a new one from WhatsApp.")
        
        wa_id, expires_at, used = result
        
        if used:
            cur.close()
            conn.close()
            return render_error("Link Already Used", "This login link has already been used. Please request a new one from WhatsApp.")
        
        if int(time.time()) > expires_at:
            cur.close()
            conn.close()
            return render_error("Link Expired", "This login link has expired. Please request a new one from WhatsApp.")
        
        cur.execute("UPDATE login_tokens SET used = TRUE WHERE token = %s", (token,))
        
        cur.execute("""
            SELECT id, name, email, language FROM users WHERE wa_id = %s
        """, (wa_id,))
        
        user_data = cur.fetchone()
        
        conn.commit()
        cur.close()
        conn.close()
        
        if user_data:
            session.clear()
            session['user_id'] = user_data[0]
            session['wa_id'] = wa_id
            session['name'] = user_data[1]
            session['language'] = user_data[3]
            session['login_time'] = time.time()
            
            return redirect(url_for('dashboard'))
        
        return render_error("User Not Found", "Could not find your user account.")
        
    except Exception as e:
        print(f"Login error: {e}")
        import traceback
        traceback.print_exc()
        return render_error("Login Failed", f"An error occurred: {str(e)}")

@app.route('/dashboard')
def dashboard():
    """Main workout dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    if 'login_time' in session:
        elapsed = time.time() - session['login_time']
        if elapsed > 86400:
            session.clear()
            return redirect(url_for('home'))
    
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT COUNT(DISTINCT w.id) as total_workouts,
                   COUNT(we.id) as total_exercises,
                   COALESCE(SUM(we.sets * we.reps), 0) as total_reps
            FROM workouts w
            LEFT JOIN workout_exercises we ON we.workout_id = w.id
            WHERE w.user_id = %s
        """, (session['user_id'],))
        
        stats = cur.fetchone()
        total_workouts, total_exercises, total_reps = stats if stats else (0, 0, 0)
        
        cur.execute("""
            SELECT w.workout_date, w.muscle_group, 
                   we.exercise_name, we.sets, we.reps, we.weight
            FROM workouts w
            JOIN workout_exercises we ON we.workout_id = w.id
            WHERE w.user_id = %s AND w.workout_date >= CURRENT_DATE - INTERVAL '30 days'
            ORDER BY w.workout_date DESC, we.order_index
            LIMIT 50
        """, (session['user_id'],))
        
        workouts = cur.fetchall()
        
        cur.execute("""
            SELECT exercise_name, weight, reps, date_achieved
            FROM personal_records
            WHERE user_id = %s
            ORDER BY date_achieved DESC
            LIMIT 10
        """, (session['user_id'],))
        
        records = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return render_dashboard(session.get('name'), workouts, records, stats)
        
    except Exception as e:
        print(f"Dashboard error: {e}")
        import traceback
        traceback.print_exc()
        return f"Error loading dashboard: {str(e)}", 500

@app.route('/exercises/<muscle_group>')
def view_exercises(muscle_group):
    """View exercises for a muscle group"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    lang = session.get('language', 'en')
    exercises = get_exercises(muscle_group, lang)
    
    return render_exercises(muscle_group, exercises, lang)

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('home'))

@app.route('/health')
def health():
    """Health check endpoint for Railway"""
    return jsonify({"status": "healthy"}), 200

# ========================================
# RUN APPLICATION
# ========================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print("=" * 50)
    print(f"🚀 Starting Combined Workout Bot on port {port}")
    print(f"📍 Webhook: /webhook")
    print(f"📍 Web App: /dashboard")
    print("=" * 50)
    
    # Use waitress for production
    from waitress import serve
    serve(app, host='0.0.0.0', port=port, threads=4)