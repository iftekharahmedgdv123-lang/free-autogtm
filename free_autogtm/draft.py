"""Personalised drafting — local templates, no paid LLM.

The template uses only what enrichment actually found (company, role,
homepage signals). If there is nothing specific to say, it says so
plainly instead of inventing a fake compliment — that is what keeps
reply rates honest.

Swap `build_draft()` for a local LLM (e.g. Ollama) later without
changing callers: it takes (lead, seller) and returns the same dict.
"""

def _first_name(lead):
    name = (lead.get("contact_name") or "").strip()
    return name.split()[0] if name else "there"

def _signal(lead):
    notes = lead.get("notes") or ""
    if "Signals:" in notes:
        sig = notes.split("Signals:", 1)[1].strip()
        # Strip any trailing fetch-failure note.
        sig = sig.split(" | Homepage fetch failed")[0].strip()
        return sig[:180]
    return ""

def build_draft(lead, seller):
    company = lead.get("company", "your team")
    role = lead.get("role") or "team"
    name = _first_name(lead)
    signal = _signal(lead)
    product = seller.get("product", "our product")
    offer = seller.get("offer", "")
    seller_name = seller.get("name", "")
    seller_company = seller.get("company", "")

    if signal:
        opener = f"I was looking at {company} — {signal} stood out, and it made me think this might be relevant for you as {role}."
    else:
        opener = f"I came across {company} while researching companies in your space, and thought this might be relevant for you as {role}."

    subject = f"Quick idea for {company}"
    body = f"""Hi {name},

{opener}

We help teams like yours with {product}. {offer}

Would it be worth a 15-minute chat next week to see if it fits? If not, no worries — just say the word and I won't follow up.

Best,
{seller_name}
{seller_company}
"""
    followup1 = f"""Hi {name},

Just bumping my note below about {company} — happy to send a short example of how {product} works in practice if that's easier than a call.

Worth a look, or should I close the loop?

Best,
{seller_name}
"""
    followup2 = f"""Hi {name},

Last note from me on this — I'll assume timing isn't right and leave it here. If {product} becomes relevant for {company} later, I'm easy to find.

Thanks for your time,
{seller_name}
"""
    return {
        "subject": subject,
        "body": body.strip() + "\n",
        "followup1": followup1.strip() + "\n",
        "followup2": followup2.strip() + "\n",
    }
