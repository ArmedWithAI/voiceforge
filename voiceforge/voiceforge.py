import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from agents.researcher import run_research
from agents.scriptwriter import run_scriptwriter
from agents.synthesizer import synthesize_and_save
from agents.voice_picker import pick_voice


def _mask_key(value: str) -> str:
    if not value:
        return "(missing)"
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


def _safe_console_print(console: Console, text: str) -> None:
    try:
        console.print(text)
    except UnicodeEncodeError:
        fallback = re.sub(r"[^\x00-\x7F]+", "", text).strip()
        print(fallback or text.encode("ascii", errors="ignore").decode("ascii"))


def _print_step(console: Console, emoji: str, step_text: str, supports_emoji: bool) -> None:
    prefix = emoji if supports_emoji else "-"
    _safe_console_print(console, f"{prefix} [bold]{step_text}[/bold]")


def _mock_context(input_value: str) -> Dict[str, Any]:
    business_name = input_value if " " in input_value or "." not in input_value else input_value.split(".")[0]
    return {
        "business_name": business_name.strip().title() or "Sample Business",
        "industry": "AI Technology",
        "tone": "clear, confident, and helpful",
        "personality": "professional, warm, and solution-oriented",
        "services": ["AI platform support", "API access guidance", "enterprise onboarding"],
        "target_customer": "business teams evaluating AI tooling",
        "location": "Global",
        "tagline": "Build smarter workflows with trusted AI.",
        "key_details": [
            "Offers developer-friendly APIs",
            "Supports enterprise use cases",
            "Focuses on reliability and rapid onboarding",
        ],
        "confidence": 0.42,
    }


def _mock_script(context: Dict[str, Any]) -> str:
    return (
        f"[CUSTOMER] Hi, I am calling because my team is evaluating {context.get('business_name', 'your')} "
        "for AI-powered workflows. We need dependable API access and quick onboarding, and I want to understand "
        "what support you provide before we move forward. "
        f"[AGENT] Absolutely, and thanks for reaching out to {context.get('business_name', 'us')}! Of course, I can help. "
        "We guide teams through setup, provide clear API documentation, and offer practical onboarding for both pilots "
        "and enterprise rollouts. If you share your timeline and goals, I can recommend the best starting plan and "
        "set up a follow-up with our solutions team today."
    )


def _mock_voice_result(override_voice_id: str = "") -> Dict[str, Any]:
    voices = [
        {
            "voice_id": "premade-rachel",
            "name": "Rachel",
            "category": "premade",
            "description": "Warm and professional with confident clarity.",
            "labels": {"gender": "female", "age": "young_adult", "accent": "american"},
        },
        {
            "voice_id": "premade-adam",
            "name": "Adam",
            "category": "premade",
            "description": "Clear and mature with calm delivery.",
            "labels": {"gender": "male", "age": "middle_aged", "accent": "american"},
        },
        {
            "voice_id": "premade-bella",
            "name": "Bella",
            "category": "premade",
            "description": "Friendly and upbeat for customer engagement.",
            "labels": {"gender": "female", "age": "young_adult", "accent": "american"},
        },
    ]
    selected = voices[0]
    if override_voice_id:
        selected = next((v for v in voices if v["voice_id"] == override_voice_id), voices[0])

    top_3 = [{"voice": v, "score": float(3 - i), "reason": "offline mock ranking"} for i, v in enumerate(voices)]
    return {"selected": selected, "top_3": top_3, "reasoning": "Offline mock voice selection (dry-run fallback)."}


def _load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _safe_name(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip())
    return cleaned.strip("_") or "business"


def _run_post_hook(project_root: Path, output_dir: Path) -> None:
    hook = project_root / "hooks" / "post_generate.sh"
    if not hook.exists():
        return
    try:
        subprocess.run(
            ["bash", str(hook), str(output_dir)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="VoiceForge: Zero-input ElevenLabs voice demo generator")
    parser.add_argument("input_value", help="Business website URL or business name")
    parser.add_argument("--dry-run", action="store_true", help="Skip ElevenLabs TTS generation")
    parser.add_argument("--voice", default="", help="Override selected premade voice ID")
    parser.add_argument(
        "--debug-env",
        action="store_true",
        help="Print safe environment/key loading diagnostics (masked).",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path, override=True)
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "").strip().strip("\"'")
    elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "").strip().strip("\"'")
    if not args.dry_run and not anthropic_api_key:
        print("Missing ANTHROPIC_API_KEY in environment.", file=sys.stderr)
        return 1
    if not elevenlabs_api_key and not args.dry_run:
        print("Missing ELEVENLABS_API_KEY in environment.", file=sys.stderr)
        return 1
    offline_mock_mode = args.dry_run and (not anthropic_api_key or not elevenlabs_api_key)
    mock_voice_in_dry_run = args.dry_run

    console = Console()
    output_encoding = (sys.stdout.encoding or "").lower()
    supports_emoji = "utf" in output_encoding
    prompts_dir = project_root / "prompts"
    if args.debug_env:
        _safe_console_print(console, f"[cyan]Debug[/cyan] .env path: {env_path}")
        _safe_console_print(console, f"[cyan]Debug[/cyan] .env exists: {env_path.exists()}")
        _safe_console_print(
            console,
            "[cyan]Debug[/cyan] ANTHROPIC_API_KEY loaded: "
            f"{bool(anthropic_api_key)} len={len(anthropic_api_key)} value={_mask_key(anthropic_api_key)}",
        )
        _safe_console_print(
            console,
            "[cyan]Debug[/cyan] ELEVENLABS_API_KEY loaded: "
            f"{bool(elevenlabs_api_key)} len={len(elevenlabs_api_key)} value={_mask_key(elevenlabs_api_key)}",
        )

    try:
        research_prompt = _load_prompt(prompts_dir / "research_prompt.txt")
        script_prompt = _load_prompt(prompts_dir / "script_prompt.txt")
        voice_prompt = _load_prompt(prompts_dir / "voice_prompt.txt")

        _print_step(console, "🔎", "Step 1/4: Researching business...", supports_emoji)
        if offline_mock_mode:
            _safe_console_print(
                console,
                f"{'🧪 ' if supports_emoji else ''}[yellow]Offline mock mode active (missing API key in dry-run).[/yellow]",
            )
            context = _mock_context(args.input_value)
        else:
            context = run_research(args.input_value, anthropic_api_key, research_prompt)

        _print_step(console, "📝", "Step 2/4: Writing inbound call script...", supports_emoji)
        script = _mock_script(context) if offline_mock_mode else run_scriptwriter(context, anthropic_api_key, script_prompt)

        _print_step(console, "🎙️", "Step 3/4: Selecting best ElevenLabs voice...", supports_emoji)
        if mock_voice_in_dry_run:
            _safe_console_print(
                console,
                "[yellow]Dry-run mode: using mock voice selection (no ElevenLabs API calls).[/yellow]",
            )
            voice_result = _mock_voice_result(args.voice)
        else:
            voice_result = pick_voice(
                context=context,
                elevenlabs_api_key=elevenlabs_api_key,
                anthropic_api_key=anthropic_api_key,
                voice_prompt=voice_prompt,
                override_voice_id=args.voice,
            )

        _print_step(console, "🔊", "Step 4/4: Generating demo output...", supports_emoji)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        business_name = _safe_name(str(context.get("business_name", args.input_value)))
        output_dir = project_root / "output" / f"{business_name}_{ts}"
        files = synthesize_and_save(
            output_dir=output_dir,
            script_text=script,
            context=context,
            voice_result=voice_result,
            elevenlabs_api_key=elevenlabs_api_key,
            dry_run=args.dry_run,
        )

        _run_post_hook(project_root, output_dir)
        summary_text = files["summary"].read_text(encoding="utf-8")
        try:
            console.print(Panel(summary_text, title="VoiceForge Complete", expand=False))
        except UnicodeEncodeError:
            print(summary_text)
        print(summary_text)
        return 0
    except Exception as exc:
        _safe_console_print(console, f"[red]VoiceForge failed:[/red] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
