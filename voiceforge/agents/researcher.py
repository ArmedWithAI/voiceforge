import json
import re
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

import httpx
from anthropic import Anthropic
from bs4 import BeautifulSoup

MODEL_NAME = "claude-sonnet-4-5"


def _looks_like_url(text: str) -> bool:
    if text.startswith("http://") or text.startswith("https://"):
        return True
    return "." in text and " " not in text


def _normalize_url(value: str) -> str:
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"https://{value}"


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _guess_name_from_domain(domain: str) -> str:
    stem = re.sub(r"^www\.", "", domain or "", flags=re.I).split(".")[0]
    if not stem:
        return "Unknown"
    return stem.replace("-", " ").replace("_", " ").title()


def _extract_business_name(soup: BeautifulSoup, domain: str) -> str:
    candidates: List[str] = []
    for key in ["og:site_name", "application-name", "twitter:title"]:
        tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if tag and tag.get("content"):
            candidates.append(_clean_text(str(tag.get("content"))))
    if soup.title:
        title_text = _clean_text(soup.title.get_text(" ", strip=True))
        title_split = re.split(r"\s[\-|:|]\s", title_text)
        candidates.extend([c for c in title_split if c])
    h1 = soup.find("h1")
    if h1:
        candidates.append(_clean_text(h1.get_text(" ", strip=True)))
    for candidate in candidates:
        if 2 <= len(candidate) <= 80:
            return candidate
    return _guess_name_from_domain(domain)


def _infer_industry(text: str) -> str:
    haystack = text.lower()
    rules: List[Tuple[str, List[str]]] = [
        ("Healthcare", ["clinic", "medical", "dental", "patient", "hospital"]),
        ("Restaurant & Hospitality", ["menu", "restaurant", "dining", "reservation", "chef"]),
        ("Technology", ["software", "saas", "platform", "api", "automation", "ai"]),
        ("Retail & Ecommerce", ["shop", "store", "cart", "checkout", "fashion", "retail"]),
        ("Professional Services", ["consulting", "advisory", "agency", "client services"]),
        ("Finance", ["banking", "fintech", "investment", "wealth", "insurance"]),
        ("Education", ["course", "learning", "students", "curriculum", "academy"]),
    ]
    best_label = "Unknown"
    best_score = 0
    for label, keywords in rules:
        score = sum(1 for keyword in keywords if keyword in haystack)
        if score > best_score:
            best_label = label
            best_score = score
    return best_label


def _estimate_scrape_confidence(signals: Dict[str, Any]) -> float:
    visible_len = len(str(signals.get("visible_text", "")))
    heading_count = len(signals.get("headings", []))
    has_desc = bool(signals.get("meta_description"))
    has_name = bool(signals.get("business_name") and signals.get("business_name") != "Unknown")

    confidence = 0.4
    if visible_len > 500:
        confidence += 0.2
    if visible_len > 1500:
        confidence += 0.1
    if heading_count >= 3:
        confidence += 0.1
    if has_desc:
        confidence += 0.05
    if has_name:
        confidence += 0.1
    return max(0.0, min(0.95, confidence))


def _extract_page_signals(html: str, source_url: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["style", "noscript"]):
        tag.extract()

    ld_json_items: List[str] = []
    for script_tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw_json = _clean_text(script_tag.get_text(" ", strip=True))
        if raw_json:
            ld_json_items.append(raw_json[:1200])

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    headings = [h.get_text(" ", strip=True) for h in soup.select("h1, h2, h3")][:12]
    paragraphs = [p.get_text(" ", strip=True) for p in soup.select("p")][:24]
    meta_desc_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    meta_description = meta_desc_tag.get("content", "").strip() if meta_desc_tag else ""
    og_description_tag = soup.find("meta", attrs={"property": "og:description"})
    og_description = og_description_tag.get("content", "").strip() if og_description_tag else ""
    domain = urlparse(source_url).netloc
    business_name = _extract_business_name(soup, domain)

    text_blobs: List[str] = [title, business_name, meta_description, og_description] + headings + paragraphs
    visible_text = " ".join([t for t in text_blobs if t]).strip()
    visible_text = re.sub(r"\s+", " ", visible_text)[:8000]
    industry_guess = _infer_industry(visible_text)

    signals = {
        "source_url": source_url,
        "domain": domain,
        "business_name": business_name,
        "industry_guess": industry_guess,
        "title": title,
        "meta_description": meta_description,
        "og_description": og_description,
        "headings": headings,
        "ld_json": ld_json_items[:5],
        "visible_text": visible_text,
        "scrape_confidence": 0.0,
    }
    signals["scrape_confidence"] = _estimate_scrape_confidence(signals)
    return signals


def _coerce_result(raw: Dict[str, Any], fallback_name: str) -> Dict[str, Any]:
    def as_string(value: Any, default: str = "Unknown") -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return default

    def as_list(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    confidence = raw.get("confidence", 0.45)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.45
    confidence = max(0.0, min(1.0, confidence))

    return {
        "business_name": as_string(raw.get("business_name"), fallback_name),
        "industry": as_string(raw.get("industry")),
        "tone": as_string(raw.get("tone")),
        "personality": as_string(raw.get("personality")),
        "services": as_list(raw.get("services")),
        "target_customer": as_string(raw.get("target_customer")),
        "location": as_string(raw.get("location")),
        "tagline": as_string(raw.get("tagline")),
        "key_details": as_list(raw.get("key_details")),
        "confidence": confidence,
    }


def run_research(user_input: str, anthropic_api_key: str, research_prompt: str) -> Dict[str, Any]:
    source_payload: Dict[str, Any] = {"user_input": user_input}

    if _looks_like_url(user_input):
        url = _normalize_url(user_input)
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                response = client.get(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36"
                        ),
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                )
                response.raise_for_status()
                source_payload["scraped"] = _extract_page_signals(response.text, str(response.url))
        except Exception as exc:
            source_payload["scrape_error"] = str(exc)
            source_payload["scraped"] = {}
    else:
        source_payload["scraped"] = {}

    client = Anthropic(api_key=anthropic_api_key)
    user_block = (
        "Build structured business context from this evidence.\n\n"
        f"Input:\n{user_input}\n\n"
        f"Evidence JSON:\n{json.dumps(source_payload, indent=2)}"
    )
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=1200,
        system=research_prompt,
        messages=[{"role": "user", "content": user_block}],
    )
    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()

    heuristic_result: Dict[str, Any] = {}
    scraped = source_payload.get("scraped", {}) if isinstance(source_payload.get("scraped"), dict) else {}
    if scraped:
        heuristic_result = {
            "business_name": scraped.get("business_name", user_input),
            "industry": scraped.get("industry_guess", "Unknown"),
            "tone": "professional and informative",
            "personality": "helpful and trustworthy",
            "services": [],
            "target_customer": "prospective customers",
            "location": "Unknown",
            "tagline": scraped.get("meta_description", "")[:140],
            "key_details": [scraped.get("title", ""), scraped.get("meta_description", "")],
            "confidence": float(scraped.get("scrape_confidence", 0.55)),
        }

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = heuristic_result or {"business_name": user_input, "confidence": 0.35}

    result = _coerce_result(parsed, user_input)
    if scraped:
        if result["business_name"] == user_input and scraped.get("business_name"):
            result["business_name"] = str(scraped.get("business_name"))
        if result["industry"] == "Unknown" and scraped.get("industry_guess"):
            result["industry"] = str(scraped.get("industry_guess"))
        scraped_conf = float(scraped.get("scrape_confidence", 0.0))
        if scraped_conf > result["confidence"]:
            result["confidence"] = scraped_conf
    return result
