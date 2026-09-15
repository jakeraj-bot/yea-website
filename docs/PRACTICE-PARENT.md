# Practice parent portal

A sandbox parent account so you can click everything a parent can click — including **Pay now** — without touching a live family.

This is **not** Parent view. Parent view (on a real family) only shows the screens and does not charge a card.

## Open it

1. Sign in to portal admin.
2. Click **Open practice parent** in the header, on Overview, or on Parent comms.
3. You are signed in as the Practice family. A green banner says: *Practice parent — test payments only, not a real family.*
4. Click **Back to admin** when you are done.

## Login if you want to type it

- URL: `/portal/login/`
- Username: `practiceparent`
- Password: `PracticeFamily2026!`

You do not need to remember that password if you use **Open practice parent**.

## What you can do here

- Pay now (Stripe **test** checkout when test keys are set, or a clear test receipt if they are not)
- Add and delete emergency contacts
- Change profile, receipts, Help, Spanish
- Same parent menu as a real family

Payments never use live Stripe keys. Receipts show **Youth Education Academy**.

## Production

Hidden on yeanj.org unless Settings → Billing permissions → **Show Practice parent**. Even then, practice charges stay on the sandbox family and only use Stripe test mode.
