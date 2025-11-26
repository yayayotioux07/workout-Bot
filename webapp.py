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
            
            @media (max-width: 768px) {{
                .content-grid {{
                    grid-template-columns: 1fr;
                }}
                .header-content {{
                    flex-direction: column;
                    gap: 15px;
                    text-align: center;
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
                <a href="/logout" class="logout-btn">Logout</a>
            </div>
        </div>
        
        <div class="container">
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
                    <button class="log-btn" onclick="window.location.href='/log-exercise/{muscle_group}/{exercise_name}'">
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

@app.route('/log-exercise/<muscle_group>/<exercise_name>')
def log_exercise_form(muscle_group, exercise_name):
    """Detailed exercise logging form similar to fitness apps"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    from datetime import datetime
    current_date = datetime.now().strftime('%Y-%m-%d')
    display_date = datetime.now().strftime('%b %d, %Y')
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Log {exercise_name}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                background: #f5f7fa;
                min-height: 100vh;
                padding-bottom: 100px;
            }}
            .header {{
                background: white;
                padding: 15px 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                position: sticky;
                top: 0;
                z-index: 100;
            }}
            .header-content {{
                max-width: 600px;
                margin: 0 auto;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }}
            .back-btn {{
                background: none;
                border: none;
                color: #667eea;
                font-size: 1.1em;
                cursor: pointer;
                padding: 5px;
            }}
            .save-btn {{
                background: #667eea;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 8px;
                font-weight: 600;
                cursor: pointer;
            }}
            .workout-info {{
                max-width: 600px;
                margin: 20px auto;
                padding: 0 20px;
            }}
            .workout-title {{
                font-size: 1.8em;
                color: #333;
                margin-bottom: 10px;
                font-weight: bold;
                line-height: 1.2;
            }}
            .workout-meta {{
                display: flex;
                gap: 20px;
                color: #666;
                font-size: 0.95em;
                margin-bottom: 30px;
                flex-wrap: wrap;
            }}
            .meta-item {{
                display: flex;
                align-items: center;
                gap: 8px;
                cursor: pointer;
                background: white;
                padding: 10px 15px;
                border-radius: 10px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
                transition: all 0.3s;
                position: relative;
            }}
            .meta-item:hover {{
                color: #667eea;
                box-shadow: 0 4px 10px rgba(102,126,234,0.2);
                transform: translateY(-2px);
            }}
            .meta-item.clickable {{
                border: 2px solid #e0e0e0;
            }}
            .meta-item.clickable:hover {{
                border-color: #667eea;
            }}
            .date-picker {{
                position: absolute;
                opacity: 0;
                pointer-events: none;
                width: 0;
                height: 0;
            }}
            .exercise-card {{
                background: white;
                max-width: 600px;
                margin: 0 auto 20px auto;
                padding: 20px;
                border-radius: 15px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }}
            .exercise-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
            }}
            .exercise-name {{
                color: #667eea;
                font-size: 1.2em;
                font-weight: 600;
            }}
            .set-table {{
                width: 100%;
                overflow-x: auto;
            }}
            .set-header {{
                display: grid;
                grid-template-columns: 60px 1fr 1fr 50px;
                gap: 10px;
                padding: 10px 0;
                border-bottom: 2px solid #f0f0f0;
                font-weight: 600;
                color: #666;
                font-size: 0.9em;
            }}
            .set-header > div {{
                text-align: center;
            }}
            .set-header > div:first-child {{
                text-align: left;
            }}
            .set-row {{
                display: grid;
                grid-template-columns: 60px 1fr 1fr 50px;
                gap: 10px;
                padding: 15px 0;
                align-items: center;
                border-bottom: 1px solid #f5f5f5;
            }}
            .set-number {{
                background: #f0f0f0;
                width: 40px;
                height: 40px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 600;
                color: #333;
            }}
            .set-input {{
                background: #f8f9fa;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
                text-align: center;
                font-size: 1em;
                font-weight: 500;
                color: #333;
                width: 100%;
            }}
            .set-input:focus {{
                outline: none;
                border-color: #667eea;
                background: white;
            }}
            .check-mark {{
                width: 30px;
                height: 30px;
                border-radius: 50%;
                border: 2px solid #e0e0e0;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: all 0.3s;
                margin: 0 auto;
            }}
            .check-mark.checked {{
                background: #4CAF50;
                border-color: #4CAF50;
                color: white;
            }}
            .add-set-btn {{
                width: 100%;
                background: #f8f9fa;
                border: 2px dashed #e0e0e0;
                color: #666;
                padding: 15px;
                border-radius: 10px;
                margin-top: 15px;
                cursor: pointer;
                font-size: 1em;
                font-weight: 500;
                transition: all 0.3s;
            }}
            .add-set-btn:hover {{
                background: #e0e0e0;
                border-color: #667eea;
                color: #667eea;
            }}
            .bottom-bar {{
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                background: white;
                padding: 15px 20px;
                box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
                max-width: 600px;
                margin: 0 auto;
            }}
            .finish-btn {{
                width: 100%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 15px;
                border-radius: 10px;
                font-size: 1.1em;
                font-weight: 600;
                cursor: pointer;
            }}
            
            @media (max-width: 600px) {{
                .workout-info {{
                    padding: 0 15px;
                }}
                .workout-title {{
                    font-size: 1.4em;
                }}
                .workout-meta {{
                    gap: 15px;
                    font-size: 0.9em;
                }}
                .exercise-card {{
                    margin: 0 15px 20px 15px;
                    padding: 15px;
                }}
                .set-header {{
                    grid-template-columns: 45px 90px 90px 45px;
                    gap: 8px;
                    font-size: 0.85em;
                }}
                .set-row {{
                    grid-template-columns: 45px 90px 90px 45px;
                    gap: 8px;
                    padding: 12px 0;
                }}
                .set-number {{
                    width: 35px;
                    height: 35px;
                    font-size: 0.9em;
                }}
                .set-input {{
                    padding: 8px 4px;
                    font-size: 0.95em;
                }}
                .check-mark {{
                    width: 28px;
                    height: 28px;
                }}
                .add-set-btn {{
                    padding: 12px;
                    font-size: 0.95em;
                }}
                .bottom-bar {{
                    padding: 12px 15px;
                }}
                .finish-btn {{
                    padding: 14px;
                    font-size: 1em;
                }}
            }}
            
            @media (max-width: 400px) {{
                .set-header {{
                    grid-template-columns: 40px 80px 80px 40px;
                    gap: 6px;
                }}
                .set-row {{
                    grid-template-columns: 40px 80px 80px 40px;
                    gap: 6px;
                }}
                .set-input {{
                    padding: 6px 2px;
                    font-size: 0.9em;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="header-content">
                <button class="back-btn" onclick="history.back()">✕ Cancel</button>
                <button class="save-btn" onclick="saveWorkout()">Save</button>
            </div>
        </div>
        
        <div class="workout-info">
            <h1 class="workout-title">{exercise_name}</h1>
            <div class="workout-meta">
                <div class="meta-item clickable" onclick="toggleDatePicker()" title="Click to change date">
                    <span>📅</span>
                    <span id="displayDate">{display_date}</span>
                    <span style="color: #667eea; font-size: 0.8em;">▼</span>
                    <input type="date" id="datePicker" class="date-picker" value="{current_date}" max="{current_date}" onchange="updateDate(this)">
                </div>
                <div class="meta-item">🏋️ {muscle_group.title()}</div>
            </div>
        </div>
        
        <div class="exercise-card">
            <div class="exercise-header">
                <span class="exercise-name">{exercise_name}</span>
            </div>
            
            <div class="set-table">
                <div class="set-header">
                    <div>Set</div>
                    <div>lbs</div>
                    <div>Reps</div>
                    <div>✓</div>
                </div>
                
                <div id="setsContainer">
                    <div class="set-row">
                        <div class="set-number">1</div>
                        <input type="number" class="set-input weight-input" placeholder="0" step="0.5">
                        <input type="number" class="set-input reps-input" placeholder="0">
                        <div class="check-mark" onclick="toggleCheck(this)"></div>
                    </div>
                    
                    <div class="set-row">
                        <div class="set-number">2</div>
                        <input type="number" class="set-input weight-input" placeholder="0" step="0.5">
                        <input type="number" class="set-input reps-input" placeholder="0">
                        <div class="check-mark" onclick="toggleCheck(this)"></div>
                    </div>
                    
                    <div class="set-row">
                        <div class="set-number">3</div>
                        <input type="number" class="set-input weight-input" placeholder="0" step="0.5">
                        <input type="number" class="set-input reps-input" placeholder="0">
                        <div class="check-mark" onclick="toggleCheck(this)"></div>
                    </div>
                </div>
                
                <button class="add-set-btn" onclick="addSet()">+ Add Set</button>
            </div>
        </div>
        
        <div class="bottom-bar">
            <button class="finish-btn" onclick="saveWorkout()">Finish Workout 💪</button>
        </div>
        
        <script>
            let setCount = 3;
            let selectedDate = '{current_date}';
            
            function toggleDatePicker() {{
                const picker = document.getElementById('datePicker');
                // Just trigger the native date picker
                picker.showPicker();
            }}
            
            function updateDate(picker) {{
                selectedDate = picker.value;
                const date = new Date(picker.value + 'T00:00:00');
                const options = {{ year: 'numeric', month: 'short', day: 'numeric' }};
                document.getElementById('displayDate').textContent = date.toLocaleDateString('en-US', options);
            }}
            
            function toggleCheck(element) {{
                element.classList.toggle('checked');
                if (element.classList.contains('checked')) {{
                    element.innerHTML = '✓';
                }} else {{
                    element.innerHTML = '';
                }}
            }}
            
            function addSet() {{
                setCount++;
                const container = document.getElementById('setsContainer');
                
                const setRow = document.createElement('div');
                setRow.className = 'set-row';
                setRow.innerHTML = `
                    <div class="set-number">${{setCount}}</div>
                    <input type="number" class="set-input weight-input" placeholder="0" step="0.5">
                    <input type="number" class="set-input reps-input" placeholder="0">
                    <div class="check-mark" onclick="toggleCheck(this)"></div>
                `;
                
                container.appendChild(setRow);
            }}
            
            async function saveWorkout() {{
                const setRows = document.querySelectorAll('.set-row');
                const exercises = [];
                
                setRows.forEach((row, index) => {{
                    const weight = row.querySelector('.weight-input').value;
                    const reps = row.querySelector('.reps-input').value;
                    const checked = row.querySelector('.check-mark').classList.contains('checked');
                    
                    if (weight && reps && checked) {{
                        exercises.push({{
                            name: '{exercise_name}',
                            sets: 1,
                            reps: parseInt(reps),
                            weight: parseFloat(weight)
                        }});
                    }}
                }});
                
                if (exercises.length === 0) {{
                    alert('⚠️ Please complete at least one set!');
                    return;
                }}
                
                const response = await fetch('/api/log-workout', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        muscle_group: '{muscle_group}',
                        exercises: exercises,
                        workout_date: selectedDate
                    }})
                }});
                
                if (response.ok) {{
                    alert('✅ Workout logged successfully!');
                    window.location.href = '/dashboard';
                }} else {{
                    alert('❌ Error logging workout');
                }}
            }}
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
        workout_date = data.get('workout_date', datetime.now().strftime('%Y-%m-%d'))
        
        conn = connect_db()
        cur = conn.cursor()
        
        # Create workout with custom date
        cur.execute("""
            INSERT INTO workouts (user_id, workout_date, muscle_group)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (session['user_id'], workout_date, muscle_group))
        
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
                    DO UPDATE SET weight = %s, reps = %s, date_achieved = %s
                """, (session['user_id'], exercise['name'], exercise['weight'], 
                      exercise['reps'], exercise['weight'], exercise['reps'], workout_date))
        
        conn.commit();
        cur.close();
        conn.close();
        
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