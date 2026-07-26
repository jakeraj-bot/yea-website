# Youth Education Academy Website

Django marketing site for Youth Education Academy (YEA).

## Local development

### 1. Activate the virtual environment

```bash
cd ~/Projects/yea-website
source venv/bin/activate
```

### 2. Run migrations

```bash
python manage.py migrate
```

### 3. Start the development server

```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser.

### 4. Stop the server

Press `Ctrl + C` in Terminal.

## Project structure

- `core/` — Home, About, Contact, Apply, Safety
- `programs/` — After-school, Summer camp, Location pages
- `partnerships/` — Partnerships page
- `donations/` — Donate page
- `templates/` — HTML templates
- `static/` — CSS and JavaScript

## Environment variables (production)

Set these on your host (Render), not in Git:

- `DJANGO_SECRET_KEY` — random secret string
- `DJANGO_DEBUG` — `False`
- `DJANGO_ALLOWED_HOSTS` — `yeanj.org,www.yeanj.org`

## Deployment

Deployment to Render and DNS cutover from WordPress.com will be covered in Part 4 and Part 5 of the setup walkthrough.
