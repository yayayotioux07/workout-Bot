from supabase import create_client, Client
import os

# --- CONFIGURATION ---
SUPABASE_URL = "https://tbhkoezbwkzwvgaibspw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRiaGtvZXpid2t6d3ZnYWlic3B3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0ODk3OTk5NSwiZXhwIjoyMDY0NTU1OTk1fQ.KhFYpOo8T-dk7qnoxVPta4S-H9OUG8T_av5wD8XW9vc"  # Use service role key to allow DB updates
BUCKET_NAME = "exercise-images"  # Example: "exercise-images"
TABLE_NAME = "exercises"

# --- INITIALIZE SUPABASE CLIENT ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CLEAN FILENAME TO MATCH name_en FORMAT ---
def clean_filename(filename):
    return filename.replace('-', ' ').replace('_', ' ').split('.')[0].title()

# --- GET PUBLIC URL FOR A FILE ---
def get_public_url(filename):
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{filename}"

# --- MAIN FUNCTION TO MATCH AND UPDATE ---
def update_exercise_images():
    files = supabase.storage.from_(BUCKET_NAME).list()

    for file in files:
        filename = file['name']
        name_en = clean_filename(filename)
        url = get_public_url(filename)

        for lang in ['en', 'es']:
            response = supabase.table(TABLE_NAME).update({"image_url": url})\
                .eq("name_en", name_en)\
                .eq("language", lang).execute()

            if response.data:
                print(f"✅ Updated: {name_en} ({lang}) → {url}")
            else:
                print(f"⚠️ No match for: {name_en} ({lang})")

# --- RUN ---
if __name__ == "__main__":
    update_exercise_images()
