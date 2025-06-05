# WhatsApp Workout Bot

A WhatsApp bot that provides exercise recommendations based on muscle groups, with support for English and Spanish languages.

## Features
- 🌐 Multilingual (English/Spanish)
- 👤 User registration system
- 💪 Exercise recommendations by muscle group
- 📸 Image-based exercise demonstrations
- 🔄 Session management

## Tech Stack
- Python with Flask
- PostgreSQL (Supabase)
- WhatsApp Cloud API
- Waitress WSGI server

## Getting Started
1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Set up your WhatsApp Business API credentials
4. Configure your Supabase database
5. Run the server:
```bash
python run.py
```

## Project Structure
```
workoutBot/
├── webhook.py      # Main application logic
├── run.py         # Production server
├── requirements.txt
└── README.md
```

## Database Schema
### Users Table
- wa_id (Primary Key)
- name
- email
- registered
- language

### Exercises Table
- id
- name_en
- name_es
- equipment
- muscle_group
- image_url