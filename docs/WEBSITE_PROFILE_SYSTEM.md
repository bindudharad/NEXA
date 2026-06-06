# Nexa Website Profile Memory

Nexa can learn website login and action flows once, store encrypted credentials, and reuse them through approved chat commands.

## First-Time Flow

1. User says `Open Contineo`.
2. If no profile exists, Nexa returns `requires_profile=true` and creates a notification asking for the website URL.
3. Submit the URL to `/api/website-profiles/analyze`.
4. Nexa detects forms, login fields, buttons, dropdowns, captcha markers, and navigation structure.
5. Save the profile through `/api/website-profiles`.

## Stored Data

Nexa stores:

- `website_profiles`
- `website_credentials`
- `website_actions`
- `website_sessions`
- `website_history`

Credential payloads are encrypted with Fernet. The key comes from `NEXA_CREDENTIAL_ENCRYPTION_KEY` when configured, otherwise Nexa creates a local key at `backend/.secrets/nexa-credentials.key`.

## Automation

`POST /api/website-profiles/{id}/auto-login` opens the website with Playwright, fills mapped credentials, submits the login form, verifies success, captures a screenshot, and stores encrypted session cookies.

## Retry And Monitoring

Default retry policy:

- `max_retries`: 5
- retryable conditions: server busy, timeout, network error, 503, 504, connection failure

If all retries fail, Nexa sends a `Website unavailable` notification and can continue monitoring through:

- `PUT /api/website-profiles/{id}/monitoring`
- `POST /api/website-profiles/monitor/check`

The backend also starts a background website monitoring worker with Nexa.

## Chat Integration

Commands such as `Open Contineo`, `Show KCET Result`, `Check College Results`, and `Download Marks Card` route through the task approval system before website automation runs.
