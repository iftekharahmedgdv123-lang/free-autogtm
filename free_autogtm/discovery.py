"""Lead discovery.

Two free paths:
1. Public-web search (DuckDuckGo HTML, no API key). Best-effort — search
   engines rate-limit, so treat this as a starting list, not a database.
2. CSV import — the reliable path. Bring leads from directories, search,
   LinkedIn, or lists you already own.
"""
import csv
import re
import urllib.parse
import urllib.request
from urllib.parse import urlparse

from .db import add_lead

def queries_from_icp(icp):
    """Turn an ICP into plain search queries, the way AutoGTM does internally."""
    queries = []
    industries = icp.get("industries", []) or ["companies"]
    locations = icp.get("locations", []) or [""]
    keywords = icp.get("keywords", []) or [""]
    for industry in industries:
        for location in locations:
            queries.append(f"{industry} companies {location}".strip())
            for kw in keywords:
                if kw:
                    queries.append(f"{industry} {kw} {location}".strip())
    # De-duplicate, keep order.
    seen, out = set(), []
    for q in queries:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out

def _domain(url):
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
        return host
    except Exception:
        return ""

def _company_from_domain(domain):
    if not domain:
        return ""
    name = domain.split(".")[0].replace("-", " ").replace("_", " ")
    return name.title()

def search_duckduckgo(query, limit=10):
    """Best-effort public search. Returns [{company, website, domain, source_url}]."""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [search] {query!r} failed: {e}")
        return []
    # DuckDuckGo HTML results link via /l/?uddg=<encoded target>
    targets = re.findall(r"uddg=([^\"&]+)", html)
    results, seen = [], set()
    for raw in targets:
        try:
            target = urllib.parse.unquote(raw)
        except Exception:
            continue
        domain = _domain(target)
        if not domain or domain in seen:
            continue
        if any(bad in domain for bad in ["duckduckgo.com", "wikipedia.org", "linkedin.com", "facebook.com", "youtube.com"]):
            continue
        seen.add(domain)
        results.append({
            "company": _company_from_domain(domain),
            "website": f"https://{domain}",
            "domain": domain,
            "source_url": target,
            "notes": f"Found via search: {query}",
            "score": 10,
        })
        if len(results) >= limit:
            break
    return results

def score_lead(lead, icp):
    score = lead.get("score", 0)
    text = " ".join(str(v) for v in lead.values()).lower()
    for kw in icp.get("keywords", []):
        if kw.lower() in text:
            score += 5
    for bad in icp.get("exclude_keywords", []):
        if bad.lower() in text:
            score -= 20
    return score

def discover(conn, icp, max_leads=30, search_fn=search_duckduckgo):
    added = 0
    for query in queries_from_icp(icp):
        if added >= max_leads:
            break
        print(f"Searching: {query}")
        for lead in search_fn(query, limit=10):
            lead["score"] = score_lead(lead, icp)
            if add_lead(conn, lead):
                added += 1
                print(f"  + {lead['company']} ({lead['domain']})")
            if added >= max_leads:
                break
    return added

def import_csv(conn, csv_path, icp=None):
    added = 0
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            company = (row.get("company") or "").strip()
            if not company:
                continue
            website = (row.get("website") or "").strip()
            lead = {
                "company": company,
                "website": website,
                "domain": _domain(website),
                "contact_name": (row.get("contact_name") or "").strip(),
                "role": (row.get("role") or "").strip(),
                "email": (row.get("email") or "").strip(),
                "notes": (row.get("notes") or "").strip(),
                "score": 20,
            }
            if icp:
                lead["score"] = score_lead(lead, icp)
            if add_lead(conn, lead):
                added += 1
    return added
