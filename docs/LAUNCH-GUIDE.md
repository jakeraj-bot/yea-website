# Youth Education Academy — Launch guide

Step-by-step checklist to go live on **yeanj.org**, turn on email, secure the site, and get found on Google in Paterson and surrounding areas.

Work through the sections **in order**.

---

## Part 1 — Get the site live (Render + DNS)

### What you need before starting

- GitHub account (free): https://github.com
- Render account (free to start): https://render.com
- Access to **yeanj.org** DNS (where you bought the domain — WordPress.com, GoDaddy, etc.)
- Stripe live keys (you already have these)
- About 1–2 hours for first deploy

### Step 1: Put the code on GitHub

1. Open Terminal and run:

```bash
cd ~/Projects/yea-website
git init
git add .
git commit -m "Initial YEA website"
```

2. On GitHub, click **New repository** → name it `yea-website` → **Create** (no README).

3. Connect and push (replace `YOUR_GITHUB_USERNAME`):

```bash
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/yea-website.git
git push -u origin main
```

**Important:** `.env` is gitignored — secrets stay on your Mac and Render only.

---

### Step 2: Create the site on Render

1. Log in to **Render** → **New +** → **Blueprint**.
2. Connect your GitHub account and select the **yea-website** repo.
3. Render reads `render.yaml` and creates:
   - A **Web Service** (your Django site)
   - A **PostgreSQL database** (applications, enrollments, drop-in bookings — **not lost on redeploy**)
4. Click **Apply**.

Wait for the first deploy (5–10 minutes). You’ll get a URL like:

`https://yea-website-xxxx.onrender.com`

Open it — the site should load (CSS included).

---

### Step 3: Add environment variables on Render

In Render → your **yea-website** service → **Environment**:

| Key | Value |
|-----|--------|
| `DJANGO_SECRET_KEY` | Generate: run `python -c "import secrets; print(secrets.token_urlsafe(50))"` on your Mac |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `yeanj.org,www.yeanj.org,your-app.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://yeanj.org,https://www.yeanj.org` |
| `SITE_URL` | `https://yeanj.org` |
| `CONTACT_EMAIL` | `info@yeanj.org` |
| `DEFAULT_FROM_EMAIL` | `info@yeanj.org` |
| `STRIPE_PUBLIC_KEY` | your `pk_live_...` |
| `STRIPE_SECRET_KEY` | your **new** rotated `sk_live_...` (see Part 4) |

`DATABASE_URL` is set automatically from the Postgres add-on.

Click **Save Changes** → Render redeploys.

---

### Step 4: Create your admin user on Render

Render → **Shell** tab (or run locally with `DATABASE_URL` exported):

```bash
python manage.py createsuperuser
```

Use the same username/password you use locally, or a new one for production.

---

### Step 5: Point yeanj.org to Render (DNS)

Where you manage **yeanj.org** DNS (WordPress.com, Cloudflare, etc.):

**Option A — Root domain (yeanj.org)**

| Type | Name | Value |
|------|------|--------|
| A | `@` | Render’s IP (shown in Render → Custom Domains) |
| OR ALIAS/ANAME | `@` | your-app.onrender.com |

**Option B — www**

| Type | Name | Value |
|------|------|--------|
| CNAME | `www` | your-app.onrender.com |

In **Render** → Web Service → **Settings** → **Custom Domains**:

1. Add `yeanj.org`
2. Add `www.yeanj.org`
3. Enable **Redirect www to apex** (or pick one canonical URL)

DNS can take **15 minutes to 48 hours**. Render shows a green check when SSL is ready.

---

### Step 6: After DNS works — smoke test

- [ ] Homepage loads at https://yeanj.org
- [ ] `/apply/` enrollment works
- [ ] `/drop-in/` loads
- [ ] `/donate/` Stripe checkout opens
- [ ] `/admin/` login works
- [ ] Footer **Staff admin** link works

---

### SEO — help families find you on Google

The site now includes:

- **Page titles & descriptions** with “Paterson”, “after-school”, “summer camp”, “Caldwell”
- **sitemap.xml** — https://yeanj.org/sitemap.xml
- **robots.txt** — https://yeanj.org/robots.txt
- **Structured data** (organization + locations) for Google

**After the site is live, do these (one-time, ~30 min):**

1. **Google Business Profile** (free) — https://business.google.com  
   Create a profile for Youth Education Academy / each location you want on Maps.

2. **Google Search Console** (free) — https://search.google.com/search-console  
   - Add property `https://yeanj.org`  
   - Verify ownership (DNS TXT record or HTML file)  
   - Submit sitemap: `https://yeanj.org/sitemap.xml`

3. **Bing Webmaster Tools** (optional) — same sitemap URL.

4. **Keep content location-specific** — program pages already mention Paterson, School 18, Caldwell, etc. Google ranks these over time (weeks, not overnight).

5. **Partnerships** — ask partners to link to yeanj.org from their sites (helps local search).

---

## Part 2 — Turn on real email

### If you use Google Workspace for info@yeanj.org

1. Log in to Google Admin → the account that owns **info@yeanj.org**.

2. Enable **2-Step Verification** on that account (required for app passwords).

3. Create an **App Password**:  
   Google Account → Security → App passwords → name it `YEA Website` → copy the 16-character password.

4. On **Render**, add environment variables:

| Key | Value |
|-----|--------|
| `EMAIL_HOST` | `smtp.gmail.com` |
| `EMAIL_PORT` | `587` |
| `EMAIL_HOST_USER` | `info@yeanj.org` |
| `EMAIL_HOST_PASSWORD` | the app password (no spaces) |
| `EMAIL_USE_TLS` | `True` |
| `DEFAULT_FROM_EMAIL` | `info@yeanj.org` |

5. Save → Render redeploys.

6. **Test:** submit the contact form and a test enrollment. Check **info@yeanj.org** inbox (and spam).

### If email is NOT Google

Ask your email host for **SMTP settings** (host, port, username, password) and use the same variable names on Render.

---

## Part 3 — Staff setup & daily use (do together)

### Enrollment applications

- **Admin** → **Enrollment applications** — one row **per child**; same family linked by **family group**
- **Print application** link on each row (staff login required)

### Drop-in

1. **Drop-in family profiles** → approve new families (Action: “Approve selected families…”)
2. **Drop-in day capacities** → add dates + locations + max spots
3. **Drop-in bookings** — see who paid
4. **Drop-in waitlist entries** — ordered by request time when a day is full
5. **Daily roster:** https://yeanj.org/drop-in/roster/ (staff login)

### Contact messages

- **Admin** → **Contact messages**

### Donations

- Stripe Dashboard — https://dashboard.stripe.com — for payment records

---

## Part 4 — Security cleanup

Do these **before** or **right when** you go live:

| Task | How |
|------|-----|
| **New Django secret key** | Generate (Step 3 above) — never reuse the dev default |
| **Rotate Stripe secret key** | Stripe Dashboard → Developers → API keys → Roll secret key → update Render env |
| **DEBUG off** | `DJANGO_DEBUG=False` on Render (already in render.yaml) |
| **HTTPS** | Automatic on Render + custom domain |
| **Strong admin password** | Use a password manager |
| **Never commit `.env`** | Already gitignored |

The site enables HSTS, secure cookies, and CSRF protection when `DEBUG=False`.

**Staff admin footer link** — stays visible as you requested.

**Additional staff logins later** — Admin → Users → Add user → check **Staff status** (we can walk through this when you’re ready).

---

## Part 5 — Parent portal (later)

Not required for launch. Planned features:

- Log in to view signed policies
- See enrollment status
- Billing history / payment portal link
- Update emergency contact

We’ll scope this after Parts 1–4 are stable.

---

## Quick reference

| What | URL |
|------|-----|
| Public site | https://yeanj.org |
| Staff admin | https://yeanj.org/admin/ |
| Drop-in roster | https://yeanj.org/drop-in/roster/ |
| Apply | https://yeanj.org/apply/ |
| Sitemap | https://yeanj.org/sitemap.xml |

---

## Need help on a step?

Tell me which part you’re on (e.g. “Step 2 Render” or “DNS on WordPress”) and we’ll do it together in the next message.
