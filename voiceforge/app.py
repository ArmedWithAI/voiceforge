"""
Flask backend for VoiceForge web UI.
Serves the demo UI and proxies generation to voiceforge.py.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS

ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT_DIR / "output"
VOICEFORGE_SCRIPT = ROOT_DIR / "voiceforge.py"
TEMPLATES_DIR = ROOT_DIR / "templates"

app = Flask(__name__, template_folder=str(TEMPLATES_DIR))
CORS(app)


def _folders_before_run() -> set[str]:
    if not OUTPUT_DIR.is_dir():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return set()
    return {p.name for p in OUTPUT_DIR.iterdir() if p.is_dir()}


def _resolve_latest_output_folder(before: set[str]) -> Path | None:
    if not OUTPUT_DIR.is_dir():
        return None
    candidates = [p for p in OUTPUT_DIR.iterdir() if p.is_dir() and p.name not in before]
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    all_dirs = [p for p in OUTPUT_DIR.iterdir() if p.is_dir()]
    if not all_dirs:
        return None
    return max(all_dirs, key=lambda p: p.stat().st_mtime)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _parse_voice_from_voice_info(text: str) -> str:
    """Agent / primary voice display name from voice_info.txt (supports current and legacy layouts)."""
    if not text or not text.strip():
        return "Unknown"

    raw = text.lstrip("\ufeff\u200b")
    lines = [ln.strip() for ln in raw.splitlines()]

    in_agent = False
    for line in lines:
        low = line.lower()
        if low.startswith("agent voice"):
            in_agent = True
            continue
        if in_agent and low.startswith("customer voice"):
            break
        if in_agent and low.startswith("name:"):
            return line.split(":", 1)[1].strip()

    for line in lines:
        if line.lower().startswith("selected voice:"):
            return line.split(":", 1)[1].strip()

    return "Unknown"


def _script_preview(script_text: str, max_len: int = 420) -> str:
    cleaned = re.sub(r"\s+", " ", script_text.strip())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/output/<path:rel_path>")
def serve_output(rel_path: str):
    """Serve generated demo files (audio, etc.) from the output directory."""
    return send_from_directory(OUTPUT_DIR, rel_path)


@app.route("/generate", methods=["POST"])
def generate():
    body = request.get_json(silent=True) or {}
    business = (body.get("business") or "").strip()
    if not business:
        return jsonify({"ok": False, "error": 'Missing "business" field'}), 400

    if not VOICEFORGE_SCRIPT.is_file():
        return jsonify({"ok": False, "error": "voiceforge.py not found"}), 500

    before = _folders_before_run()
    start = time.time()

    try:
        proc = subprocess.run(
            [sys.executable, str(VOICEFORGE_SCRIPT), business],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Generation timed out"}), 504

    folder = _resolve_latest_output_folder(before)
    if proc.returncode != 0:
        err_tail = (proc.stderr or proc.stdout or "")[-2000:]
        return jsonify(
            {
                "ok": False,
                "error": f"voiceforge.py exited with code {proc.returncode}",
                "details": err_tail.strip(),
                "folder": str(folder) if folder else None,
            }
        ), 500

    if not folder or not folder.is_dir():
        return jsonify({"ok": False, "error": "No output folder was created"}), 500

    context_path = folder / "context.json"
    voice_path = folder / "voice_info.txt"
    script_path = folder / "script.txt"
    audio_path = folder / "demo.mp3"

    ctx = _read_json(context_path)
    voice_text = voice_path.read_text(encoding="utf-8", errors="replace") if voice_path.is_file() else ""
    script_text = script_path.read_text(encoding="utf-8", errors="replace") if script_path.is_file() else ""

    business_name = str(ctx.get("business_name") or "").strip() or folder.name.split("_")[0]
    industry = str(ctx.get("industry") or "Unknown")
    voice_label = _parse_voice_from_voice_info(voice_text)

    rel_folder = folder.relative_to(OUTPUT_DIR)
    audio_rel = f"{rel_folder.as_posix()}/demo.mp3"
    if not audio_path.is_file():
        audio_rel = ""

    return jsonify(
        {
            "ok": True,
            "business_name": business_name,
            "industry": industry,
            "voice": voice_label,
            "script_preview": _script_preview(script_text) if script_text else "",
            "audio_path": f"/output/{audio_rel}" if audio_rel else "",
            "output_folder": folder.name,
            "elapsed_sec": round(time.time() - start, 2),
        }
    )


def main():
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
