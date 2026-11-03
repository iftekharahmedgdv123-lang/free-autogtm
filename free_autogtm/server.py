"""Standalone backend + admin panel — Python stdlib only.

Run:  python3 cli.py serve
Then: http://localhost:8000/        — main page, with a separate
                                     "Admin Panel" button
      http://localhost:8000/admin  — login-protected admin panel

Admin login (env vars, never commit them):
    FREE_AUTOGTM_ADMIN_USER (default: admin)
    FREE_AUTOGTM_ADMIN_PASSWORD (default: changeme123 — change it!)

API (all /api/* except /api/login require a session cookie):
    GET  /api/me, /api/stats, /api/leads, /api/drafts, /api/suppressed,
         /api/campaigns, /api/settings, /api/export
    POST /api/login, /api/logout, /api/leads, /api/suppress, /api/campaigns
    PUT  /api/leads/<id>, /api/drafts/<id>, /api/settings
    DELETE /api/leads/<id>
    POST /api/drafts/<id>/approve, /api/drafts/<id>/reject
"""
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import auth
from .db import (
    add_campaign, add_lead, connect, delete_lead, get_setting, list_campaigns,
    list_drafts, list_leads, list_suppressed, set_draft_status, set_setting,
    stats, suppress, update_draft_fields, update_lead,
)
from .discovery import _domain

DB_PATH = os.environ.get("FREE_AUTOGTM_DB", "data.db")

def base_path():
    """Mount prefix, e.g. '/tool' for iftekhar.ami.bd/tool, or '' locally.
    Set via FREE_AUTOGTM_BASE_PATH or `cli.py serve --base-path /tool`.
    The app then answers /tool, /tool/admin, /tool/api/*, while the main
    site at / stays untouched — important when the tool shares a domain
    with an existing site that already has its own /admin page."""
    return os.environ.get("FREE_AUTOGTM_BASE_PATH", "").rstrip("/")

def strip_base(path):
    base = base_path()
    if base and path == base:
        return "/"
    if base and path.startswith(base + "/"):
        return path[len(base):]
    return path

def render(html):
    return html.replace("__BASE__", base_path())

MAIN_HTML = """<!doctype html><html><head><meta charset='utf-8'>
<title>Free AutoGTM</title>
<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem}
table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid #ddd;padding:.5rem;text-align:left;vertical-align:top}
.card{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1rem 0}
.admin-btn{display:inline-block;background:#111;color:#fff !important;padding:.8rem 1.4rem;border-radius:8px;text-decoration:none;font-weight:600;margin:1rem 0}
.admin-btn:hover{background:#333}
pre{white-space:pre-wrap}</style></head><body>
<h1>Free AutoGTM</h1>
<p>Your self-hosted outbound pipeline. Leads, drafts and approvals live here.</p>
<!-- Separate button on the main page to access the admin panel -->
<a class="admin-btn" href="__BASE__/admin">Admin Panel &rarr;</a>
<p><small>Admin is login-protected. The main page is a read-only overview.</small></p>
<div class='card' id='stats'>Loading…</div>
<h2>Leads</h2><div id='leads'>Loading…</div>
<h2>Drafts</h2><div id='drafts'>Loading…</div>
<script>
const BASE = "__BASE__";
async function load(){
  try {
    const s = await (await fetch(BASE + '/api/stats-public')).json();
    document.getElementById('stats').innerHTML = Object.entries(s).map(([k,v])=>`<b>${k}</b>: ${v}`).join(' &nbsp;|&nbsp; ');
  } catch(e) { document.getElementById('stats').innerHTML = 'Stats need admin login — use the Admin Panel button above.'; }
  try {
    const leads = await (await fetch(BASE + '/api/leads-public')).json();
    document.getElementById('leads').innerHTML = '<table><tr><th>Company</th><th>Contact</th><th>Email</th><th>Score</th></tr>' +
      leads.map(l=>`<tr><td>${l.company}</td><td>${(l.contact_name||'')} ${(l.role||'')}</td><td>${l.email||''}</td><td>${l.score}</td></tr>`).join('') + '</table>';
  } catch(e) { document.getElementById('leads').innerHTML = '<p>Log in via Admin Panel to manage leads.</p>'; }
  try {
    const drafts = await (await fetch(BASE + '/api/drafts-public')).json();
    document.getElementById('drafts').innerHTML = drafts.map(d=>`<div class='card'><b>${d.company}</b> — ${d.email||'(no email)'} — <i>${d.status}</i><br><b>${d.subject}</b><pre>${d.body}</pre></div>`).join('') || '<p>No drafts yet.</p>';
  } catch(e) { document.getElementById('drafts').innerHTML = '<p>Log in via Admin Panel to manage drafts.</p>'; }
}
load();
</script></body></html>
"""

ADMIN_HTML = """<!doctype html><html><head><meta charset='utf-8'>
<title>Admin Panel — Free AutoGTM</title>
<style>body{font-family:system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem}
table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid #ddd;padding:.5rem;text-align:left;vertical-align:top}
button{cursor:pointer;margin-right:.4rem} input,textarea,select{width:100%;padding:.4rem;margin:.2rem 0;box-sizing:border-box}
.card{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1rem 0}
.tabs button{padding:.6rem 1rem} .tabs button.active{background:#111;color:#fff}
.admin-btn{display:inline-block;background:#111;color:#fff !important;padding:.6rem 1rem;border-radius:8px;text-decoration:none;font-weight:600}
pre{white-space:pre-wrap}</style></head><body>
<h1>Admin Panel</h1>
<p><a class="admin-btn" href="__BASE__/">&larr; Back to Main Page</a></p>
<div id="login" class="card" style="display:none">
  <h2>Log in</h2>
  <p>Default: <code>admin</code> / <code>changeme123</code> — change it with
  <code>FREE_AUTOGTM_ADMIN_USER</code> / <code>FREE_AUTOGTM_ADMIN_PASSWORD</code>.</p>
  <input id="lu" placeholder="Username" value="admin">
  <input id="lp" type="password" placeholder="Password">
  <button onclick="doLogin()">Log in</button><span id="loginMsg"></span>
</div>
<div id="admin" style="display:none">
  <p>Logged in as <b id="who"></b> <button onclick="doLogout()">Log out</button></p>
  <div class="tabs">
    <button onclick="showTab('leadsTab')" id="tab-leadsTab" class="active">Leads</button>
    <button onclick="showTab('draftsTab')" id="tab-draftsTab">Drafts</button>
    <button onclick="showTab('suppTab')" id="tab-suppTab">Suppression</button>
    <button onclick="showTab('settingsTab')" id="tab-settingsTab">Settings</button>
  </div>
  <div class="card" id="stats"></div>
  <div id="leadsTab">
    <h2>Add lead</h2>
    <div class="card"><input id="nl-company" placeholder="Company *"><input id="nl-website" placeholder="Website">
    <input id="nl-name" placeholder="Contact name"><input id="nl-role" placeholder="Role">
    <input id="nl-email" placeholder="Email"><input id="nl-notes" placeholder="Notes">
    <button onclick="addLead()">Add lead</button></div>
    <h2>Leads</h2><div id="leads"></div>
  </div>
  <div id="draftsTab" style="display:none"><h2>Drafts</h2><div id="drafts"></div></div>
  <div id="suppTab" style="display:none"><h2>Do-not-contact</h2>
    <div class="card"><input id="sup-email" placeholder="Email to suppress"><button onclick="addSupp()">Suppress</button></div>
    <div id="supp"></div></div>
  <div id="settingsTab" style="display:none"><h2>Settings</h2>
    <div class="card"><input id="set-key" placeholder="Key, e.g. seller_name"><input id="set-val" placeholder="Value">
    <button onclick="saveSetting()">Save setting</button></div><div id="settings"></div></div>
</div>
<script>
const BASE = "__BASE__";
let leads=[], drafts=[];
function showTab(id){ ['leadsTab','draftsTab','suppTab','settingsTab'].forEach(t=>{document.getElementById(t).style.display=t===id?'block':'none';document.getElementById('tab-'+t).classList.toggle('active',t===id);}); }
async function api(path, method='GET', body){
  const r = await fetch(BASE + path, {method, headers:{'Content-Type':'application/json'}, body: body?JSON.stringify(body):undefined});
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}
async function doLogin(){
  try { await api('/api/login','POST',{username:document.getElementById('lu').value,password:document.getElementById('lp').value}); location.reload(); }
  catch(e){ document.getElementById('loginMsg').textContent=' Login failed.'; }
}
async function doLogout(){ await api('/api/logout','POST',{}); location.reload(); }
async function load(){
  try { const me = await api('/api/me'); document.getElementById('who').textContent=me.user; document.getElementById('admin').style.display='block'; }
  catch(e){ document.getElementById('login').style.display='block'; return; }
  const s = await api('/api/stats'); document.getElementById('stats').innerHTML = Object.entries(s).map(([k,v])=>`<b>${k}</b>: ${v}`).join(' | ');
  leads = await api('/api/leads');
  document.getElementById('leads').innerHTML = '<table><tr><th>Company</th><th>Contact</th><th>Email</th><th>Score</th><th></th></tr>' +
    leads.map(l=>`<tr><td>${l.company}</td><td>${l.contact_name||''} ${l.role||''}</td><td>${l.email||''}</td><td>${l.score}</td><td><button onclick="delLead(${l.id})">Delete</button></td></tr>`).join('') + '</table>';
  drafts = await api('/api/drafts');
  document.getElementById('drafts').innerHTML = drafts.map(d=>`<div class='card'><b>${d.company}</b> — ${d.email||''} — <i>${d.status}</i><br>
    <input data-f="subject" data-id="${d.id}" value="${d.subject.replace(/"/g,'&quot;')}"><textarea data-f="body" data-id="${d.id}" rows="6">${d.body}</textarea>
    <button onclick="saveDraft(${d.id})">Save</button>
    <button onclick="draftAction(${d.id},'approve')">Approve</button>
    <button onclick="draftAction(${d.id},'reject')">Reject</button></div>`).join('') || '<p>No drafts yet.</p>';
  const supp = await api('/api/suppressed');
  document.getElementById('supp').innerHTML = supp.map(x=>`<div>${x.email} — ${x.reason||''}</div>`).join('') || '<p>None.</p>';
  const settings = await api('/api/settings');
  document.getElementById('settings').innerHTML = Object.entries(settings).map(([k,v])=>`<div><b>${k}</b>: ${v}</div>`).join('') || '<p>No settings yet.</p>';
}
async function addLead(){
  const b={company:document.getElementById('nl-company').value, website:document.getElementById('nl-website').value, contact_name:document.getElementById('nl-name').value, role:document.getElementById('nl-role').value, email:document.getElementById('nl-email').value, notes:document.getElementById('nl-notes').value};
  if(!b.company) return alert('Company is required');
  await api('/api/leads','POST',b); load();
}
async function delLead(id){ if(confirm('Delete this lead?')){ await api('/api/leads/'+id,'DELETE'); load(); } }
async function saveDraft(id){
  const els=document.querySelectorAll(`[data-id="${id}"]`); const b={};
  els.forEach(e=>b[e.dataset.f]=e.value); await api('/api/drafts/'+id,'PUT',b); load();
}
async function draftAction(id, act){ await api(`/api/drafts/${id}/${act}`,'POST',{}); load(); }
async function addSupp(){ await api('/api/suppress','POST',{email:document.getElementById('sup-email').value}); load(); }
async function saveSetting(){ await api('/api/settings','PUT',{key:document.getElementById('set-key').value, value:document.getElementById('set-val').value}); load(); }
load();
</script></body></html>
"""

def _cookie_token(handler):
    cookie = handler.headers.get("Cookie") or ""
    m = re.search(r"session=([^;]+)", cookie)
    return m.group(1) if m else None

class Handler(BaseHTTPRequestHandler):
    def _send(self, body, code=200, ctype="application/json", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200, extra=None):
        self._send(obj, code, "application/json", extra)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode())
        except Exception:
            return {}

    def _user(self):
        return auth.check_session(_cookie_token(self))

    def _require(self):
        user = self._user()
        if not user:
            self._json({"error": "login required"}, 401)
            return None
        return user

    def _conn(self):
        return connect(DB_PATH)

    # ---- routing ----
    def do_GET(self):
        path = strip_base(urlparse(self.path).path)
        if path == "/":
            self._send(render(MAIN_HTML), 200, "text/html")
            return
        if path == "/admin":
            self._send(render(ADMIN_HTML), 200, "text/html")
            return
        conn = self._conn()
        try:
            # Public read-only views for the main page (no editing).
            if path == "/api/stats-public":
                self._json(stats(conn)); return
            if path == "/api/leads-public":
                self._json(list_leads(conn)); return
            if path == "/api/drafts-public":
                self._json(list_drafts(conn)); return
            user = self._require()
            if not user:
                return
            if path == "/api/me":
                self._json({"user": user}); return
            if path == "/api/stats":
                self._json(stats(conn)); return
            if path == "/api/leads":
                self._json(list_leads(conn)); return
            if path == "/api/drafts":
                self._json(list_drafts(conn)); return
            if path == "/api/suppressed":
                self._json(list_suppressed(conn)); return
            if path == "/api/campaigns":
                self._json(list_campaigns(conn)); return
            if path == "/api/settings":
                rows = conn.execute("SELECT key, value FROM settings").fetchall()
                self._json({r["key"]: r["value"] for r in rows}); return
            if path == "/api/export":
                rows = list_drafts(conn)
                lines = ["company,contact_name,email,subject,status"]
                for r in rows:
                    lines.append(",".join(f'"{str(r.get(k, "")).replace(chr(34), chr(34)*2)}"' for k in ["company", "contact_name", "email", "subject", "status"]))
                self._send("\n".join(lines), 200, "text/csv"); return
            self._json({"error": "not found"}, 404)
        finally:
            conn.close()

    def do_POST(self):
        path = strip_base(urlparse(self.path).path)
        body = self._read_json()
        cookie_path = base_path() or "/"
        if path == "/api/login":
            if auth.check_login(body.get("username", ""), body.get("password", "")):
                token = auth.create_session(body["username"])
                self._json({"ok": True, "user": body["username"]}, 200,
                           {"Set-Cookie": f"session={token}; HttpOnly; Path={cookie_path}; SameSite=Lax"})
            else:
                self._json({"error": "invalid login"}, 401)
            return
        if path == "/api/logout":
            auth.destroy_session(_cookie_token(self))
            self._json({"ok": True}, 200, {"Set-Cookie": f"session=; HttpOnly; Path={cookie_path}; Max-Age=0"})
            return
        conn = self._conn()
        try:
            user = self._require()
            if not user:
                return
            if path == "/api/leads":
                if not body.get("company"):
                    self._json({"error": "company required"}, 400); return
                website = body.get("website", "")
                lead_id = add_lead(conn, {
                    "company": body["company"], "website": website,
                    "domain": body.get("domain") or _domain(website),
                    "contact_name": body.get("contact_name", ""), "role": body.get("role", ""),
                    "email": body.get("email", ""), "notes": body.get("notes", ""),
                    "score": int(body.get("score", 20)),
                })
                self._json({"id": lead_id}, 201); return
            if path == "/api/suppress":
                suppress(conn, body.get("email", ""), body.get("reason", "opt-out"))
                self._json({"ok": True}); return
            if path == "/api/campaigns":
                self._json({"id": add_campaign(conn, body.get("name", "Campaign"))}, 201); return
            m = re.match(r"^/api/drafts/(\d+)/(approve|reject)$", path)
            if m:
                set_draft_status(conn, int(m.group(1)), "approved" if m.group(2) == "approve" else "rejected")
                self._json({"ok": True}); return
            self._json({"error": "not found"}, 404)
        finally:
            conn.close()

    def do_PUT(self):
        path = strip_base(urlparse(self.path).path)
        body = self._read_json()
        conn = self._conn()
        try:
            if not self._require():
                return
            m = re.match(r"^/api/leads/(\d+)$", path)
            if m:
                allowed = {"company", "website", "domain", "contact_name", "role", "email", "notes", "score", "status"}
                update_lead(conn, int(m.group(1)), **{k: v for k, v in body.items() if k in allowed})
                self._json({"ok": True}); return
            m = re.match(r"^/api/drafts/(\d+)$", path)
            if m:
                update_draft_fields(conn, int(m.group(1)), **body)
                self._json({"ok": True}); return
            if path == "/api/settings":
                if body.get("key"):
                    set_setting(conn, body["key"], str(body.get("value", "")))
                    self._json({"ok": True}); return
                self._json({"error": "key required"}, 400); return
            self._json({"error": "not found"}, 404)
        finally:
            conn.close()

    def do_DELETE(self):
        path = strip_base(urlparse(self.path).path)
        conn = self._conn()
        try:
            if not self._require():
                return
            m = re.match(r"^/api/leads/(\d+)$", path)
            if m:
                delete_lead(conn, int(m.group(1)))
                self._json({"ok": True}); return
            self._json({"error": "not found"}, 404)
        finally:
            conn.close()

    def log_message(self, *args):
        pass

def serve(port=8000, host="127.0.0.1"):
    if auth.is_default_password():
        print("WARNING: using default admin password 'changeme123'.")
        print("Set FREE_AUTOGTM_ADMIN_USER / FREE_AUTOGTM_ADMIN_PASSWORD before exposing this.")
    print(f"Free AutoGTM: http://{host}:{port}{base_path()}/  — Admin Panel button on the main page -> {base_path()}/admin")
    print("Keep this terminal open — closing it stops the page.")
    try:
        ThreadingHTTPServer((host, port), Handler).serve_forever()
    except OSError as e:
        print(f"\nERROR: could not start on port {port}: {e}")
        print(f"Try: python3 cli.py serve --port {port + 1}")
        raise SystemExit(1)
