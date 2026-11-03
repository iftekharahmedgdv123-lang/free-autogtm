# Deploy Free AutoGTM on Render (Python host)

Use this when the MetroVPS Grid worker will not run Python. Render
deploys directly from the GitHub repo, so no manual file upload is needed.

## 1. Create the service

1. Go to https://dashboard.render.com and sign in (create a free account
   if you do not have one).
2. New + → Web Service → Build and deploy from a Git repository →
   Next → choose the `free-autogtm` repository, branch `main`.
3. Render reads `deploy/render.yaml` in this repo, or use these settings
   manually:
   - Environment: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python3 -u cli.py serve --host 0.0.0.0 --port $PORT`
   - Instance Type: Free
4. In Environment Variables, add:
   - `FREE_AUTOGTM_ADMIN_USER` = `admin` (or your own username)
   - `FREE_AUTOGTM_ADMIN_PASSWORD` = a strong password of your own.
     Never put this password in chat, in the repo, or in `render.yaml`
     (it is marked `sync: false` there for that reason).
   - Do NOT set `FREE_AUTOGTM_BASE_PATH` on Render. The tool runs at
     the Render service root, so the main page is `/` and admin is
     `/admin` on the Render URL — not `/tool`.
5. Create Web Service and wait for the deploy to finish. Render will
   give you a URL like `https://free-autogtm-xxxx.onrender.com`.

## 2. Verify

- Open the Render URL — you should see "Free AutoGTM".
- Open `<render-url>/admin` and sign in with the admin user/password
  you set in step 4.
- If the page does not load, open the Render service → Logs and look
  for the `Free AutoGTM: http://0.0.0.0:$PORT/` start line or an error.

## 3. Link it from your main site

On https://iftekhar.ami.bd, add a button linking to the Render URL
(and a second link to `<render-url>/admin` for the Admin Panel).
The file `website-button-snippet.html` in this repo shows the button
markup — replace its `https://iftekhar.ami.bd/tool` link with your
Render URL. Your main site itself stays untouched; the tool is simply
hosted elsewhere and linked from it.

## Notes and limits

- Render Free: the service sleeps after inactivity, so the first
  visit after a while can take ~30-60 seconds to wake up.
- SQLite storage (`data.db`) on a free Render service is ephemeral:
  leads and drafts can be lost on a redeploy or restart. Export
  important drafts/leads to CSV from the admin panel regularly.
  For durable storage, upgrade to a paid Render instance with a
  persistent disk, or move `data.db` to an external database later.
- The Grid `/tool` worker is no longer needed once Render is live.
  You can delete the Grid worker so it does not keep returning 503
  for `/tool`, or keep it stopped — do not set its Proxy Path to `/`.
