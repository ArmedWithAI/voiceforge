# Voice Selector Skill

## Goal

Select the best premade ElevenLabs voice for a business demo and return top candidates.

## Inputs

- Business context (`industry`, `tone`, `personality`, `target_customer`)
- Voice catalog from `GET /v1/voices`

## Scoring Dimensions

- Gender fit
- Age fit
- Accent fit
- Energy fit
- Industry style fit

## Industry Heuristics

- Medical: calm, mature, reassuring
- Restaurant: warm, upbeat, inviting
- Tech: clear, confident, precise
- Retail: energetic, friendly, persuasive

## Reasoning Process

1. Consider only plan-safe premade voices (fixed catalog in `agents/voice_picker.py`: entry-tier / widely available IDs; excludes tier-gated premades such as Bella).
2. Score each voice by metadata and descriptive labels.
3. Rank voices and keep top 3.
4. If close scores tie, ask Claude to break tie with concise rationale.
5. Return selected voice plus justification text.
