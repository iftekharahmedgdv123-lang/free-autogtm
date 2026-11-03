# Deploy Free AutoGTM to a MetroVPS VPS

**Do not put this dashboard on the public internet without a password.**
It has no login of its own — the password protection below (nginx
`auth_basic`) is what keeps your leads private. If you skip it, anyone
who finds the URL can see and approve your drafts.

## What this deploys

- The app in `/opt/free-autogtm`, run by systemd, restarting on boot
- nginx in front of it, proxying to `127.0.0.1:8000`
- A username/password prompt (nginx basic auth) before the dashboard loads
- Nothing is changed on your main site. Use a subdomain for the tool,
  e.g. `tool.iftekhar.ami.bd` — see step 4. Do not point the tool at
  `iftekhar.ami.bd` itself unless you want to replace that site.

## Prerequisites

- A MetroVPS VPS with Ubuntu/Debian, and SSH (root) access to it.
  MetroVPS's DashMetro panel is for rebooting / rebuilding the VPS —
  it is not where you upload website files. The install itself happens
  over SSH.
- The VPS IP address (shown in DashMetro / your MetroVPS welcome email).
- A DNS A record for your chosen subdomain pointing at that VPS IP.
  Add it wherever `ami.bd` DNS is managed, before step 5.

## Steps (from your Mac Terminal)

### 1. Upload the project to the VPS

```bash
cd ~/Downloads/free-autogtm
scp free-autogtm.zip root@YOUR_VPS_IP:/tmp/
```

Replace `YOUR_VPS_IP` with the real IP. If your VPS user is not `root`,
use that username instead.

### 2. SSH in and run the installer

```bash
ssh root@YOUR_VPS_IP
cd /tmp && unzip -o free-autogtm.zip
cd free-autogtm && bash deploy/install.sh
```

The installer will:
- install Python 3 and nginx (if missing)
- copy the app to `/opt/free-autogtm`
- ask you to choose a dashboard username and password
- install the systemd service and nginx site
- start the app

### 3. Point nginx at your subdomain

Edit the site file the installer created:

```bash
nano /etc/nginx/sites-available/free-autogtm
```

Change `server_name tool.iftekhar.ami.bd;` to the subdomain you actually
created the DNS record for, then:

```bash
nginx -t && systemctl reload nginx
```

### 4. (Optional, recommended) HTTPS

Once DNS has propagated and the site loads over HTTP:

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d tool.iftekhar.ami.bd
```

### 5. Use it

Open `https://tool.iftekhar.ami.bd` (or your subdomain), log in with the
username/password you set in step 2, and use the dashboard as normal.

## Admin panel

The main page has a separate **Admin Panel** button linking to `/admin`.
Log in there with the admin user/password set in
`/etc/systemd/system/free-autogtm.service` (change the default
`changeme123` before going live, then `systemctl daemon-reload &&
systemctl restart free-autogtm`).

To add the same button to your main website, copy
`website-button-snippet.html` from the project and change its link to
your real admin address, e.g. `https://tool.iftekhar.ami.bd/admin`.

## Updating later

```bash
scp free-autogtm.zip root@YOUR_VPS_IP:/tmp/
ssh root@YOUR_VPS_IP
cd /tmp && unzip -o free-autogtm.zip
cp -r free-autogtm/free_autogtm free-autogtm/cli.py /opt/free-autogtm/
systemctl restart free-autogtm
```

Your data lives in `/opt/free-autogtm/data.db` and is not overwritten
by an update (do not delete it).

## If you cannot SSH

If you do not have SSH/root access to the VPS, I cannot install this
from here — and you should not paste a root password into chat.
In that case, send the installer files to whoever manages the VPS, or
ask MetroVPS support to enable SSH access for you, and then follow the
steps above.
