# Free AutoGTM — a self-hosted, free alternative to Explee / AutoGTM

Build your own B2B outbound pipeline, on your own computer, with no
subscription and no paid database.

Explee / AutoGTM (in one line) is: *enter your website, it finds prospects,
writes personalised emails, sends them, follows up, and books meetings.*

This project gives you the same pipeline, in a form you control:

1. **Define your ICP** — who you sell to, in plain JSON.
2. **Discover leads** — from public web search, or import your own CSV.
   There is no 105M-company database here, and that is the honest trade-off:
   you get targeted, public-web leads for free instead of a paid database.
3. **Enrich** — fetch each company's public homepage and pull out what it
   actually does, so emails are not generic.
4. **Draft** — generate a personalised first email + 2 follow-ups per lead,
   using local templates (no paid LLM required).
5. **Review, approve, then send** — nothing sends by itself. Drafts sit in
   a queue until you approve them. Default mode is **dry-run**: it writes
   an outbox CSV you can review, instead of emailing anyone.
6. **Track** — SQLite keeps leads, drafts, approvals, and suppression
   (opt-outs / bounced / do-not-contact) in one local file.

## Quick start (no dependencies — Python 3.10+ only)

```bash
cd free-autogtm
python3 cli.py demo        # creates sample leads + drafts, no network needed
python3 cli.py serve       # dashboard at http://localhost:8000
```

Then open http://localhost:8000 — you will see stats, leads, and drafts.

## Backend + admin panel (v0.2)

The main page at http://localhost:8000 has a separate **Admin Panel**
button, linking to http://localhost:8000/admin.

Log in with (change these in production):
```
FREE_AUTOGTM_ADMIN_USER=admin FREE_AUTOGTM_ADMIN_PASSWORD=changeme123 python3 cli.py serve
# or: python3 cli.py serve --admin-user admin --admin-password 'your-password'
```

In the admin panel you can add/edit/delete leads, edit drafts, approve
or reject them, manage the suppression list, manage campaigns, and save
settings. The API is at `/api/*` and requires the admin session cookie,
except for the read-only public views used by the main page.

To add the same button to *your own* main website, copy
`website-button-snippet.html` and change its link to your real admin
address, e.g. `https://tool.iftekhar.ami.bd/admin`.

## Real run

```bash
cp config.example.json config.json
# edit config.json: your product, your ICP, your name
python3 cli.py init
python3 cli.py discover --config config.json
python3 cli.py enrich
python3 cli.py draft --config config.json
python3 cli.py export --out outbox.csv
# Review outbox.csv, approve drafts in the dashboard, then:
python3 cli.py send --dry-run        # default: writes outbox, sends nothing
```

### Importing your own leads (recommended)

Public web search is a starting point, not a perfect database. The most
reliable free path is importing leads you already have, or that you found
with search / LinkedIn / directories:

```bash
python3 cli.py import --csv my-leads.csv
```

CSV columns: `company,website,contact_name,role,email,notes`
`email` may be blank — those leads are kept for manual enrichment.

### Sending for real (only when you are ready)

Sending is deliberately opt-in, in two steps:

1. Add SMTP settings to `config.json` (your own Gmail app password, or
   any SMTP provider — never commit this file).
2. Run `python3 cli.py send --really-send`

Even then, only drafts you marked `approved` in the dashboard / DB are
sent, one at a time, with a delay between sends. Suppressed addresses
are never sent to.

> If you use Gmail, use an App Password, not your main password, and
> keep daily volume low. Cold email from a brand-new mailbox hurts
> deliverability — warm it up slowly, exactly as paid tools do.

## Project layout

```
cli.py                    Command-line entry point
config.example.json       Your product + ICP + sender (copy to config.json)
free_autogtm/
  db.py                   SQLite storage: leads, drafts, campaigns, suppression
  discovery.py            Search-query generation + public-web discovery + CSV import
  enrich.py               Public homepage fetching + signal extraction
  draft.py                Personalised email + follow-up templates
  campaign.py             Campaigns, approvals, export, dry-run / SMTP sending
  server.py               Local dashboard (stdlib http.server, no framework)
data.db                   Created on first run (ignored by git)
```

## Troubleshooting: local page not working

I re-tested a fresh unzip — the dashboard works — so a local-page
failure is almost always one of these:

1. **You are in the wrong folder.** After unzipping you get
   `free-autogtm/free-autogtm/`. You must `cd` into the *inner* folder,
   the one that contains `cli.py`, before running anything:
   ```bash
   cd free-autogtm/free-autogtm
   python3 cli.py doctor
   ```
2. **The server is not running, or its terminal was closed.** The page
   only works while `python3 cli.py serve` is running in a terminal.
   Keep that terminal open, then open http://localhost:8000 in a browser
   (do not open `server.py` or an HTML file directly).
3. **Port 8000 is already in use.** Run:
   ```bash
   python3 cli.py serve --port 8001
   ```
   and open http://localhost:8001 instead.
4. **Windows:** use `python` instead of `python3`:
   ```bash
   python cli.py doctor
   python cli.py serve
   ```
5. **Python is missing / too old.** You need Python 3.10+. Check with
   `python3 --version` (or `python --version` on Windows).

If it still fails, copy the exact error from the terminal and send it
to me — the error text tells us which of the above it is.

## Responsible use — read this

This is a sales tool, not a spam tool. Only use it for:

- Genuine B2B outreach to companies that could plausibly buy what you sell
- Publicly published business contact details, or contacts you have a
  legitimate reason to approach
- One short, relevant, honest email — with a clear opt-out, and honouring
  every opt-out immediately (`python3 cli.py suppress --email x@y.com`)

Do not scrape private data, do not buy scraped email lists, do not send
to personal (non-business) addresses, and respect local law (GDPR / PECR
in the UK/EU, CAN-SPAM in the US, and your local equivalent). If in doubt,
ask for an introduction instead of cold emailing.

## What this deliberately does NOT do

- No paid database, no Exa / Apollo / ZoomInfo key required
- No pre-warmed shared mailboxes, no deliverability guarantee
- No automatic sending, no auto-reply handling, no meeting booking —
  those are the paid parts of Explee. You review replies yourself, and
  you can add a reply inbox later (see `TODO` in `campaign.py`).
- No tracking pixels, no open tracking

## Customising

- Change the voice in `free_autogtm/draft.py` — templates are plain
  Python, with the lead's company, role, and homepage notes as inputs.
- Add a local LLM later by replacing `build_draft()`'s template body
  with a call to Ollama (`http://localhost:11434`) — the function
  signature stays the same.
- Add a new search source in `free_autogtm/discovery.py` by adding a
  function that returns the same lead dict shape.

## Licence

MIT — use it, fork it, sell with it. Your leads and drafts are yours,
stored locally in `data.db`.
