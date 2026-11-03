# Deploy on MetroVPS Grid (grid.metrovps.com) — worker process

This is the deployment route for the Grid panel, not the raw-VPS
systemd/nginx route in `deploy/README.md`. Use this one if your site
lives in the Grid panel shown at grid.metrovps.com.

## The key insight

Grid has no Python preset. It has Node.js, Custom, Laravel, and PHP.
**Custom is the route for this Python tool** — it lets you type any
startup command, and Grid's HTTP Proxy forwards your domain to that
worker process.

## Before you launch the worker

1. Get the code onto the site first, via the panel's **GitHub** tab
   (connect a repo containing this project) or via **Files** (upload
   the zip and extract it). Note the folder the code ends up in —
   you need it for Working directory below.
2. Do NOT launch the worker on your main site `iftekhar.ami.bd` if
   that site is already live. Create a separate site/subdomain for
   the tool first (Domains tab), e.g. `tool.iftekhar.ami.bd`, and
   launch the worker there.

## For iftekhar.ami.bd/tool (subpath, not subdomain)

This is the version the site owner chose. The app now supports a
base path, so it works whether Grid strips the `/tool` prefix when
proxying or forwards it through — both are handled.

1. Extract `free-autogtm.zip` in `public_html` first, so you have
   `public_html/free-autogtm/cli.py`. Do NOT delete your main site's
   `index.html`, `admin.html`, etc. — the tool lives in its own
   subfolder and its admin is `/tool/admin`, not `/admin`.
2. In Advanced → Launch worker process, use:
   - **Automatic (Production)**, **Type: Custom**, **HTTP Proxy: ON**
   - **Startup command:**
     ```
     FREE_AUTOGTM_BASE_PATH=/tool python3 cli.py serve --host 127.0.0.1 --port 8000
     ```
     With an admin login (recommended):
     ```
     FREE_AUTOGTM_BASE_PATH=/tool FREE_AUTOGTM_ADMIN_USER=admin FREE_AUTOGTM_ADMIN_PASSWORD=your-password python3 cli.py serve --host 127.0.0.1 --port 8000
     ```
   - **Working directory:** the folder containing `cli.py`,
     e.g. `public_html/free-autogtm`
   - **Path:** `/tool`
   - **Port:** `8000`
3. Open `https://iftekhar.ami.bd/tool` — the tool's main page, with
   its Admin Panel button linking to `/tool/admin`. Your main site
   at `/` and its own `/admin.html` stay untouched.

## Fill in "Launch worker process" like this (general case)

- **Automatic (Production)** — leave this selected. The worker will
  start automatically and restart if it exits.
- **Type: Custom** — do NOT leave it on Node.js. Node.js expects
  `npm start` and a Node app; this app is Python.
- **Startup command:**
  ```
  python3 cli.py serve --host 127.0.0.1 --port 8000
  ```
  Add admin login like this if you want it (recommended):
  ```
  FREE_AUTOGTM_ADMIN_USER=admin FREE_AUTOGTM_ADMIN_PASSWORD=your-password python3 cli.py serve --host 127.0.0.1 --port 8000
  ```
  Change `your-password` — do not use `changeme123` in production.
- **Working directory:** the folder containing `cli.py`
  (for example, the extracted `free-autogtm` folder — check the
  Files tab for the exact path).
- **HTTP Proxy: ON** — this is what forwards your domain to the
  worker. Leave it on.
- **Path:** `/`
- **Port:** `8000` — this must match the `--port` in the startup
  command above.

Then launch it, open the site's domain, and click the **Admin Panel**
button on the main page to log in at `/admin`.

## If it does not start

Open the panel's **Logs** tab and look for the first error:

- `python3: command not found` — the worker container does not have
  Python. Tell Muse that exact error: the backend would then need a
  Node.js port, or a different host that provides Python.
- `Address already in use` — change both the `--port` and the Port
  field to another free port, e.g. `8001`, and relaunch.
- `No such file or directory: cli.py` — Working directory is wrong.
  Fix it to the folder that actually contains `cli.py`.
- Anything else — copy the log lines and send them to Muse.

After any code change, use **Restart container** (Quick links on the
site page) to restart the worker with the new code.
