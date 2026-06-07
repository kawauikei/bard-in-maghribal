import csv
import json
import os
import re
import subprocess
import io
import numpy as np
import scipy.io.wavfile as wavfile
from scipy.signal import correlate
import warnings
warnings.filterwarnings("ignore", message="Reached EOF prematurely")

# Get the directory where this script is located
base_dir = os.path.dirname(os.path.abspath(__file__))

# From public/assets/audio/vocal/ to public/prompts/vocal/
prompt_dir = os.path.normpath(os.path.join(base_dir, "..", "..", "..", "prompts", "vocal"))
vocal_dir = base_dir

def load_audio_as_mono_wav(file_path, sample_rate=22050):
    """FFmpegを使用して音声をデコードし、モノラルWAVの数値配列として取得する"""
    command = [
        'ffmpeg',
        '-y',
        '-i', file_path,
        '-f', 'wav',
        '-ac', '1',
        '-ar', str(sample_rate),
        '-'
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg error for {file_path}: {stderr.decode('utf-8', errors='ignore')}")
    
    # メモリ上のWAVデータを読み込む
    sr, data = wavfile.read(io.BytesIO(stdout))
    
    # 浮動小数点数（-1.0〜1.0）に標準化
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.uint8:
        data = (data.astype(np.float32) - 128.0) / 128.0
        
    return sr, data

def estimate_bpm(file_path):
    """音声のオンセット強度（音の立ち上がり）の自己相関からBPMを簡易推定する"""
    try:
        sr, data = load_audio_as_mono_wav(file_path)
    except Exception as e:
        print(f"BPM estimation failed for {file_path}: {e}")
        return 120.0

    # 10ms単位でエネルギーを計算
    hop_len = int(0.01 * sr)
    num_frames = len(data) // hop_len
    
    env = []
    for i in range(num_frames):
        frame = data[i * hop_len : (i + 1) * hop_len]
        env.append(np.sqrt(np.mean(frame**2)) if len(frame) > 0 else 0.0)
    env = np.array(env)
    
    onsets = np.maximum(np.diff(env), 0.0)
    
    min_lag = int(0.33 / 0.01) # 60 BPM
    max_lag = int(1.0 / 0.01)  # 180 BPM
    
    corr = correlate(onsets, onsets, mode='full')
    center = len(corr) // 2
    search_corr = corr[center + min_lag : center + max_lag + 1]
    
    if len(search_corr) == 0:
        return 120.0
        
    best_lag_offset = np.argmax(search_corr)
    best_lag = min_lag + best_lag_offset
    
    beat_interval_sec = best_lag * 0.01
    raw_bpm = 60.0 / beat_interval_sec
    refined_bpm = round(raw_bpm)
    refined_bpm = max(60, min(180, refined_bpm))
    
    return float(refined_bpm)

# Load existing BPMs from vocal.html to use as cache and avoid recalculating
existing_bpms = {}
html_path = os.path.normpath(os.path.join(base_dir, "..", "..", "..", "devtools", "vocal.html"))
if os.path.exists(html_path):
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        start_tag = "const tracks = ["
        end_tag = "];"
        start_idx = content.find(start_tag)
        end_idx = content.find(end_tag, start_idx)
        if start_idx != -1 and end_idx != -1:
            json_str = content[start_idx + len("const tracks = ") : end_idx + len(end_tag) - 1].strip()
            existing_tracks = json.loads(json_str)
            for t in existing_tracks:
                if "bpms" in t:
                    for fn, bpm in t["bpms"].items():
                        existing_bpms[fn] = bpm
    except Exception as e:
        print(f"Could not load existing BPM cache from vocal.html: {e}")

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
        lyrics_match = re.search(r"(?:ローマ字歌詞|ひらがな歌詞):\s*\n([\s\S]+)$", prompt_content)
        if lyrics_match:
            raw_lyric_lines = [line.strip() for line in lyrics_match.group(1).split("\n") if line.strip()]
            lyrics = " / ".join(raw_lyric_lines)

        pattern = "theme"
        region_code = "0"
        region = ""
        support_theme = ""

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
            "promptFile":   ("../prompts/vocal/" + filename).replace(os.sep, "/"),
            "promptContent": prompt_content,
            "generated":    [],
            "bpms":         {},
        })


# Scan generated audio files in this directory (.mp3 only, mp4 is no longer used)
if os.path.exists(vocal_dir):
    audio_files = [f for f in os.listdir(vocal_dir) if f.endswith(".mp3")]
    for f in audio_files:
        match = re.match(r"^(song_[0-9]{3}_[0-9]{3}_[0-9]{3})(.*)\.(mp3)$", f)
        if not match:
            match = re.match(r"^([0-9A-Za-z]{5,7})__(.+)\.(mp3)$", f)
        if not match:
            continue

        track_id = match.group(1)
        for track in tracks:
            if track["id"] != track_id:
                continue
            if f not in track["generated"]:
                track["generated"].append(f)
            
            if "bpms" not in track:
                track["bpms"] = {}
            if f not in track["bpms"]:
                if f in existing_bpms:
                    track["bpms"][f] = existing_bpms[f]
                else:
                    print(f"Estimating BPM for {f}...")
                    track["bpms"][f] = estimate_bpm(os.path.join(vocal_dir, f))

tracks.sort(key=lambda x: x["id"])

# Inject into vocal.html in public/devtools folder
html_path = os.path.normpath(os.path.join(base_dir, "..", "..", "..", "devtools", "vocal.html"))
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
        print(f"Sync complete: {len(tracks)} tracks updated in vocal.html.")
    else:
        print("Could not find 'const tracks = [' injection point in vocal.html")
else:
    print(f"vocal.html not found at {html_path}")
