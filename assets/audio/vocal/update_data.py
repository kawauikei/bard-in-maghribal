import csv
import json
import os
import re

# Get the directory where this script is located
base_dir = os.path.dirname(os.path.abspath(__file__))

# From public/assets/audio/vocal/ to public/prompts/vocal/
prompt_dir = os.path.normpath(os.path.join(base_dir, "..", "..", "..", "prompts", "vocal"))
vocal_dir = base_dir

tracks = []

# Load metadata and prompt content from index.csv
csv_path = os.path.join(prompt_dir, "index.csv")
if os.path.exists(csv_path):
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            track_id = (row.get("id") or row.get("song_id") or "").strip()
            title = (row.get("title") or "").strip()
            file_rel = (row.get("file") or "").strip()

            if not track_id or not title:
                continue

            prompt_file = os.path.basename(file_rel) if file_rel else f"{track_id}__{title}.txt"
            prompt_path = os.path.join(prompt_dir, prompt_file)

            try:
                with open(prompt_path, "r", encoding="utf-8") as pf:
                    prompt_content = pf.read()
            except OSError:
                prompt_content = ""

            pattern      = (row.get("pattern") or "").strip()           # theme / region
            region_code  = (row.get("region_code") or "").strip()       # 0, 1..9, A, B, C
            region       = (row.get("region") or "").strip()            # 地域名
            instrument   = (row.get("instrument") or "").strip()
            song_type    = (row.get("song_type") or "").strip()
            main_theme   = (row.get("main_theme") or "").strip()
            support_theme = (row.get("support_theme") or "").strip()
            lyrics       = (row.get("lyrics") or "").strip()

            tracks.append({
                "id":           track_id,
                "pattern":      pattern,
                "regionCode":   region_code,
                "region":       region,
                "title":        title,
                "instrument":   instrument,
                "songType":     song_type,
                "mainTheme":    main_theme,
                "supportTheme": support_theme,
                "lyrics":       lyrics,
                "promptFile":   os.path.join("public", "prompts", "vocal", prompt_file).replace(os.sep, "/"),
                "promptContent": prompt_content,
                "generated":    None,
            })

# Scan generated audio files in this directory
if os.path.exists(vocal_dir):
    audio_files = [f for f in os.listdir(vocal_dir) if f.endswith(".mp4") or f.endswith(".mp3")]
    for f in audio_files:
        # New naming: 113110__砂の手紙.mp4  or  11611A__苔の石段・朝.mp4
        match = re.match(r"^([0-9A-Za-z]{5,7})__(.+)\.(mp4|mp3)$", f)
        if not match:
            # Old naming: song_101_211_321__*.mp4
            match = re.match(r"^(song_[0-9]{3}_[0-9]{3}_[0-9]{3})__(.+)\.(mp4|mp3)$", f)
        if not match:
            continue

        track_id = match.group(1)
        for track in tracks:
            if track["id"] != track_id:
                continue
            current_gen = track["generated"]
            if not current_gen or (current_gen.endswith(".mp3") and f.endswith(".mp4")):
                track["generated"] = f

tracks.sort(key=lambda x: x["id"])

# Inject into index.html
html_path = os.path.join(vocal_dir, "index.html")
if os.path.exists(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    json_data = json.dumps(tracks, indent=4, ensure_ascii=False)
    start_tag = "const tracks = ["
    end_tag = "];"

    start_idx = content.find(start_tag)
    end_idx = content.find(end_tag, start_idx)

    if start_idx != -1 and end_idx != -1:
        indented_lines = []
        for i, line in enumerate(json_data.split("\n")):
            if i == 0:
                indented_lines.append(line)
            else:
                indented_lines.append("        " + line)
        indented_json = "\n".join(indented_lines)

        new_content = content[:start_idx] + f"const tracks = {indented_json};" + content[end_idx + len(end_tag):]
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Sync complete: {len(tracks)} tracks updated.")
    else:
        print("Could not find 'const tracks = [' injection point in index.html")
else:
    print(f"index.html not found at {html_path}")
