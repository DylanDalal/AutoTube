# run_pipeline.py

import subprocess
import os

# Paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(ROOT_DIR, 'scripts')

def run_script(script_name):
    """Helper to run a Python script inside /scripts/."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    print(f"Running {script_name}...")
    result = subprocess.run(["python3", script_path], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error running {script_name}:")
        print(result.stderr)
    else:
        print(result.stdout)

def main():
    print("Starting AutoYouTube Pipeline...")

    # Step 1: Scrape new posts
    run_script('scrape_reddit.py')

    # Step 2: Generate scripts from posts
    run_script('generate_script.py')

    # Step 3: Convert scripts to audio
    run_script('text_to_speech.py')

    # Step 4: Link to video and add subtitles
    run_script('assemble_video.py')

    print("Pipeline completed.")

if __name__ == "__main__":
    main()
