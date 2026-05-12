import json
from typing import Any, Dict, List, Tuple

import requests
from anthropic import Anthropic

MODEL_NAME = "claude-sonnet-4-5"
VOICES_ENDPOINT = "https://api.elevenlabs.io/v1/voices"
_VOICE_CACHE: List[Dict[str, Any]] = []

# Default [CUSTOMER] voice when multiple candidates match (alphabetical order used to pick Bella first).
CUSTOMER_VOICE_FALLBACK_ID = "6aDn1KB0hjpdcocrUkmq"  # Tiffany

# Premade voices allowed for selection: matched to your current ElevenLabs account.
PLAN_SAFE_PREMADE_VOICE_IDS = frozenset(
    {
        "hpp4J3VqNfWAUOO0d1Us",  # Bella - Professional, Bright, Warm
        "iP95p4xoKVk53GoZ742B",  # Chris - Charming, Down-to-Earth
        "nPczCjzI2devNBz1zQrb",  # Brian - Deep, Resonant and Comforting
        "onwK4e9ZLuTAKqWW03F9",  # Daniel - Steady Broadcaster
        "pFZP5JQG7iQjIQuC4Bku",  # Lily - Velvety Actress
        "pNInz6obpgDQGcFmaJgB",  # Adam - Dominant, Firm
        "pqHfZKP75CvOlQylNhV4",  # Bill - Wise, Mature, Balanced
        "6fZce9LFNG3iEITDfqZZ",  # Charlotte - Warm, Clear, Modern, Distinctive
        "6aDn1KB0hjpdcocrUkmq",  # Tiffany - Natural and Welcoming
        "Lhz3IUCNLm2vpOD2OX5Q",  # Jess - Poetic, Soothing and Calm
        "CwhRBWXzGAHq8TQ4Fs17",  # Roger - Laid-Back, Casual, Resonant
    }
)

_FREE_TIER_MARKERS = frozenset({"free", "starter"})


def _industry_weights(industry: str) -> Dict[str, float]:
    lowered = industry.lower()
    if "medical" in lowered or "health" in lowered or "dental" in lowered:
        return {"calm": 2.0, "mature": 2.0, "warm": 1.0, "confident": 1.0}
    if "restaurant" in lowered or "food" in lowered or "hospitality" in lowered:
        return {"warm": 2.0, "upbeat": 2.0, "energetic": 1.0}
    if "tech" in lowered or "software" in lowered or "saas" in lowered:
        return {"clear": 2.0, "confident": 2.0, "professional": 1.0}
    if "retail" in lowered or "shop" in lowered or "ecommerce" in lowered:
        return {"energetic": 2.0, "friendly": 2.0, "warm": 1.0}
    return {"clear": 1.0, "friendly": 1.0, "professional": 1.0}


def _score_voice(voice: Dict[str, Any], context: Dict[str, Any]) -> Tuple[float, str]:
    labels = (voice.get("labels") or {})
    searchable = " ".join(
        [
            str(voice.get("name", "")),
            str(voice.get("description", "")),
            str(labels.get("accent", "")),
            str(labels.get("age", "")),
            str(labels.get("gender", "")),
            str(labels.get("use_case", "")),
        ]
    ).lower()
    tone = str(context.get("tone", "")).lower()
    personality = str(context.get("personality", "")).lower()
    industry = str(context.get("industry", "")).lower()

    score = 0.0
    reasons: List[str] = []

    for keyword, weight in _industry_weights(industry).items():
        if keyword in searchable:
            score += weight
            reasons.append(f"matches {keyword}")

    for keyword in ["warm", "friendly", "clear", "confident", "calm", "energetic", "mature"]:
        if keyword in tone and keyword in searchable:
            score += 0.9
            reasons.append(f"fits tone {keyword}")
        if keyword in personality and keyword in searchable:
            score += 0.7
            reasons.append(f"fits personality {keyword}")

    if labels.get("gender"):
        score += 0.2
    if labels.get("age"):
        score += 0.2
    if labels.get("accent"):
        score += 0.2

    reason_text = ", ".join(reasons) if reasons else "general business-safe voice profile"
    return score, reason_text


def _normalize_voice_gender(labels: Dict[str, Any]) -> str:
    raw = str((labels or {}).get("gender") or "").strip().lower()
    if raw in ("female", "feminine", "woman"):
        return "female"
    if raw in ("male", "masculine", "man"):
        return "male"
    return ""


def pick_customer_voice(agent_voice: Dict[str, Any], elevenlabs_api_key: str) -> Dict[str, Any]:
    """Premade voice opposite gender from the agent (for [CUSTOMER] lines)."""
    voices = _fetch_voices(elevenlabs_api_key)
    agent_id = agent_voice.get("voice_id")
    others = [v for v in voices if v.get("voice_id") != agent_id]
    if not others:
        raise RuntimeError("No alternate premade ElevenLabs voice available for the customer role.")

    agent_g = _normalize_voice_gender(agent_voice.get("labels") or {})
    if agent_g == "female":
        target = "male"
    elif agent_g == "male":
        target = "female"
    else:
        target = ""

    if target:
        opposite = [
            v for v in others if _normalize_voice_gender(v.get("labels") or {}) == target
        ]
        if opposite:
            others = opposite

    preferred = next((v for v in others if v.get("voice_id") == CUSTOMER_VOICE_FALLBACK_ID), None)
    if preferred:
        return preferred

    others.sort(key=lambda x: str(x.get("name", "")))
    return others[0]


def _voice_allowed_for_all_plans(voice: Dict[str, Any]) -> bool:
    """Drop premades that declare paid-only tiers in the API (when that metadata is present)."""
    vid = str(voice.get("voice_id") or "")
    if vid not in PLAN_SAFE_PREMADE_VOICE_IDS:
        return False
    tiers = voice.get("available_for_tiers")
    if not tiers or not isinstance(tiers, list):
        return True
    lowered = {str(t).lower() for t in tiers if t is not None}
    if not lowered:
        return True
    return bool(lowered & _FREE_TIER_MARKERS)


def _fetch_voices(api_key: str) -> List[Dict[str, Any]]:
    global _VOICE_CACHE
    if _VOICE_CACHE:
        return _VOICE_CACHE

    response = requests.get(VOICES_ENDPOINT, headers={"xi-api-key": api_key}, timeout=20)
    response.raise_for_status()
    voices = response.json().get("voices", [])
    premade = [v for v in voices if v.get("category") == "premade"]
    _VOICE_CACHE = [v for v in premade if _voice_allowed_for_all_plans(v)]
    return _VOICE_CACHE


def pick_voice(
    context: Dict[str, Any],
    elevenlabs_api_key: str,
    anthropic_api_key: str,
    voice_prompt: str,
    override_voice_id: str = "",
) -> Dict[str, Any]:
    voices = _fetch_voices(elevenlabs_api_key)
    if not voices:
        raise RuntimeError("No premade ElevenLabs voices available.")

    if override_voice_id:
        selected = next((v for v in voices if v.get("voice_id") == override_voice_id), None)
        if not selected:
            raise ValueError(
                f"Override voice '{override_voice_id}' was not found among plan-safe premade voices "
                "(see PLAN_SAFE_PREMADE_VOICE_IDS in agents/voice_picker.py)."
            )
        return {
            "selected": selected,
            "top_3": [{"voice": selected, "score": 999.0, "reason": "manual override"}],
            "reasoning": "Voice selected by --voice override.",
        }

    scored = []
    for voice in voices:
        score, reason = _score_voice(voice, context)
        scored.append({"voice": voice, "score": score, "reason": reason})
    scored.sort(key=lambda x: x["score"], reverse=True)
    top_3 = scored[:3]

    if len(top_3) == 1:
        selected = top_3[0]["voice"]
        reasoning = top_3[0]["reason"]
        return {"selected": selected, "top_3": top_3, "reasoning": reasoning}

    score_gap = top_3[0]["score"] - top_3[1]["score"]
    if score_gap >= 0.75:
        return {"selected": top_3[0]["voice"], "top_3": top_3, "reasoning": top_3[0]["reason"]}

    client = Anthropic(api_key=anthropic_api_key)
    user_payload = {
        "business_context": context,
        "tied_candidates": [
            {
                "voice_id": item["voice"].get("voice_id"),
                "name": item["voice"].get("name"),
                "description": item["voice"].get("description"),
                "labels": item["voice"].get("labels"),
                "heuristic_score": item["score"],
                "heuristic_reason": item["reason"],
            }
            for item in top_3
        ],
    }
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=800,
        system=voice_prompt,
        messages=[{"role": "user", "content": json.dumps(user_payload, indent=2)}],
    )
    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()
    try:
        tie = json.loads(text)
        selected_id = tie.get("selected_voice_id", "")
        selected = next((item["voice"] for item in top_3 if item["voice"].get("voice_id") == selected_id), top_3[0]["voice"])
        reasoning = str(tie.get("reasoning", top_3[0]["reason"]))
    except json.JSONDecodeError:
        selected = top_3[0]["voice"]
        reasoning = top_3[0]["reason"]

    return {"selected": selected, "top_3": top_3, "reasoning": reasoning}
