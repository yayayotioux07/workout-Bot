import os
import subprocess
from supabase import create_client, Client
from pathlib import Path

# --- CONFIGURATION ---
SUPABASE_URL = "https://tbhkoezbwkzwvgaibspw.supabase.co"
SUPABASE_KEY = "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRiaGtvZXpid2t6d3ZnYWlic3B3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0ODk3OTk5NSwiZXhwIjoyMDY0NTU1OTk1fQ"
BUCKET_NAME = "exercise-videos"
LOCAL_ROOT = "C:/Users/Me_/Desktop/Programming Projects/workoutBot/images"

folders = ["abs", "arms", "BACK", "chest", "legs", "shoulders"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def convert_gif_to_mp4(gif_path: str, mp4_path: str):
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", gif_path, "-movflags", "faststart", "-pix_fmt", "yuv420p", mp4_path
        ], check=True)
        print(f"✅ Converted: {gif_path} → {mp4_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error converting {gif_path}: {e}")

def upload_to_supabase(mp4_path: str, supabase_path: str):
    with open(mp4_path, "rb") as file:
        res = supabase.storage.from_(BUCKET_NAME).upload(supabase_path, file, {"upsert": True})
        print(f"⬆️ Uploaded: {supabase_path}")
        return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{supabase_path}"

def process_all_gifs():
    output_links = {}
    for folder in folders:
        local_dir = os.path.join(LOCAL_ROOT, folder)
        if not os.path.isdir(local_dir):
            continue
        for file in os.listdir(local_dir):
            if file.lower().endswith(".gif"):
                gif_path = os.path.join(local_dir, file)
                mp4_name = file.replace(".gif", ".mp4")
                mp4_path = os.path.join(local_dir, mp4_name)
                convert_gif_to_mp4(gif_path, mp4_path)

                supabase_path = f"{folder}/{mp4_name}"
                public_url = upload_to_supabase(mp4_path, supabase_path)
                output_links[file] = public_url

    print("\n🔗 Final Public URLs:")
    for k, v in output_links.items():
        print(f"{k} → {v}")

if __name__ == "__main__":
    process_all_gifs()
