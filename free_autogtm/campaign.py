"""Campaigns, approvals, export, and sending.

Safety model (deliberate):
- Drafts start as 'draft'. Only 'approved' drafts can be sent.
- `send(..., really_send=False)` is the default: it writes an outbox CSV
  and marks nothing as sent. Review it first.
- `really_send=True` requires SMTP in config, skips suppressed addresses,
  sends only approved drafts, and pauses between sends.
- TODO (future): reply inbox polling, meeting booking, bounce handling.
  Those need a real mailbox integration — add them only with explicit
  user approval, not by default.
"""
import csv
import smtplib
import time
from email.message import EmailMessage

from .db import is_suppressed, list_drafts, list_leads, set_draft_status

def generate_drafts(conn, seller):
    from .draft import build_draft
    made = 0
    for lead in list_leads(conn):
        if not lead.get("email"):
            continue
        draft = build_draft(lead, seller)
        from .db import add_draft
        add_draft(conn, lead["id"], draft["subject"], draft["body"],
                  draft["followup1"], draft["followup2"])
        made += 1
    return made

def export_drafts(conn, out_path):
    rows = list_drafts(conn)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["company", "contact_name", "email", "subject", "body", "followup1", "followup2", "status"])
        for r in rows:
            w.writerow([r.get("company", ""), r.get("contact_name", ""), r.get("email", ""),
                        r.get("subject", ""), r.get("body", ""), r.get("followup1", ""),
                        r.get("followup2", ""), r.get("status", "")])
    return len(rows)

def send(conn, config, really_send=False):
    """Returns (sent_count, skipped_count, outbox_path_or_None)."""
    smtp_cfg = (config.get("smtp") or {})
    campaign_cfg = (config.get("campaign") or {})
    delay = int(campaign_cfg.get("delay_seconds_between_sends", 60))
    approved = [d for d in list_drafts(conn) if d.get("status") == "approved"]
    if not really_send:
        out = "outbox.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["company", "contact_name", "email", "subject", "body"])
            for d in approved:
                if not is_suppressed(conn, d.get("email", "")):
                    w.writerow([d.get("company", ""), d.get("contact_name", ""), d.get("email", ""), d.get("subject", ""), d.get("body", "")])
        return 0, 0, out
    # Real sending — only approved, only non-suppressed, with a delay.
    if not smtp_cfg.get("host") or not smtp_cfg.get("username"):
        raise ValueError("SMTP not configured in config.json (smtp.host / username).")
    sent = skipped = 0
    for d in approved:
        email = d.get("email", "")
        if not email or is_suppressed(conn, email):
            skipped += 1
            continue
        msg = EmailMessage()
        msg["From"] = smtp_cfg.get("from_email") or smtp_cfg["username"]
        msg["To"] = email
        msg["Subject"] = d["subject"]
        msg.set_content(d["body"])
        with smtplib.SMTP(smtp_cfg["host"], int(smtp_cfg.get("port", 587))) as s:
            s.starttls()
            s.login(smtp_cfg["username"], smtp_cfg["password"])
            s.send_message(msg)
        set_draft_status(conn, d["id"], "sent")
        sent += 1
        if delay:
            time.sleep(delay)
    return sent, skipped, None
