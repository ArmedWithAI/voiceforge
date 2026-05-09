# Scriptwriter Skill

## Goal

Write a realistic inbound phone-call script for ElevenLabs demo playback.

## Constraints

- Customer initiates call.
- Agent answers warmly and professionally.
- **Never address the customer by a personal name.** The agent must not greet or respond with invented caller names (no "Hi, Michelle!", "Thanks, Jordan," "Got it, Sarah," etc.). Use neutral phrases only: "Thanks for calling," "How can I help you today?," "Absolutely—tell me a bit more."
- **Customer must not introduce themselves with a personal first or full name** (TTS uses a separate voice; a named identity can clash with how that voice sounds). The caller may reference company, role, or need generically ("I'm calling from…," "We're looking for…," "My team needs…").
- Use turn markers `[CUSTOMER]` and `[AGENT]`.
- Script length must be 100-130 words.
- Include real business details from context.
- Sound natural with conversational fillers like "Of course!" and "Absolutely."
- End with clear resolution and next step.

## Reasoning Process

1. Identify likely caller intent from services and target customer.
2. Construct a short, natural two-party exchange with balanced turns.
3. Inject brand-specific detail (service names, location cues, tone).
4. Verify word count and turn tags before final output.
5. Confirm no personal caller names appear anywhere (customer self-ID or agent addressing the caller by name).
