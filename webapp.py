from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from flask_cors import CORS
import psycopg2
import os
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app)

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT")

def connect_db():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
        port=DB_PORT
    )

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Workout Tracker</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 500px;
                width: 100%;
                text-align: center;
            }
            h1 { 
                color: #333; 
                margin-bottom: 20px;
                font-size: 2.5em;
            }
            .emoji { font-size: 4em; margin-bottom: 20px; }
            p { color: #666; line-height: 1.6; margin: 15px 0; }
            .info { 
                background: #f8f9fa; 
                padding: 20px; 
                border-radius: 10px; 
                margin-top: 30px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="emoji">💪</div>
            <h1>Workout Tracker</h1>
            <p>Please login via WhatsApp to access your personalized workout tracker.</p>
            <div class="info">
                <p><strong>How to login:</strong></p>
                <p>1. Open WhatsApp<br>
                2. Message your fitness bot<br>
                3. Type "tracker" to get your login link</p>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/login/<token>')
def web_login(token):
    """Handle one-time token login from WhatsApp"""
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        # Verify token
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
        
        # Mark token as used
        cur.execute("UPDATE login_tokens SET used = TRUE WHERE token = %s", (token,))
        
        # Get user data
        cur.execute("""
            SELECT id, name, email, language FROM users WHERE wa_id = %s
        """, (wa_id,))
        
        user_data = cur.fetchone()
        
        conn.commit()
        cur.close()
        conn.close()
        
        if user_data:
            # Set session
            session['user_id'] = user_data[0]
            session['wa_id'] = wa_id
            session['name'] = user_data[1]
            session['language'] = user_data[3]
            
            return redirect(url_for('dashboard'))
        
        return render_error("User Not Found", "Could not find your user account.")
        
    except Exception as e:
        print(f"Login error: {e}")
        import traceback
        traceback.print_exc()
        return render_error("Login Failed", f"An error occurred: {str(e)}")

def render_error(title, message):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            .error {{
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 500px;
                width: 100%;
                text-align: center;
            }}
            h2 {{ color: #e74c3c; margin-bottom: 20px; }}
            p {{ color: #666; line-height: 1.6; }}
            .emoji {{ font-size: 4em; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <div class="error">
            <div class="emoji">❌</div>
            <h2>{title}</h2>
            <p>{message}</p>
        </div>
    </body>
    </html>
    """, 403

@app.route('/dashboard')
def dashboard():
    """Main workout dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        # Get workout statistics
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
        
        # Get recent workouts (last 30 days)
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
        
        # Get personal records
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

def render_dashboard(name, workouts, records, stats):
    total_workouts, total_exercises, total_reps = stats
    
    # Define exactly 7 muscle groups with bilingual names
    muscle_groups = [
        {
            "key": "chest",
            "en": "Chest",
            "es": "Pecho",
            "emoji": "💪",
            "color": "#667eea"
        },
        {
            "key": "back",
            "en": "Back",
            "es": "Espalda",
            "emoji": "🏋️",
            "color": "#f093fb"
        },
        {
            "key": "biceps",
            "en": "Biceps",
            "es": "Bíceps",
            "emoji": "💪",
            "color": "#fa709a"
        },
        {
            "key": "triceps",
            "en": "Triceps",
            "es": "Tríceps",
            "emoji": "💪",
            "color": "#fee140"
        },
        {
            "key": "shoulders",
            "en": "Shoulders",
            "es": "Hombros",
            "emoji": "🏋️",
            "color": "#43e97b"
        },
        {
            "key": "legs",
            "en": "Legs",
            "es": "Piernas",
            "emoji": "🦵",
            "color": "#4facfe"
        },
        {
            "key": "abs",
            "en": "Abs",
            "es": "Abdominales",
            "emoji": "🎯",
            "color": "#30cfd0"
        }
    ]
    
    # Build muscle group cards
    muscle_cards = ""
    for muscle in muscle_groups:
        muscle_cards += f"""
        <div class="muscle-card" style="border-left: 4px solid {muscle['color']};" onclick="window.location.href='/exercises/{muscle['key']}'">
            <div class="muscle-emoji">{muscle['emoji']}</div>
            <h3>{muscle['en']}</h3>
            <p class="muscle-subtitle">{muscle['es']}</p>
        </div>
        """
    
    # Build workout history HTML
    workout_html = ""
    if workouts:
        current_date = None
        for date, muscle, exercise, sets, reps, weight in workouts:
            if date != current_date:
                if current_date is not None:
                    workout_html += "</div>"
                workout_html += f"""
                <div class="workout-day">
                    <div class="workout-date">
                        <strong>📅 {date.strftime('%A, %B %d, %Y')}</strong>
                        <span class="muscle-badge">{muscle.title() if muscle else 'General'}</span>
                    </div>
                """
                current_date = date
            
            workout_html += f"""
            <div class="exercise-row">
                <span class="exercise-name">{exercise}</span>
                <span class="exercise-stats">{sets} × {reps} @ {weight}kg</span>
            </div>
            """
        
        if current_date is not None:
            workout_html += "</div>"
    else:
        workout_html = """
        <div class="empty-state">
            <div class="empty-emoji">🏋️</div>
            <p>No workouts logged yet!</p>
            <p>Start tracking your progress by browsing exercises below.</p>
        </div>
        """
    
    # Build personal records HTML
    records_html = ""
    if records:
        for exercise, weight, reps, date in records:
            records_html += f"""
            <div class="record-item">
                <div class="record-exercise">
                    <strong>{exercise}</strong>
                    <span class="record-date">{date.strftime('%b %d, %Y')}</span>
                </div>
                <div class="record-stats">
                    <span class="record-weight">{weight}kg</span>
                    <span class="record-reps">× {reps}</span>
                </div>
            </div>
            """
    else:
        records_html = """
        <div class="empty-state-small">
            <p>Complete workouts to set your first PR! 🎯</p>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Workout Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                background: #f5f7fa;
                min-height: 100vh;
                padding-bottom: 60px;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px 20px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header-content {{
                max-width: 1200px;
                margin: 0 auto;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            h1 {{ font-size: 1.8em; }}
            .header-buttons {{
                display: flex;
                gap: 15px;
                align-items: center;
            }}
            .logout-btn {{
                background: rgba(255,255,255,0.2);
                color: white;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 8px;
                transition: background 0.3s;
            }}
            .logout-btn:hover {{
                background: rgba(255,255,255,0.3);
            }}
            .coffee-btn {{
                background: #FFDD00;
                color: #000;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 8px;
                transition: all 0.3s;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            }}
            .coffee-btn:hover {{
                background: #FFED4E;
                transform: translateY(-2px);
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            }}
            .container {{
                max-width: 1200px;
                margin: 30px auto;
                padding: 0 20px;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            .stat-card {{
                background: white;
                padding: 25px;
                border-radius: 15px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
                text-align: center;
            }}
            .stat-value {{
                font-size: 2.5em;
                font-weight: bold;
                color: #667eea;
                display: block;
            }}
            .stat-label {{
                color: #666;
                margin-top: 8px;
                font-size: 0.9em;
            }}
            
            /* Muscle Group Cards Section */
            .section-title {{
                font-size: 1.8em;
                color: #333;
                margin: 40px 0 20px 0;
            }}
            .muscle-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }}
            .muscle-card {{
                background: white;
                padding: 30px 20px;
                border-radius: 15px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
                text-align: center;
                cursor: pointer;
                transition: all 0.3s ease;
            }}
            .muscle-card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 5px 20px rgba(0,0,0,0.1);
            }}
            .muscle-emoji {{
                font-size: 3em;
                margin-bottom: 15px;
            }}
            .muscle-card h3 {{
                color: #333;
                margin-bottom: 5px;
                font-size: 1.2em;
            }}
            .muscle-subtitle {{
                color: #999;
                font-size: 0.9em;
                font-weight: 500;
            }}
            
            .content-grid {{
                display: grid;
                grid-template-columns: 2fr 1fr;
                gap: 20px;
            }}
            .card {{
                background: white;
                padding: 25px;
                border-radius: 15px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            }}
            .card h2 {{
                color: #333;
                margin-bottom: 20px;
                font-size: 1.5em;
            }}
            .workout-day {{
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 2px solid #f0f0f0;
            }}
            .workout-day:last-child {{
                border-bottom: none;
            }}
            .workout-date {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                color: #333;
            }}
            .muscle-badge {{
                background: #667eea;
                color: white;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 0.85em;
            }}
            .exercise-row {{
                display: flex;
                justify-content: space-between;
                padding: 12px;
                background: #f8f9fa;
                margin-bottom: 8px;
                border-radius: 8px;
            }}
            .exercise-name {{
                font-weight: 500;
                color: #333;
            }}
            .exercise-stats {{
                color: #666;
                font-family: 'Courier New', monospace;
            }}
            .record-item {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 15px;
                background: #f8f9fa;
                margin-bottom: 10px;
                border-radius: 8px;
                border-left: 4px solid #ffd700;
            }}
            .record-exercise strong {{
                display: block;
                color: #333;
                margin-bottom: 5px;
            }}
            .record-date {{
                color: #999;
                font-size: 0.85em;
            }}
            .record-stats {{
                text-align: right;
            }}
            .record-weight {{
                font-size: 1.3em;
                font-weight: bold;
                color: #667eea;
                display: block;
            }}
            .record-reps {{
                color: #666;
                font-size: 0.9em;
            }}
            .empty-state {{
                text-align: center;
                padding: 60px 20px;
                color: #999;
            }}
            .empty-emoji {{
                font-size: 4em;
                margin-bottom: 20px;
            }}
            .empty-state-small {{
                text-align: center;
                padding: 40px 20px;
                color: #999;
            }}
            
            /* Support banner */
            .support-banner {{
                background: linear-gradient(135deg, #FFDD00 0%, #FFA500 100%);
                padding: 20px;
                border-radius: 15px;
                text-align: center;
                margin-bottom: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .support-banner p {{
                color: #333;
                margin-bottom: 15px;
                font-size: 1.1em;
            }}
            .coffee-btn-large {{
                background: white;
                color: #000;
                padding: 15px 30px;
                text-decoration: none;
                border-radius: 10px;
                font-weight: 600;
                display: inline-flex;
                align-items: center;
                gap: 10px;
                transition: all 0.3s;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                font-size: 1.1em;
            }}
            .coffee-btn-large:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0,0,0,0.3);
            }}
            
            @media (max-width: 768px) {{
                .content-grid {{
                    grid-template-columns: 1fr;
                }}
                .header-content {{
                    flex-direction: column;
                    gap: 15px;
                    text-align: center;
                }}
                .header-buttons {{
                    flex-direction: column;
                    width: 100%;
                }}
                .coffee-btn, .logout-btn {{
                    width: 100%;
                    justify-content: center;
                }}
                .muscle-grid {{
                    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
                }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="header-content">
                <h1>💪 {name}'s Workout Tracker</h1>
                <div class="header-buttons">
                    <a href="https://buymeacoffee.com/yourprofile" target="_blank" class="coffee-btn">
                        ☕ Buy Me a Coffee
                    </a>
                    <a href="/logout" class="logout-btn">Logout</a>
                </div>
            </div>
        </div>
        
        <div class="container">
            <div class="support-banner">
                <p>☕ Enjoying the app? Support the project!</p>
                <a href="https://buymeacoffee.com/yourprofile" target="_blank" class="coffee-btn-large">
                    ☕ Buy Me a Coffee
                </a>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <span class="stat-value">{total_workouts}</span>
                    <span class="stat-label">Total Workouts</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{total_exercises}</span>
                    <span class="stat-label">Total Exercises</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{total_reps:,}</span>
                    <span class="stat-label">Total Reps</span>
                </div>
            </div>
            
            <h2 class="section-title">Browse Exercises by Muscle Group</h2>
            <div class="muscle-grid">
                {muscle_cards}
            </div>
            
            <div class="content-grid">
                <div class="card">
                    <h2>Recent Workouts (Last 30 Days)</h2>
                    {workout_html}
                </div>
                
                <div class="card">
                    <h2>🏆 Personal Records</h2>
                    {records_html}
                </div>
            </div>
        </div>
    </body>
    </html>
    """

# Add new route for exercise browsing by muscle group
@app.route('/exercises/<muscle_group>')
def view_exercises(muscle_group):
    """View all exercises for a specific muscle group"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        # Get exercises for this muscle group
        lang = session.get('language', 'en')
        
        cur.execute("""
            SELECT name_en, name_es, equipment, image_url, gif_url 
            FROM exercises 
            WHERE LOWER(muscle_group) = LOWER(%s)
            ORDER BY name_en
        """, (muscle_group,))
        
        exercises = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Build exercise cards
        exercise_cards = ""
        for name_en, name_es, equipment, image_url, gif_url in exercises:
            exercise_name = name_en if lang == 'en' else name_es
            
            gif_section = ""
            if gif_url:
                gif_section = f'<a href="{gif_url}" target="_blank" class="gif-link">View Animation 🎬</a>'
            
            exercise_cards += f"""
            <div class="exercise-card">
                <img src="{image_url}" alt="{exercise_name}" onerror="this.src='https://via.placeholder.com/300x200?text=Exercise'">
                <div class="exercise-info">
                    <h3>{exercise_name}</h3>
                    <p class="equipment">Equipment: {equipment}</p>
                    {gif_section}
                    <button class="log-btn" onclick="logExercise('{exercise_name}', '{muscle_group}')">
                        Log This Exercise
                    </button>
                </div>
            </div>
            """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{muscle_group.title()} Exercises</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    background: #f5f7fa;
                    min-height: 100vh;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                }}
                .header-content {{
                    max-width: 1200px;
                    margin: 0 auto;
                    display: flex;
                    align-items: center;
                    gap: 20px;
                }}
                .back-btn {{
                    background: rgba(255,255,255,0.2);
                    color: white;
                    padding: 10px 20px;
                    text-decoration: none;
                    border-radius: 8px;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 30px auto;
                    padding: 0 20px;
                }}
                .exercise-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                    gap: 25px;
                }}
                .exercise-card {{
                    background: white;
                    border-radius: 15px;
                    overflow: hidden;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
                    transition: transform 0.3s;
                }}
                .exercise-card:hover {{
                    transform: translateY(-5px);
                    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
                }}
                .exercise-card img {{
                    width: 100%;
                    height: 200px;
                    object-fit: cover;
                }}
                .exercise-info {{
                    padding: 20px;
                }}
                .exercise-info h3 {{
                    color: #333;
                    margin-bottom: 10px;
                }}
                .equipment {{
                    color: #999;
                    font-size: 0.9em;
                    margin-bottom: 15px;
                }}
                .gif-link {{
                    display: inline-block;
                    color: #667eea;
                    text-decoration: none;
                    margin-bottom: 15px;
                    font-size: 0.9em;
                }}
                .log-btn {{
                    width: 100%;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    padding: 12px;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 1em;
                    transition: opacity 0.3s;
                }}
                .log-btn:hover {{
                    opacity: 0.9;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="header-content">
                    <a href="/dashboard" class="back-btn">← Back</a>
                    <h1>💪 {muscle_group.title()} Exercises</h1>
                </div>
            </div>
            
            <div class="container">
                <div class="exercise-grid">
                    {exercise_cards}
                </div>
            </div>
            
            <script>
                function logExercise(exerciseName, muscleGroup) {{
                    const sets = prompt("How many sets?", "3");
                    if (!sets) return;
                    
                    const reps = prompt("How many reps?", "10");
                    if (!reps) return;
                    
                    const weight = prompt("Weight in kg?", "20");
                    if (!weight) return;
                    
                    fetch('/api/log-workout', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            muscle_group: muscleGroup,
                            exercises: [{{
                                name: exerciseName,
                                sets: parseInt(sets),
                                reps: parseInt(reps),
                                weight: parseFloat(weight)
                            }}]
                        }})
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            alert('✅ Workout logged successfully!');
                        }} else {{
                            alert('❌ Error logging workout');
                        }}
                    }});
                }}
            </script>
        </body>
        </html>
        """
        
    except Exception as e:
        print(f"Error viewing exercises: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}", 500

@app.route('/log-workout')
def log_workout_page():
    """Workout logging form"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Log Workout</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                background: #f5f7fa;
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            }
            h1 { color: #333; margin-bottom: 30px; }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                color: #666;
                margin-bottom: 8px;
                font-weight: 500;
            }
            input, select {
                width: 100%;
                padding: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 1em;
            }
            input:focus, select:focus {
                outline: none;
                border-color: #667eea;
            }
            .exercise-entry {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 15px;
            }
            .sets-reps-grid {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 10px;
            }
            button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 15px 30px;
                border: none;
                border-radius: 10px;
                font-size: 1em;
                cursor: pointer;
                width: 100%;
                margin-top: 20px;
            }
            button:hover {
                opacity: 0.9;
            }
            .back-link {
                color: #667eea;
                text-decoration: none;
                display: inline-block;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/dashboard" class="back-link">← Back to Dashboard</a>
            <h1>📝 Log Workout</h1>
            
            <form id="workoutForm">
                <div class="form-group">
                    <label>Muscle Group</label>
                    <select name="muscle_group" required>
                        <option value="">Select muscle group</option>
                        <option value="chest">Chest</option>
                        <option value="back">Back</option>
                        <option value="legs">Legs</option>
                        <option value="shoulders">Shoulders</option>
                        <option value="biceps">Biceps</option>
                        <option value="triceps">Triceps</option>
                        <option value="abs">Abs</option>
                    </select>
                </div>
                
                <div id="exercises">
                    <div class="exercise-entry">
                        <div class="form-group">
                            <label>Exercise Name</label>
                            <input type="text" name="exercise_name[]" placeholder="e.g., Bench Press" required>
                        </div>
                        <div class="sets-reps-grid">
                            <div class="form-group">
                                <label>Sets</label>
                                <input type="number" name="sets[]" placeholder="3" required>
                            </div>
                            <div class="form-group">
                                <label>Reps</label>
                                <input type="number" name="reps[]" placeholder="10" required>
                            </div>
                            <div class="form-group">
                                <label>Weight (kg)</label>
                                <input type="number" step="0.5" name="weight[]" placeholder="60" required>
                            </div>
                        </div>
                    </div>
                </div>
                
                <button type="button" onclick="addExercise()" style="background: #28a745;">+ Add Another Exercise</button>
                <button type="submit">Save Workout</button>
            </form>
        </div>
        
        <script>
            function addExercise() {
                const exercisesDiv = document.getElementById('exercises');
                const newExercise = document.querySelector('.exercise-entry').cloneNode(true);
                newExercise.querySelectorAll('input').forEach(input => input.value = '');
                exercisesDiv.appendChild(newExercise);
            }
            
            document.getElementById('workoutForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                
                const response = await fetch('/api/log-workout', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        muscle_group: formData.get('muscle_group'),
                        exercises: formData.getAll('exercise_name[]').map((name, i) => ({
                            name: name,
                            sets: parseInt(formData.getAll('sets[]')[i]),
                            reps: parseInt(formData.getAll('reps[]')[i]),
                            weight: parseFloat(formData.getAll('weight[]')[i])
                        }))
                    })
                });
                
                if (response.ok) {
                    alert('Workout logged successfully! 🎉');
                    window.location.href = '/dashboard';
                } else {
                    alert('Error logging workout. Please try again.');
                }
            });
        </script>
    </body>
    </html>
    """

@app.route('/api/log-workout', methods=['POST'])
def api_log_workout():
    """API endpoint to log workout"""
    if 'user_id' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        data = request.json
        muscle_group = data['muscle_group']
        exercises = data['exercises']
        
        conn = connect_db()
        cur = conn.cursor()
        
        # Create workout
        cur.execute("""
            INSERT INTO workouts (user_id, workout_date, muscle_group)
            VALUES (%s, CURRENT_DATE, %s)
            RETURNING id
        """, (session['user_id'], muscle_group))
        
        workout_id = cur.fetchone()[0]
        
        # Add exercises
        for idx, exercise in enumerate(exercises):
            cur.execute("""
                INSERT INTO workout_exercises 
                (workout_id, exercise_name, sets, reps, weight, order_index)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (workout_id, exercise['name'], exercise['sets'], 
                  exercise['reps'], exercise['weight'], idx))
            
            # Check for PR
            cur.execute("""
                SELECT weight FROM personal_records 
                WHERE user_id = %s AND exercise_name = %s
            """, (session['user_id'], exercise['name']))
            
            pr = cur.fetchone()
            if not pr or exercise['weight'] > pr[0]:
                cur.execute("""
                    INSERT INTO personal_records (user_id, exercise_name, weight, reps)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, exercise_name)
                    DO UPDATE SET weight = %s, reps = %s, date_achieved = CURRENT_DATE
                """, (session['user_id'], exercise['name'], exercise['weight'], 
                      exercise['reps'], exercise['weight'], exercise['reps']))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"Error logging workout: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/workouts', methods=['GET'])
def get_workouts():
    """API endpoint for workout data"""
    if 'user_id' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT w.workout_date, we.exercise_name, we.sets, we.reps, we.weight, w.muscle_group
            FROM workouts w
            JOIN workout_exercises we ON we.workout_id = w.id
            WHERE w.user_id = %s
            ORDER BY w.workout_date DESC
            LIMIT 100
        """, (session['user_id'],))
        
        data = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify([{
            "date": str(row[0]),
            "exercise": row[1],
            "sets": row[2],
            "reps": row[3],
            "weight": float(row[4]),
            "muscle_group": row[5]
        } for row in data])
        
    except Exception as e:
        print(f"Error getting workouts: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print("🚀 Starting Workout Tracker Web App...")
    print(f"📍 Running on: http://0.0.0.0:{port}")
    app.run(debug=False, port=port, host='0.0.0.0')