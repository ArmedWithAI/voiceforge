import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from agents.voice_picker import pick_customer_voice

TTS_BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"
MODEL_ID = "eleven_multilingual_v2"
VOICE_SETTINGS = {"stability": 0.45, "similarity_boost": 0.75}
REQUEST_TIMEOUT_S = 60


def _clean_script_for_tts(script: str) -> str:
    cleaned = re.sub(r"\[(AGENT|CUSTOMER)\]\s*", "", script, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _parse_script_turns(script_text: str) -> Optional[List[Tuple[str, str]]]:
    """Split into [(AGENT|CUSTOMER, text), ...]. Returns None for legacy single-voice path."""
    raw = script_text.strip()
    parts = re.split(r"\[(AGENT|CUSTOMER)\]\s*", raw, flags=re.IGNORECASE)
    if len(parts) < 2:
        return None

    prefix = re.sub(r"\s+", " ", parts[0].strip())
    turns: List[Tuple[str, str]] = []
    i = 1
    while i + 1 < len(parts):
        role = parts[i].upper()
        text = re.sub(r"\s+", " ", parts[i + 1].strip())
        if role not in ("AGENT", "CUSTOMER"):
            role = "AGENT"
        if text:
            turns.append((role, text))
        i += 2

    if prefix and turns:
        r0, t0 = turns[0]
        turns[0] = (r0, (prefix + " " + t0).strip())
    elif prefix and not turns:
        turns.append(("CUSTOMER", prefix))

    return turns if turns else None


def _synthesize_segment(text: str, voice_id: str, elevenlabs_api_key: str) -> bytes:
    payload = {
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": VOICE_SETTINGS,
    }
    response = requests.post(
        f"{TTS_BASE_URL}/{voice_id}",
        headers={
            "xi-api-key": elevenlabs_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json=payload,
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.content


def _concat_mp3_segments(segment_bytes: List[bytes]) -> bytes:
    """Append MPEG audio chunks back-to-back (no re-encode; works with typical decoder pipelines)."""
    return b"".join(segment_bytes)


def synthesize_and_save(
    output_dir: Path,
    script_text: str,
    context: Dict[str, Any],
    voice_result: Dict[str, Any],
    elevenlabs_api_key: str,
    dry_run: bool,
) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    script_path = output_dir / "script.txt"
    context_path = output_dir / "context.json"
    voice_info_path = output_dir / "voice_info.txt"
    summary_path = output_dir / "summary.md"
    audio_path = output_dir / "demo.mp3"

    script_path.write_text(script_text, encoding="utf-8")
    context_path.write_text(json.dumps(context, indent=2), encoding="utf-8")

    selected = voice_result["selected"]
    top_3 = voice_result.get("top_3", [])
    reasoning = voice_result.get("reasoning", "")

    customer_voice: Optional[Dict[str, Any]] = None
    if not dry_run:
        customer_voice = pick_customer_voice(selected, elevenlabs_api_key)

    voice_lines = [
        "Agent voice ([AGENT] lines):",
        f"  Name: {selected.get('name', 'Unknown')}",
        f"  Voice ID: {selected.get('voice_id', 'Unknown')}",
        f"  Category: {selected.get('category', 'Unknown')}",
        "  Labels: "
        + json.dumps(selected.get("labels") or {}, separators=(",", ":")),
        "",
        "Customer voice ([CUSTOMER] lines):",
    ]
    if customer_voice:
        voice_lines.extend(
            [
                f"  Name: {customer_voice.get('name', 'Unknown')}",
                f"  Voice ID: {customer_voice.get('voice_id', 'Unknown')}",
                "  Labels: "
                + json.dumps(customer_voice.get("labels") or {}, separators=(",", ":")),
                "(Opposite gender from agent when labels allow.)",
            ]
        )
    else:
        voice_lines.append("  (Resolved during synthesis; omitted in dry-run.)")

    voice_lines.extend(
        [
            "",
            "Voice picker reasoning:",
            reasoning,
            "",
            "Top 3 agent candidates:",
        ]
    )
    for idx, item in enumerate(top_3, start=1):
        voice = item["voice"]
        voice_lines.append(
            f"{idx}. {voice.get('name', 'Unknown')} ({voice.get('voice_id', 'Unknown')}) "
            f"- score={item.get('score', 0):.2f} - {item.get('reason', '')}"
        )
    voice_info_path.write_text("\n".join(voice_lines), encoding="utf-8")

    if dry_run:
        audio_status = "Skipped ElevenLabs synthesis (--dry-run)."
    else:
        turns = _parse_script_turns(script_text)
        agent_id = selected["voice_id"]
        cust_id = customer_voice["voice_id"] if customer_voice else agent_id

        if turns:
            blobs: List[bytes] = []
            segments_dir = output_dir / "segments"
            segments_dir.mkdir(parents=True, exist_ok=True)
            for idx, (role, line) in enumerate(turns, start=1):
                vid = agent_id if role == "AGENT" else cust_id
                blob = _synthesize_segment(line, vid, elevenlabs_api_key)
                blobs.append(blob)
                seg_path = segments_dir / f"turn_{idx:02d}_{role.lower()}.mp3"
                seg_path.write_bytes(blob)
            audio_path.write_bytes(_concat_mp3_segments(blobs))
            audio_status = (
                f"Generated {audio_path.name} ({len(blobs)} turns, dual voices; segments/ + byte concat merge)"
            )
        else:
            payload_text = _clean_script_for_tts(script_text)
            blob = _synthesize_segment(payload_text, agent_id, elevenlabs_api_key)
            audio_path.write_bytes(blob)
            audio_status = (
                f"Generated {audio_path.name} (single clip; script had no [AGENT]/[CUSTOMER] turns)"
            )

    cust_name = (
        (customer_voice or {}).get("name", "—")
        if not dry_run
        else "(dry-run)"
    )
    cust_vid = (
        (customer_voice or {}).get("voice_id", "—")
        if not dry_run
        else "(dry-run)"
    )

    summary_md = "\n".join(
        [
            "# VoiceForge Demo Summary",
            "",
            f"- Business: {context.get('business_name', 'Unknown')}",
            f"- Industry: {context.get('industry', 'Unknown')}",
            f"- Confidence: {context.get('confidence', 'Unknown')}",
            f"- Agent voice: {selected.get('name', 'Unknown')} (`{selected.get('voice_id', 'Unknown')}`)",
            f"- Customer voice: {cust_name} (`{cust_vid}`)",
            f"- Audio: {audio_status}",
            "",
            "## Output Files",
            "- script.txt",
            "- context.json",
            "- voice_info.txt",
            "- summary.md",
            "- segments/ (per-turn MP3 clips when script uses [AGENT]/[CUSTOMER] tags)",
            "- demo.mp3 (only when not dry run)",
        ]
    )
    summary_path.write_text(summary_md, encoding="utf-8")

    return {
        "script": script_path,
        "context": context_path,
        "voice_info": voice_info_path,
        "summary": summary_path,
        "audio": audio_path,
    }
