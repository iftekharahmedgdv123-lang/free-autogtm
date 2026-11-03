#!/usr/bin/env python3
"""Free AutoGTM CLI. Run `python3 cli.py --help` for all commands."""
import argparse
import json
import sys
from pathlib import Path

from free_autogtm import db as dbmod
from free_autogtm.campaign import export_drafts, generate_drafts, send
from free_autogtm.discovery import discover, import_csv
from free_autogtm.enrich import enrich_lead

DB = "data.db"

def load_config(path):
    if not Path(path).exists():
        print(f"Config not found: {path} — copy config.example.json to config.json and edit it.")
        sys.exit(1)
    return json.loads(Path(path).read_text())

def cmd_init(args):
    conn = dbmod.connect(DB)
    conn.close()
    print(f"Initialised {DB}. Copy config.example.json to config.json and edit your ICP.")

def cmd_demo(args):
    conn = dbmod.connect(DB)
    samples = [
        {"company": "Northwind SaaS", "website": "https://northwind.example", "domain": "northwind.example",
         "contact_name": "Ava Smith", "role": "Head of Sales", "email": "ava@northwind.example",
         "notes": "Signals: Helps sales teams book more meetings.", "score": 30},
        {"company": "Bright Agency", "website": "https://bright.example", "domain": "bright.example",
         "contact_name": "Liam Jones", "role": "Founder", "email": "liam@bright.example",
         "notes": "Signals: Marketing agency for growing SaaS brands.", "score": 25},
        {"company": "Harbour Tools", "website": "https://harbour.example", "domain": "harbour.example",
         "contact_name": "", "role": "", "email": "",
         "notes": "No email yet — enrich or find a contact manually.", "score": 10},
    ]
    for lead in samples:
        dbmod.add_lead(conn, lead)
    seller = {"name": "Your Name", "company": "Your Company",
              "product": "a done-for-you outbound system", "offer": "It replaces manual prospecting with a reviewed, personalised pipeline."}
    made = generate_drafts(conn, seller)
    print(f"Demo ready: {len(samples)} sample leads, {made} drafts (only leads with email get drafts).")
    print("Run: python3 cli.py serve")

def cmd_discover(args):
    cfg = load_config(args.config)
    conn = dbmod.connect(DB)
    n = discover(conn, cfg.get("icp", {}), max_leads=cfg.get("campaign", {}).get("max_leads_per_run", 30))
    print(f"Discovered {n} new leads.")

def cmd_import(args):
    cfg = {}
    if Path(args.config).exists():
        cfg = load_config(args.config)
    conn = dbmod.connect(DB)
    n = import_csv(conn, args.csv, cfg.get("icp"))
    print(f"Imported {n} new leads from {args.csv}.")

def cmd_enrich(args):
    conn = dbmod.connect(DB)
    updated = 0
    for lead in dbmod.list_leads(conn):
        if lead.get("status") in ("enriched",):
            continue
        changes = enrich_lead(lead)
        if changes:
            dbmod.update_lead(conn, lead["id"], **changes)
            updated += 1
            print(f"  enriched {lead['company']}")
    print(f"Enriched {updated} leads.")

def cmd_draft(args):
    cfg = load_config(args.config)
    conn = dbmod.connect(DB)
    n = generate_drafts(conn, cfg["seller"])
    print(f"Generated drafts for {n} leads with email addresses.")

def cmd_export(args):
    conn = dbmod.connect(DB)
    n = export_drafts(conn, args.out)
    print(f"Exported {n} drafts to {args.out}.")

def cmd_send(args):
    cfg = load_config(args.config) if Path(args.config).exists() else {}
    conn = dbmod.connect(DB)
    sent, skipped, out = send(conn, cfg, really_send=args.really_send)
    if out:
        print(f"Dry-run: no emails sent. Approved drafts written to {out} for review.")
    else:
        print(f"Sent {sent}, skipped {skipped} (suppressed / no email).")

def cmd_suppress(args):
    conn = dbmod.connect(DB)
    dbmod.suppress(conn, args.email, args.reason)
    print(f"Suppressed {args.email} — it will never be sent to.")

def cmd_doctor(args):
    import socket
    import sys
    print(f"Python: {sys.version.split()[0]} (need 3.10+)")
    print(f"Folder: {Path.cwd()}")
    print(f"cli.py here: {Path('cli.py').exists()}")
    print(f"free_autogtm/ here: {Path('free_autogtm').is_dir()}")
    try:
        conn = dbmod.connect(DB)
        print(f"Database: OK — {dbmod.stats(conn)}")
        conn.close()
    except Exception as e:
        print(f"Database: FAILED — {e}")
    for port in (8000, 8001):
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", port))
            print(f"Port {port}: free")
        except OSError as e:
            print(f"Port {port}: BUSY — {e} (use --port {8001 if port == 8000 else 8002})")
        finally:
            s.close()
    print("Next: python3 cli.py demo  then  python3 cli.py serve")

def cmd_serve(args):
    import os
    if args.admin_user:
        os.environ["FREE_AUTOGTM_ADMIN_USER"] = args.admin_user
    if args.admin_password:
        os.environ["FREE_AUTOGTM_ADMIN_PASSWORD"] = args.admin_password
    if args.base_path:
        os.environ["FREE_AUTOGTM_BASE_PATH"] = args.base_path
    from free_autogtm.server import serve
    serve(args.port, args.host)

def main():
    p = argparse.ArgumentParser(description="Free AutoGTM — self-hosted outbound pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn, help_text in [
        ("init", cmd_init, "Create the local database"),
        ("demo", cmd_demo, "Load sample leads + drafts (no network)"),
        ("discover", cmd_discover, "Find leads from public web search"),
        ("import", cmd_import, "Import leads from a CSV"),
        ("enrich", cmd_enrich, "Enrich leads from public homepages"),
        ("draft", cmd_draft, "Generate personalised drafts"),
        ("export", cmd_export, "Export drafts to CSV"),
        ("send", cmd_send, "Dry-run (default) or really send approved drafts"),
        ("suppress", cmd_suppress, "Add an email to the do-not-contact list"),
        ("serve", cmd_serve, "Start the local dashboard"),
        ("doctor", cmd_doctor, "Check setup, database, and free ports"),
    ]:
        sp = sub.add_parser(name, help=help_text)
        sp.set_defaults(fn=fn)
        if name in ("discover", "draft", "send"):
            sp.add_argument("--config", default="config.json")
        if name == "import":
            sp.add_argument("--csv", required=True)
            sp.add_argument("--config", default="config.json")
        if name == "export":
            sp.add_argument("--out", default="outbox.csv")
        if name == "send":
            sp.add_argument("--really-send", action="store_true")
        if name == "suppress":
            sp.add_argument("--email", required=True)
            sp.add_argument("--reason", default="opt-out")
        if name == "serve":
            sp.add_argument("--port", type=int, default=8000)
            sp.add_argument("--host", default="127.0.0.1")
            sp.add_argument("--admin-user", default=None)
            sp.add_argument("--admin-password", default=None)
            sp.add_argument("--base-path", default=None, help="Mount under a subpath, e.g. /tool for iftekhar.ami.bd/tool")
    args = p.parse_args()
    args.fn(args)

if __name__ == "__main__":
    main()
