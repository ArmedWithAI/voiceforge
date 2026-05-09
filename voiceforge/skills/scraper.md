# Scraper Skill

## Goal

Extract reliable business context from a single URL or business name with a confidence score.

## Reasoning Process

1. Try `httpx` GET against the provided URL (or inferred homepage if input looks like a domain).
2. Parse visible HTML with BeautifulSoup (`title`, headings, paragraph text, meta description).
3. Derive:
   - `business_name`
   - `industry`
   - `tone`
   - `services`
   - `personality`
   - `target_customer`
   - `location`
   - `tagline`
   - `key_details`
4. If page text is missing or weak, fall back to Claude web-informed reasoning from available clues.
5. Output structured JSON plus `confidence` from `0.0` to `1.0`.

## Output Format

Return valid JSON object only. Keep unknown fields as best-guess strings and lower confidence accordingly.
