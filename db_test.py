import psycopg2

try:
    conn = psycopg2.connect(
        host="aws-0-us-west-1.pooler.supabase.com",
        database="postgres",
        user="postgres.tbhkoezbwkzwvgaibspw",
        password="Key25one!38",  # Replace this
        port=5432,
         sslmode="require"
    )
    print("✅ Connected successfully!")
    conn.close()
except Exception as e:
    print("❌ Connection failed:", e)
