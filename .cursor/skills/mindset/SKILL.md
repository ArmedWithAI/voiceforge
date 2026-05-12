---
name: mindset
description: >-
  Runs the VAIB warm-outreach mindset lock-in when the user types /mindset or
  asks to redo or re-lock mindset. Reads and updates
  voiceforge/outreach-starter/.claude/state/user-profile.json (requires
  /activate first). Covers three mindset shifts, three pressure scenarios, and
  merges a mindset block with completed_at. Use when the user says /mindset,
  redo mindset, re-lock mindset, or mindset again after activate.
disable-model-invocation: true
---

# /mindset (Cursor)

The user invokes this by typing `/mindset`, usually after `/activate` in `voiceforge/outreach-starter/`. Goal: three mindset shifts plus three short scenario checks, light pushback when answers drift off doctrine, then save their own words under `mindset` in the profile file.

**Profile path (this repo):** `voiceforge/outreach-starter/.claude/state/user-profile.json`

**Doctrine reference (wording parity):** `voiceforge/outreach-starter/.claude/skills/mindset/SKILL.md`

## Hard rules

- Polished casual sentence case in your messages to the user, not lowercase. Lowercase is for outreach drafts, not this interview.
- If the profile file is missing, stop. Tell them to run `/activate` first (same outreach-starter flow), then return.
- Push back at most **twice** per question. After two counters, save their answer verbatim, note the gap in the summary, move on.
- Do not paste whole doctrine essays. Use the one counter that fits what they said.
- Do not use em dashes.

## Pre-flight

Read `voiceforge/outreach-starter/.claude/state/user-profile.json`. Use `user.first_name` when addressing them.

If `mindset.completed_at` exists, offer:

> "Looks like you already locked in your mindset on [date]. Want to (1) see what you saved, (2) redo one section, or (3) rebuild from scratch?"

## Intro (wait for go)

> "Alright [first_name]. Before we start, mindset is the biggest blocker in doing warm outreach. It's normal to feel unprepared, unsure and not confident. It's exactly why we're doing this together, to make this easier for you.
>
> We're going to discuss the three mental shifts most people get wrong at first, plus a couple of scenarios. Ready?"

Wait for confirmation, then run the three mindsets in order, one exchange cluster at a time.

## Mindset 1, targets

**Ask:** "First question :) In warm outreach, who do you think you should be messaging?"

Aligned examples: anyone who knows my name, everyone I know regardless of job, friends, family, coworkers, classmates, not only business owners.

**Push back** if they say business owners only, niche, decision-makers, or "people in [industry]" (cold framing, no niche in warm, bridges and referrals, everyone knows roughly five people).

**Push back** if "only people I'm close to" (too tight, anyone who recognizes their first name counts).

**Push back** if "people who need what I'm selling" (target is the bridge, not the buyer).

After one or two exchanges, capture a line they own. Save verbatim.

## Mindset 2, selling

**Ask:** "Ok, thanks. In message one, are you trying to sell anyone anything? What do you think is the real goal?"

Aligned: not selling, catchup, goodwill, conversation, referral path only later.

**Push back** if they want a call, demo, or close in message one (no pitching mode, only show what you do when they ask, referrals later).

**Push back** if "get them interested" (even that is a step too far for message one).

**Push back** if "build the list" (tracker is for them, message reads like a friend text).

Save their final answer.

## Mindset 3, hardest

**Ask:** "Third. What do you think is or will be the hardest part of all this warm outreach stuff?"

Aligned: pressing send, awkwardness, volume, actually reaching out.

**Push back** if "figuring out what to write" (awkwardness of sending is the usual real blocker, drafting can be helped).

**Push back** if "picking the right person" (stall tactic, cost of one text if wrong).

**Push back** if "finding time" (time is real, but check if something is underneath).

Save their final answer.

## Three pressure-test scenarios

Keep each to about two or three turns. Save answers, light grading.

**Scenario 1, silent close friend:** They send a demo to a close friend, three days, silence. What do they do? Aligned: do not chase the demo, move on, light catchup later with zero demo mention.

**Scenario 2, direct ask too early:** Reply is "hey, been ages, how are you?" and they want to jump to "know anyone interested in voice AI?" Aligned: too early, build goodwill first, they ask what you do first.

**Scenario 3, same-vertical peer:** Old coworker runs a voice AI agency too. Same outreach as everyone else? Aligned: peer relationship, not a referral engine for same market.

## Major tips after scenarios

Briefly list common mistakes that burn the list:

- No emotionally heavy opener content in outreach.
- No deep tech stack jargon unless they know the stack.
- Keep messages short.
- Easy, open questions ("what's good on your end?"), not homework ("watch this, then give detailed feedback").

## Confirmation before save

Plain English summary with six bullets: targets, selling, hardest, each scenario answer.

> "Sound right to you? Want to tweak anything before I save?"

Wait for yes or edits.

## Save

Merge into the existing profile. **Do not** overwrite `user`, `channels`, `voice`, `tone_tiers`, `illustrative_samples_by_channel`, or `availability`.

Add or replace:

```json
"mindset": {
  "completed_at": "YYYY-MM-DD",
  "targets": "...",
  "selling": "...",
  "hardest": "...",
  "scenarios": {
    "silent_close_friend": "...",
    "direct_ask_too_early": "...",
    "same_vertical_peer": "..."
  }
}
```

Use today's date for `completed_at` (authoritative calendar from user info when available).

## Hand off

> "Saved. When you're ready, type `/outreach` and we can start drafting first messages."

Exact pushback wording when you need line-for-line parity with VAIB: read `voiceforge/outreach-starter/.claude/skills/mindset/SKILL.md`.
