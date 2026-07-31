#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Free Render has no Shell — set PORTAL_BOOTSTRAP_ON_DEPLOY=True in Environment to run on deploy.
if [ "${PORTAL_BOOTSTRAP_ON_DEPLOY}" = "True" ]; then
  python manage.py bootstrap_portal
fi

if [ "${PORTAL_CLEAR_MEMBERS_ON_DEPLOY}" = "True" ]; then
  python manage.py clear_portal_members --yes
fi

if [ -n "${PORTAL_ADMIN_USERNAME}" ] && [ -n "${PORTAL_ADMIN_PASSWORD}" ]; then
  python manage.py create_portal_admin \
    --username "${PORTAL_ADMIN_USERNAME}" \
    --password "${PORTAL_ADMIN_PASSWORD}" \
    --name "${PORTAL_ADMIN_NAME:-YEA Admin}"
fi

if [ -n "${WEBSITE_ADMIN_USERNAME}" ] && [ -n "${WEBSITE_ADMIN_PASSWORD}" ]; then
  python manage.py create_website_admin \
    --username "${WEBSITE_ADMIN_USERNAME}" \
    --password "${WEBSITE_ADMIN_PASSWORD}" \
    --email "${WEBSITE_ADMIN_EMAIL:-}"
fi
