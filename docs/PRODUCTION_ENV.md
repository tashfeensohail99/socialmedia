# Production Environment Variables

Reference of env vars set in Railway for each service. Anything marked
**required** must be set before the service starts; anything optional has a
sensible default.

## Per-service variables

### `backend` service

| Variable | Required | Source / Example |
|---|---|---|
| `SMA_DATABASE_URL` | **yes** | `${{Postgres.DATABASE_URL}}` (auto-injected from Postgres addon) |
| `DEPLOYMENT_MODE` | **yes** | `multi_tenant` |
| `MASTER_KEY` | **yes** | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `JWT_SECRET` | **yes** | `openssl rand -hex 32` |
| `PUBLIC_BASE_URL` | **yes** | `https://api.summitautomates.com` (used to build OAuth callback URLs in emails) |
| `CORS_ALLOWED_ORIGINS` | **yes** | `https://app.summitautomates.com,https://summitautomates.com` |
| `WHOP_WEBHOOK_SECRET` | **yes** for SaaS | From whop.com → product → Webhooks. Without this, webhooks are rejected in multi_tenant mode. |
| `RESEND_API_KEY` | **yes** for SaaS | From resend.com. Without it, magic-link URLs are logged to stdout instead of emailed. |
| `EMAIL_FROM` | **yes** for SaaS | `Summit Automates <noreply@summitautomates.com>` (domain must be verified in Resend) |
| `META_APP_ID` | yes for IG+FB OAuth | From your Meta App dashboard |
| `META_APP_SECRET` | yes for IG+FB OAuth | From your Meta App dashboard |
| `GOOGLE_CLIENT_ID` | yes for YouTube OAuth | From Google Cloud Console → APIs & Services → Credentials |
| `GOOGLE_CLIENT_SECRET` | yes for YouTube OAuth | Same |
| `TIKTOK_CLIENT_KEY` | yes for TikTok | developers.tiktok.com → your app |
| `TIKTOK_CLIENT_SECRET` | yes for TikTok | Same |
| `LINKEDIN_CLIENT_ID` | yes for LinkedIn | developer.linkedin.com → your app |
| `LINKEDIN_CLIENT_SECRET` | yes for LinkedIn | Same |
| `LOG_LEVEL` | no | default `INFO`. Set to `DEBUG` to see every API call. |

### `worker` service

Same vars as `backend` except:
- No `CORS_ALLOWED_ORIGINS` (it doesn't serve HTTP)
- All the OAuth `_CLIENT_*` vars are needed because the worker calls social posters too

The simplest setup: in Railway, set these variables at the **project level**
so both `backend` and `worker` inherit them automatically. Then the per-service
config only needs to override what differs.

### `frontend` service

| Variable | Required | Source / Example |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | **yes** | `https://api.summitautomates.com` (baked into the build via `buildArgs`) |
| `NODE_ENV` | no | `production` (Railway sets automatically) |

That's it. The frontend is a thin shell — all real state comes from the API.

## Generating the secrets

Before first deploy, generate these locally and paste them into Railway:

```powershell
# MASTER_KEY (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# JWT_SECRET
openssl rand -hex 32
```

These two values must stay constant across deploys forever. If `MASTER_KEY`
changes, every encrypted credential and OAuth token in the DB becomes
unreadable. If `JWT_SECRET` changes, all logged-in users are logged out.
**Store them in a password manager.**

## Where to set env vars in Railway

1. Open your Railway project
2. Click the service (e.g. `backend`)
3. Variables tab → "Add variable"
4. Paste name + value, click Add

For shared vars across services, use **Project Variables** (Project Settings →
Variables) — those get inherited by all services automatically.

## CORS troubleshooting

If you see "blocked by CORS policy" in the browser console:

1. Confirm `CORS_ALLOWED_ORIGINS` on `backend` matches the frontend's actual
   domain exactly (including `https://`, no trailing slash).
2. After changing the env var, Railway redeploys the backend automatically.
   Hard-reload the frontend (Ctrl+Shift+R) to drop the stale preflight cache.
3. Multiple domains separated by commas, no spaces around the commas.

## Webhook URL configuration

After Railway gives you the `backend` service's public URL, configure these in
external dashboards:

| Service | Webhook URL to register |
|---|---|
| Whop | `https://api.summitautomates.com/api/webhooks/whop` |
| Meta OAuth callback | `https://api.summitautomates.com/api/oauth/meta/callback` |
| Google OAuth callback | `https://api.summitautomates.com/api/oauth/youtube/callback` |
| TikTok OAuth callback | `https://api.summitautomates.com/api/oauth/tiktok/callback` |
| LinkedIn OAuth callback | `https://api.summitautomates.com/api/oauth/linkedin/callback` |
