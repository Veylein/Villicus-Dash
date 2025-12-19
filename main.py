import os
from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
import httpx
from urllib.parse import urlencode
from dotenv import load_dotenv
from itsdangerous import URLSafeSerializer
import os
import json
import secrets

load_dotenv()

BASE_DIR = Path(__file__).parent
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/callback")
SCOPE = "identify guilds"
BOT_API_URL = os.getenv("BOT_API_URL", "http://localhost:5000")
BOT_API_KEY = os.getenv("BOT_API_KEY")
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me")

app = FastAPI(title="Villicus Website")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# expose `now()` to templates for footer timestamps
templates.env.globals['now'] = datetime.utcnow

# simple signed-session helper
serializer = URLSafeSerializer(SESSION_SECRET)

# Optional Redis session store (set REDIS_URL in environment to enable)
REDIS_URL = os.getenv('REDIS_URL')


async def _get_redis():
    return getattr(app.state, 'redis', None)


async def get_token_from_request(request: Request):
    session = request.cookies.get('villicus_session')
    if not session:
        return None
    try:
        data = serializer.loads(session)
    except Exception:
        return None
    redis = await _get_redis()
    if redis and isinstance(data, dict) and data.get('sid'):
        sid = data.get('sid')
        key = f'session:{sid}'
        try:
            raw = await redis.get(key)
            if not raw:
                return None
            obj = json.loads(raw)
            return obj.get('access_token')
        except Exception:
            return None
    return data.get('access_token') if isinstance(data, dict) else None



@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "prompt": "consent",
    }
    oauth_url = f"https://discord.com/api/oauth2/authorize?{urlencode(params)}"
    return templates.TemplateResponse("index.html", {"request": request, "oauth_url": oauth_url})


@app.get("/login")
async def login():
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "prompt": "consent",
    }
    oauth_url = f"https://discord.com/api/oauth2/authorize?{urlencode(params)}"
    return RedirectResponse(oauth_url)


@app.get("/callback")
async def callback(code: str = None):
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")
    token_url = "https://discord.com/api/oauth2/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient() as client:
        r = await client.post(token_url, data=data, headers=headers)
        r.raise_for_status()
        token = r.json()

    # Prefer server-side session storage when Redis is configured.
    resp = RedirectResponse(url="/dashboard")
    access_token = token.get('access_token')
    if REDIS_URL and getattr(app.state, 'redis', None):
        sid = secrets.token_urlsafe(24)
        key = f'session:{sid}'
        try:
            await app.state.redis.set(key, json.dumps({'access_token': access_token}), ex=60 * 60 * 24 * 7)
            s = serializer.dumps({'sid': sid})
            resp.set_cookie('villicus_session', s, httponly=True, secure=False, samesite='lax')
            return resp
        except Exception:
            # fallback to cookie session
            pass

    # Fallback: Store token in a signed cookie (development only)
    s = serializer.dumps({'access_token': access_token})
    resp.set_cookie('villicus_session', s, httponly=True, secure=False, samesite='lax')
    return resp


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    token = await get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/")
    async with httpx.AsyncClient() as client:
        r = await client.get("https://discord.com/api/users/@me/guilds", headers={"Authorization": f"Bearer {token}"})
        if r.status_code != 200:
            # token may be invalid
            return RedirectResponse(url="/")
        guilds = r.json()

    # Render a simple dashboard listing guilds where user is admin
    admin_guilds = [g for g in guilds if g.get("owner") or (g.get("permissions", 0) & 0x8)]
    return templates.TemplateResponse("dashboard.html", {"request": request, "guilds": guilds, "admin_guilds": admin_guilds})


@app.get('/health')
async def health():
    return {"status": "ok"}


@app.get('/configure/{guild_id}', response_class=HTMLResponse)
async def configure_get(request: Request, guild_id: int):
    token = await get_token_from_request(request)
    if not token:
        return RedirectResponse(url="/")

    # Exchange for short-lived JWT and fetch guild settings via Authorization header
    access_token = await get_token_from_request(request)
    if not access_token:
        return RedirectResponse(url="/")
    async with httpx.AsyncClient() as client:
        t_resp = await client.post(f"{BOT_API_URL}/api/token", headers={"X-API-KEY": BOT_API_KEY, "Content-Type": "application/json"}, json={"access_token": access_token, "guild_id": guild_id})
        if t_resp.status_code != 200:
            return HTMLResponse(f"Failed to get token: {t_resp.text}", status_code=403)
        token = t_resp.json().get('token')

        headers = {"Authorization": f"Bearer {token}"}
        url = f"{BOT_API_URL}/api/guilds/{guild_id}/settings"
        r = await client.get(url, headers=headers)
        if r.status_code != 200:
            return HTMLResponse(f"Failed to fetch guild settings: {r.text}", status_code=500)
        settings = r.json()

        # Enrich staff role IDs with role names via bot API (best-effort)
        try:
            roles_url = f"{BOT_API_URL}/api/guilds/{guild_id}/roles"
            r2 = await client.get(roles_url, headers=headers)
            roles_info = r2.json().get('roles', []) if r2.status_code == 200 else []
            role_map = {str(r['id']): r for r in roles_info}
            staff_list = []
            for rid, lvl in (settings.get('staff_roles') or {}).items():
                info = role_map.get(str(rid))
                staff_list.append({"id": rid, "level": lvl, "name": info['name'] if info else str(rid)})
            settings['staff_roles_list'] = staff_list
        except Exception:
            settings['staff_roles_list'] = [{"id": k, "level": v, "name": str(k)} for k, v in (settings.get('staff_roles') or {}).items()]

    return templates.TemplateResponse('configure.html', {"request": request, "guild_id": guild_id, "settings": settings})


@app.post('/configure/{guild_id}/add_staff')
async def configure_add_staff(request: Request, guild_id: int):
    data = await request.json()
    role_id = int(data.get('role_id'))
    level = int(data.get('level'))
    # Exchange session for a short-lived JWT scoped to this guild
    token = None
    access_token = await get_token_from_request(request)
    if not access_token:
        return HTMLResponse('Not authenticated', status_code=401)
    async with httpx.AsyncClient() as client:
        t_resp = await client.post(f"{BOT_API_URL}/api/token", headers={"X-API-KEY": BOT_API_KEY, "Content-Type": "application/json"}, json={"access_token": access_token, "guild_id": guild_id})
        if t_resp.status_code != 200:
            return HTMLResponse(f"Failed to get token: {t_resp.text}", status_code=403)
        token = t_resp.json().get('token')

        url = f"{BOT_API_URL}/api/guilds/{guild_id}/staffrole"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r = await client.post(url, headers=headers, json={"role_id": role_id, "level": level})
    return HTMLResponse(r.text, status_code=r.status_code)


@app.post('/configure/{guild_id}/remove_staff')
async def configure_remove_staff(request: Request, guild_id: int):
    data = await request.json()
    role_id = int(data.get('role_id'))
    access_token = await get_token_from_request(request)
    if not access_token:
        return HTMLResponse('Not authenticated', status_code=401)
    async with httpx.AsyncClient() as client:
        t_resp = await client.post(f"{BOT_API_URL}/api/token", headers={"X-API-KEY": BOT_API_KEY, "Content-Type": "application/json"}, json={"access_token": access_token, "guild_id": guild_id})
        if t_resp.status_code != 200:
            return HTMLResponse(f"Failed to get token: {t_resp.text}", status_code=403)
        token = t_resp.json().get('token')
        url = f"{BOT_API_URL}/api/guilds/{guild_id}/staffrole"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r = await client.delete(url, headers=headers, json={"role_id": role_id})
    return HTMLResponse(r.text, status_code=r.status_code)


@app.post('/configure/{guild_id}/save_setting')
async def save_setting(request: Request, guild_id: int):
    data = await request.json()
    # forward single setting key/value to bot API
    access_token = await get_token_from_request(request)
    if not access_token:
        return HTMLResponse('Not authenticated', status_code=401)
    async with httpx.AsyncClient() as client:
        t_resp = await client.post(f"{BOT_API_URL}/api/token", headers={"X-API-KEY": BOT_API_KEY, "Content-Type": "application/json"}, json={"access_token": access_token, "guild_id": guild_id})
        if t_resp.status_code != 200:
            return HTMLResponse(f"Failed to get token: {t_resp.text}", status_code=403)
        token = t_resp.json().get('token')
        url = f"{BOT_API_URL}/api/guilds/{guild_id}/settings"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r = await client.post(url, headers=headers, json=data)
    return HTMLResponse(r.text, status_code=r.status_code)


@app.post('/configure/{guild_id}')
async def configure_post(request: Request, guild_id: int, warns_to_punish: int = Form(None), warn_action: str = Form(None)):
    # Save settings via bot API
    url = f"{BOT_API_URL}/api/guilds/{guild_id}/settings"
    headers = {"X-API-KEY": BOT_API_KEY, "Content-Type": "application/json"}
    payload = {}
    if warns_to_punish is not None:
        payload['warns_to_punish'] = str(warns_to_punish)
    if warn_action:
        payload['warn_punish_action'] = warn_action
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=headers, json=payload)
    if r.status_code != 200:
        return HTMLResponse(f"Failed to save: {r.text}", status_code=500)
    return RedirectResponse(url=f"/configure/{guild_id}", status_code=303)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

