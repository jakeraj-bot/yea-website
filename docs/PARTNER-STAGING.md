# Partner staging overview

**Full deploy steps:** see **[DEPLOY-PARTNER-STAGING.md](./DEPLOY-PARTNER-STAGING.md)** — push to GitHub, Render blueprint, env vars, seed, share link.

## What “staging” means

| | Production (later) | Partner staging (now) |
|---|---|---|
| URL | `https://yeanj.org` | `https://yea-website-staging.onrender.com` |
| DNS | Public domain | **No change to yeanj.org** |
| Portals | Live | **Live** (`PORTAL_PREVIEW_MODE=False`) |
| UI | Production polish | **Same polish** — no preview/demo banners |
| Database | Production Postgres | **Separate** staging database |
| Google indexing | Allowed | **Blocked** (`STAGING_SITE=True`, noindex meta) |

Your partner gets a private link. The public website stays on WordPress until you switch DNS.

---

## Quick reference after deploy

- **Site:** `https://yea-website-staging.onrender.com`
- **Portals:** `/portal/`
- **Seed (once):** `python manage.py seed_portal` in Render Shell
- **Test logins** (share privately — not shown on the site):
  - Parent: `jakeraj` / `JacobsFamily2026!`
  - Staff: `staff18` / `StaffSchool18!`
  - Admin: `/portal/admin/dashboard/`

---

## Partner feedback checklist

- [ ] Public website — homepage, programs, enrollment pages
- [ ] Admin portal — units, programs, billing, comms
- [ ] Staff portal — attendance, families, agency
- [ ] Parent portal — billing, policies, drop-in
- [ ] Phone Home Screen app — YEA Parent Portal (Add to Home Screen)
- [ ] Anything that still feels like a “demo” or placeholder

---

## YEA Parent Portal (Home Screen app)

Parents add **YEA Parent Portal** from Safari or Chrome (Share → Add to Home Screen / Install app). No Apple Developer account is needed for this.

A later store wrap can reuse the same URLs, name, and icons. Keep Stripe Checkout in the **system browser** (not an in-app webview). Apple Developer is $99/year and Google Play is $25 one-time when you ask to list store apps.

---

## Local quick demo (optional)

```bash
cd ~/Projects/yea-website
export PORTAL_PREVIEW_MODE=False
export STAGING_SITE=True
./venv/bin/python manage.py migrate
./venv/bin/python manage.py seed_portal
./venv/bin/python manage.py runserver 0.0.0.0:8000
```

Use ngrok or Cloudflare Tunnel to share temporarily — same env vars as Render staging.

---

## Production launch

Follow **`docs/LAUNCH-GUIDE.md`** when ready for yeanj.org. Keep staging for QA until launch.
