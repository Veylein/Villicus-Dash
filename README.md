
# Villicus Website

This folder contains the Villicus configuration dashboard (FastAPI + Jinja2) used to connect staff/admin users and configure guild settings for the Villicus Discord bot.

## Features
- Discord OAuth login (server side) for admin access
- Per-guild configuration: warn thresholds, auto-punish action, theme, accent color
- Staff-role management (assign role IDs → staff levels)
- Live save endpoints that call the bot's API (requires bot-side `BOT_API_KEY`)

## Prerequisites
- Python 3.10+
- The bot API running and reachable (see `BOT_API_URL`)
- Redis (optional, recommended for production session storage)

## Environment
Copy `.env.example` to `.env` and fill values:

- `DISCORD_CLIENT_ID` — Discord OAuth application client ID
- `DISCORD_CLIENT_SECRET` — Discord OAuth client secret
- `REDIRECT_URI` — OAuth redirect (e.g. `https://yourdomain.com/callback`)
- `BOT_API_URL` — Bot API base, e.g. `http://bot:5000` or `https://api.example.com`
- `BOT_API_KEY` — Shared secret used by the website to call the bot API
- `SESSION_SECRET` — Random secret for signing session cookies

## Install

Install dependencies (prefer a venv):

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r ../requirements.txt
```

## Run locally

Start the site with uvicorn:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` and sign in with Discord to access the dashboard.

## Deployment (GitHub / Heroku / Railway)

Example `Procfile` (Heroku / Railway):

```
web: uvicorn main:app --host=0.0.0.0 --port=${PORT:-8000}
```

Notes:
- Ensure `SESSION_SECRET` and `BOT_API_KEY` are set in the deployment environment.
 - Ensure `SESSION_SECRET`, `BOT_API_KEY` and optionally `BOT_JWT_SECRET` are set in the deployment environment.
- Use HTTPS in production and set `resp.set_cookie(..., secure=True)` in `main.py`.
- For production session storage, replace the signed cookie with a server-side session (Redis recommended).

### GitHub Pages (static frontend)

You can publish a static marketing frontend (hero and docs) to GitHub Pages while hosting the FastAPI backend elsewhere.

- A GH Action (`.github/workflows/gh-pages.yml`) is included. It renders `templates/index.html` to a static `site/` folder and deploys it to the `gh-pages` branch.
- To configure the Sign-in button OAuth link, set the repository secret `OAUTH_URL` to your Discord OAuth authorize URL (or leave as `#` for a placeholder).

- A GH Action (`.github/workflows/gh-pages.yml`) is included. It renders `templates/index.html` to a static `docs/` folder under `Villicus Website/docs` and deploys it to GitHub Pages.
- To configure the Sign-in button OAuth link, set the repository secret `OAUTH_URL` to your Discord OAuth authorize URL (or leave as `#` for a placeholder).

### Full backend deployment (recommended)

You can automatically build and publish a backend container for the FastAPI website and deploy it to Render using the included workflow `.github/workflows/build-and-deploy-image.yml`.

Required repository secrets for automated deploy:
- `GITHUB_TOKEN` (provided automatically by GitHub Actions) — used to push to GHCR.
- `RENDER_API_KEY` — a Render API token with deploy permissions.
- `RENDER_SERVICE_ID` — the Render service ID for your web service.

What the workflow does:
- Builds a Docker image from the repository `Dockerfile` and pushes it to GitHub Container Registry as `ghcr.io/<owner>/villicus-website:<sha>`.
- Triggers a Render deploy by POSTing to the Render API with the pushed image.

If you use another host (Railway, Heroku, Cloud Run), you can adapt the deploy step to call their API or use their CLI.

## Integration tests

An integration test suite is included at `tests/test_integration.py` to verify a deployed instance responds correctly. The GitHub Actions workflow `.github/workflows/integration-tests.yml` runs these tests when the repository secret `DEPLOY_URL` is set.

To run tests locally against a deployed URL:

```bash
DEPLOY_URL=https://your-deploy.example.com pytest -q tests/test_integration.py
```

### E2E JWT exchange tests (only with real credentials)

There is an end-to-end test skeleton `tests/test_e2e_jwt.py` that exercises the JWT exchange and a protected bot API endpoint. This MUST only be run with safe test credentials and against a test guild.

To run locally set these environment variables before running pytest:

```bash
export BOT_API_URL=https://api.your-deploy.com
export TEST_DISCORD_OAUTH_TOKEN=your_test_discord_oauth_token
export TEST_GUILD_ID=1234567890
pytest -q tests/test_e2e_jwt.py
```

Do NOT run these tests against production accounts or live guilds without permission.

## Demo pages on GitHub Pages

The static renderer now generates demo pages so the repository's Pages site can showcase the dashboard and configure screens even when the backend runs elsewhere.

- After pushing, enable Pages to serve the `/docs` folder on `main`.
- Demo URLs that will be available on your Pages site:
	- `/` — marketing index
	- `/dashboard.html` — demo dashboard (sample guilds)
	- `/configure_111111.html` — demo configure page for sample guild id `111111`

These demo pages use mocked data so you can preview the UI on GitHub Pages without a running backend.

Publishing via repo-root `docs/` on `main` branch:

1. Push the repo to GitHub.
2. In the repository settings → Pages, set the source to `main` branch and the `/docs` folder.
3. The GH Action will render and update the `docs/` content automatically on push.

Note: The dashboard & configuration require a running FastAPI backend — only the marketing/static frontend is suitable for GitHub Pages.

## Production Recommendations

- Switch to server-side sessions (Redis) to avoid storing tokens in client cookies.
- Use a short-lived JWT or rotated API tokens between the website and bot rather than a long-lived static `BOT_API_KEY`.
- This repository implements a JWT exchange: the website exchanges the logged-in user's Discord OAuth `access_token` for a short-lived JWT scoped to the guild using `/api/token`. The website then calls the bot API endpoints with `Authorization: Bearer <jwt>` so actions are performed per authenticated user.
- Add CSRF protections for POST endpoints that mutate state.
- Rate-limit the bot API endpoints and validate input server-side.

## Troubleshooting

- If the dashboard shows no guilds after sign-in, ensure the OAuth `scope` includes `identify guilds` and that your redirect URI matches the application settings.
- If the bot endpoints return 401/403, verify `BOT_API_KEY` matches the bot's config and the bot's API is reachable.

## Next steps
- Add Redis-backed session support and sample config.
- Add automated tests for website ↔ bot API integration.
