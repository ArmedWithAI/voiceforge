# VoiceForge

VoiceForge is a zero-input ElevenLabs voice demo generator. The user provides only a business website URL or business name, and the system handles the rest.

## Pipeline Order

Run agents strictly in this sequence:

1. `researcher`  
2. `scriptwriter`  
3. `voice_picker`  
4. `synthesizer`

## Environment Variables

Create a `.env` file (copy from `.env.example`) and set:

- `ANTHROPIC_API_KEY`
- `ELEVENLABS_API_KEY`

## Output Convention

All generation artifacts are saved to:

`/output/{business_name}_{timestamp}/`

Each output folder contains:

- `demo.mp3` (or skipped note in dry run mode)
- `script.txt`
- `context.json`
- `voice_info.txt`
- `summary.md`

## Skills

Skills define how each agent reasons:

- `skills/scraper.md` tells the researcher how to fetch/extract and score confidence.
- `skills/scriptwriter.md` tells the scriptwriter how to compose realistic inbound call scripts.
- `skills/voice_selector.md` tells the voice picker how to rank premade ElevenLabs voices by business fit.

## Run

From inside `voiceforge/`:

`python voiceforge.py "https://example.com"`

or

`python voiceforge.py "Business Name"`

Optional flags:

- `--dry-run` to skip ElevenLabs synthesis.
- `--voice <voice_id>` to override automatic voice selection.

## Offline Mock Fallback

When running with `--dry-run`, VoiceForge automatically enters offline mock mode if either API key is missing.

In offline mock mode it:

- Generates mock business context
- Generates a realistic mock inbound script
- Selects a mock premade voice ranking
- Still writes all output artifacts into `/output/{business_name}_{timestamp}/`
