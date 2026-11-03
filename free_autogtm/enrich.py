"""Enrichment from public homepages only.

Fetches a company's public website, extracts its title / description and
any business email published on that page, and stores a short signal
summary for the drafter. No private data, no login, no scraping behind
paywalls.
"""
import re
import urllib.request

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
META_RE = re.compile(
    r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\'](.*?)["\']',
    re.I | re.S,
)

def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text

def fetch_page(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 FreeAutoGTM/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def enrich_lead(lead):
    """Return dict of updates for a lead (does not write to DB itself)."""
    website = lead.get("website") or ""
    if not website:
        return {}
    try:
        html = fetch_page(website)
    except Exception as e:
        return {"notes": (lead.get("notes") or "") + f" | Homepage fetch failed: {e}"}
    title = _clean(TITLE_RE.search(html).group(1)) if TITLE_RE.search(html) else ""
    meta = META_RE.search(html)
    description = _clean(meta.group(1)) if meta else ""
    # Only keep plausible business emails, skip obvious traps / personal-looking.
    emails = []
    for email in EMAIL_RE.findall(html):
        low = email.lower()
        if any(bad in low for bad in [".png", ".jpg", ".svg", "example.com", "w3.org"]):
            continue
        if low not in emails:
            emails.append(low)
        if len(emails) >= 3:
            break
    signals = " | ".join(p for p in [title, description[:240]] if p)
    notes = lead.get("notes") or ""
    if signals:
        notes = (notes + " | Signals: " + signals)[:900]
    updates = {"notes": notes}
    if emails and not lead.get("email"):
        updates["email"] = emails[0]
        updates["status"] = "enriched"
    if signals:
        updates["score"] = int(lead.get("score", 0)) + 10
    return updates
