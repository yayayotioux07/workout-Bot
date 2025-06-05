import psycopg2

# DB connection details (update if needed)
DB_HOST = "aws-0-us-west-1.pooler.supabase.com"
DB_NAME = "postgres"
DB_USER = "postgres.tbhkoezbwkzwvgaibspw"
DB_PASSWORD = "Key25one!38"
DB_PORT = "5432"

def insert_exercises():
    data = [
        {
            "name_en": "Barbell Bench Press",
            "name_es": "Press de banca con barra",
            "equipment": "Barbell",
            "muscle_group": "Pectoralis Major"
        },
        {
            "name_en": "Dumbbell Bench Press",
            "name_es": "Press de banca con mancuernas",
            "equipment": "Dumbbells",
            "muscle_group": "Pectoralis Major"
        },
        {
            "name_en": "Incline Dumbbell Bench Press",
            "name_es": "Press inclinado con mancuernas",
            "equipment": "Dumbbells",
            "muscle_group": "Pectoralis Major (Upper)"
        },
        {
            "name_en": "Decline Dumbbell Bench Press",
            "name_es": "Press declinado con mancuernas",
            "equipment": "Dumbbells",
            "muscle_group": "Pectoralis Major (Lower)"
        },
        {
            "name_en": "Dumbbell Chest Fly",
            "name_es": "Aperturas de pecho con mancuernas",
            "equipment": "Dumbbells",
            "muscle_group": "Pectoralis Major"
        },
        {
            "name_en": "Cable Crossover",
            "name_es": "Cruce de cables",
            "equipment": "Cable Machine",
            "muscle_group": "Pectoralis Major"
        },
        {
            "name_en": "Push-ups",
            "name_es": "Flexiones",
            "equipment": "Bodyweight",
            "muscle_group": "Pectoralis Major"
        },
        {
            "name_en": "Dips",
            "name_es": "Fondos en paralelas",
            "equipment": "Parallel Bars",
            "muscle_group": "Pectoralis Major (Lower)"
        },
        {
            "name_en": "Incline Dumbbell Fly",
            "name_es": "Aperturas inclinadas con mancuernas",
            "equipment": "Dumbbells",
            "muscle_group": "Pectoralis Major (Upper)"
        },
        {
            "name_en": "Machine Chest Press",
            "name_es": "Press de pecho en máquina",
            "equipment": "Machine",
            "muscle_group": "Pectoralis Major"
        }
    ]

    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cur = conn.cursor()

        for row in data:
            # Insert English version
            cur.execute("""
                INSERT INTO exercises (name_en, name_es, equipment, muscle_group, language)
                VALUES (%s, %s, %s, %s, %s)
            """, (row["name_en"], row["name_es"], row["equipment"], row["muscle_group"], "en"))

            # Insert Spanish version
            cur.execute("""
                INSERT INTO exercises (name_en, name_es, equipment, muscle_group, language)
                VALUES (%s, %s, %s, %s, %s)
            """, (row["name_en"], row["name_es"], row["equipment"], row["muscle_group"], "es"))

        conn.commit()
        cur.close()
        conn.close()
        print("✅ Exercises inserted successfully.")

    except Exception as e:
        print("❌ Error inserting exercises:", e)

# Run it
insert_exercises()
