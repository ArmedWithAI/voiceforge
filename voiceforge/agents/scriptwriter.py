import json
import re
from typing import Any, Dict

from anthropic import Anthropic

MODEL_NAME = "claude-sonnet-4-5"


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _is_valid_script(text: str) -> bool:
    words = _word_count(text)
    has_agent = "[AGENT]" in text
    has_customer = "[CUSTOMER]" in text
    return 80 <= words <= 160 and has_agent and has_customer


def run_scriptwriter(
    context: Dict[str, Any], anthropic_api_key: str, script_prompt: str, retries: int = 2
) -> str:
    client = Anthropic(api_key=anthropic_api_key)
    context_blob = json.dumps(context, indent=2)
    feedback = ""

    for _ in range(retries + 1):
        user_prompt = (
            "Create an inbound call script using this business context.\n"
            f"{feedback}\n\n"
            f"Business context JSON:\n{context_blob}"
        )
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=1000,
            system=script_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        script = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()

        if _is_valid_script(script):
            return script

        feedback = (
            "Previous attempt failed validation. Fix all issues: "
            "must be 80-160 words and include both [CUSTOMER] and [AGENT] turns. "
            "Do not use personal caller names: the agent must not address the customer by name, "
            "and the customer must not introduce themselves with a personal first or full name."
        )

    raise ValueError("Could not generate a valid script in 80-160 words with required turns.")
