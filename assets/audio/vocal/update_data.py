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

# Load metadata and prompt content by scanning song_*.txt files directly
if os.path.exists(prompt_dir):
    import glob
    txt_files = glob.glob(os.path.join(prompt_dir, "song_*.txt"))
    for pf_path in txt_files:
        try:
            with open(pf_path, "r", encoding="utf-8") as pf:
                prompt_content = pf.read()
        except OSError:
            continue

        filename = os.path.basename(pf_path)
        id_match = re.search(r"^ID:\s*(song_[0-9_]+|[a-zA-Z0-9_]+)", prompt_content, re.MULTILINE)
        if id_match:
            track_id = id_match.group(1).strip()
        else:
            match_fn = re.match(r"^song_([0-9]+)_([0-9]+)_([0-9]+)", filename)
            if match_fn:
                track_id = f"song_{match_fn.group(1)}_{match_fn.group(2)}_{match_fn.group(3)}"
            else:
                track_id = os.path.splitext(filename)[0]

        title_match = re.search(r"^タイトル:\s*(.+)$", prompt_content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else os.path.splitext(filename)[0]

        inst_match = re.search(r"^楽器:\s*(.+)$", prompt_content, re.MULTILINE)
        instrument = inst_match.group(1).strip() if inst_match else ""

        song_type_match = re.search(r"^曲調:\s*(.+)$", prompt_content, re.MULTILINE)
        song_type = song_type_match.group(1).strip() if song_type_match else ""

        theme_match = re.search(r"^主題:\s*(.+)$", prompt_content, re.MULTILINE)
        main_theme = theme_match.group(1).strip() if theme_match else ""

        lyrics = ""
        lyrics_match = re.search(r"ひらがな歌詞:\s*\n([\s\S]+)$", prompt_content)
        if lyrics_match:
            raw_lyric_lines = [line.strip() for line in lyrics_match.group(1).split("\n") if line.strip()]
            lyrics = " / ".join(raw_lyric_lines)

        pattern = "theme"
        region_code = "0"
        region = ""
        support_theme = ""

        # Check if the filename or ID matches the structure to infer region
        # e.g., if there's any regional naming
        # Let's keep it simple or parse further if needed
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
            "promptFile":   os.path.join("public", "prompts", "vocal", filename).replace(os.sep, "/"),
            "promptContent": prompt_content,
            "generated":    None,
        })


# Scan generated audio files in this directory
if os.path.exists(vocal_dir):
    audio_files = [f for f in os.listdir(vocal_dir) if f.endswith(".mp4") or f.endswith(".mp3")]
    for f in audio_files:
        # Matches the standard ID prefix e.g. song_101_211_321 followed by optional text or Japanese labels and extension
        match = re.match(r"^(song_[0-9]{3}_[0-9]{3}_[0-9]{3})(.*)\.(mp4|mp3)$", f)
        if not match:
            # Check other patterns if needed
            match = re.match(r"^([0-9A-Za-z]{5,7})__(.+)\.(mp4|mp3)$", f)
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
