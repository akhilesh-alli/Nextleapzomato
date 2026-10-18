# Deployment Plan — Zomato Concierge AI

> **Strategy:** Backend (Python/Starlette API) -> **Railway** | Frontend (Static HTML/CSS/JS) -> **Vercel**

---

## Architecture Overview

```
 User Browser
      |
      v
 Vercel CDN          API Calls        Railway
 (Frontend)    ----------------------> (Backend)
 index.html   <----------------------  Starlette
 style.css        JSON Responses      Orchestrator
 app.js                               Groq LLM
                                      Zomato CSV
```

> NOTE: The frontend and backend will be **decoupled** after deployment.
> The frontend API calls must be updated from relative paths (`/api/recommend`)
> to the full Railway URL before deploying to Vercel.

---

## Pre-Deployment Checklist

- [ ] Project pushed to a GitHub repository
- [ ] Railway account created at https://railway.app
- [ ] Vercel account created at https://vercel.com
- [ ] Groq API key available (from https://console.groq.com/keys)
- [x] `data/restaurants_clean.csv` un-ignored in `.gitignore` and ready to commit

---

## Phase 1 — Repository Preparation

### 1.1 Add Missing Config Files

#### `Procfile` (Railway process definition)
```
web: uvicorn ui.server:app --host 0.0.0.0 --port $PORT
```

#### `railway.json` (Railway build config)
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": { "builder": "NIXPACKS" },
  "deploy": {
    "startCommand": "uvicorn ui.server:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/api/health",
    "healthcheckTimeout": 300,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

#### `runtime.txt` (Python version pin)
```
python-3.11
```

#### `requirements-prod.txt` (Production-only, excludes Streamlit/pytest)
```
datasets>=2.19.0
pandas>=2.0.0
numpy>=1.26.0
groq>=0.9.0
openai>=1.30.0
google-generativeai>=0.7.0
python-dotenv>=1.0.0
starlette>=0.40.0
uvicorn[standard]>=0.30.0
python-multipart>=0.0.9
```

### 1.2 Update `.gitignore`

Comment out the clean CSV line so Railway can access it:
```gitignore
# data/restaurants_clean.csv   <- COMMENT OUT to commit this file
data/restaurants_raw.csv        # still ignore the 574 MB raw file
```

### 1.3 Decouple Frontend API URL

`web/js/app.js` (line 563) currently calls `fetch('/api/recommend', ...)` using a
relative path — this only works when frontend and backend share the same origin.

**Step 1:** Add at the top of the IIFE in `app.js`:
```js
const API_BASE = window.CONCIERGE_API_BASE || '';
```

**Step 2:** Replace `fetch('/api/recommend'` with:
```js
const response = await fetch(`${API_BASE}/api/recommend`, {
```

Apply the same pattern to any other `/api/` calls (locations, cuisines, health).

**Step 3:** In `web/index.html`, inject the Railway URL before `app.js` loads:
```html
<script>
  window.CONCIERGE_API_BASE = 'https://your-app-name.railway.app';
</script>
<script src="/js/app.js"></script>
```

For local development leave `CONCIERGE_API_BASE` unset — it will fall back to `''`.

### 1.4 Harden CORS in `ui/server.py`

After Vercel deployment, replace `allow_origins=["*"]` with:
```python
allow_origins=[
    "https://your-project.vercel.app",
    "https://your-custom-domain.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
],
```

---

## Phase 2 — Railway Backend Deployment

### 2.1 Create New Railway Project

1. Go to https://railway.app -> **New Project**
2. Select **Deploy from GitHub repo**
3. Authorize Railway and select `next-leap-ai-restaurant`
4. Railway auto-detects Python via Nixpacks

### 2.2 Configure Environment Variables

In Railway dashboard -> **Variables** tab:

| Variable         | Value                     | Required            |
|------------------|---------------------------|---------------------|
| LLM_PROVIDER     | groq                      | Yes                 |
| LLM_MODEL        | llama-3.3-70b-versatile   | Yes                 |
| GROQ_API_KEY     | gsk_...                   | Yes                 |
| OPENAI_API_KEY   | sk-...                    | Only if using OpenAI|
| GEMINI_API_KEY   | AI...                     | Only if using Gemini|
| PORT             | 8000                      | Auto-set by Railway |

> CAUTION: Never commit API keys to the repository!

### 2.3 Configure Start Command

In Railway -> Settings -> Deploy tab:
```
uvicorn ui.server:app --host 0.0.0.0 --port $PORT
```

Railway automatically injects `$PORT`. Do NOT hardcode port 8000.

### 2.4 Set Health Check

- Health Check Path: `/api/health`
- Health Check Timeout: `300` seconds

### 2.5 Trigger First Deployment

```bash
git add Procfile railway.json runtime.txt requirements-prod.txt
git commit -m "feat: add Railway deployment configuration"
git push origin main
```

### 2.6 Verify Backend is Live

```bash
curl https://your-app.railway.app/api/health
```

Expected:
```json
{
  "status": "healthy",
  "service": "Zomato Concierge AI",
  "provider": "groq",
  "model": "llama-3.3-70b-versatile",
  "dataset_rows": 9220,
  "neural_nodes": "active"
}
```

---

## Phase 3 — Vercel Frontend Deployment

### 3.1 Create `vercel.json`

```json
{
  "version": 2,
  "name": "zomato-concierge-ai",
  "builds": [
    { "src": "web/**", "use": "@vercel/static" }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "/web/$1" }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-XSS-Protection", "value": "1; mode=block" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" }
      ]
    },
    {
      "source": "/css/(.*)",
      "headers": [{ "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }]
    },
    {
      "source": "/js/(.*)",
      "headers": [{ "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }]
    }
  ]
}
```

### 3.2 Deploy via Vercel Dashboard (Recommended)

1. Go to https://vercel.com -> **New Project**
2. Import your GitHub repository
3. In **Configure Project**:
   - Framework Preset: **Other**
   - Root Directory: **`web`**
   - Build Command: *(leave empty)*
   - Output Directory: **`.`**
4. Click **Deploy**

### 3.3 Deploy via Vercel CLI (Alternative)

```bash
npm install -g vercel
vercel login
cd web
vercel --prod
```

### 3.4 Add Custom Domain (Optional)

Vercel -> Domains -> Add domain -> Follow DNS instructions.

---

## Phase 4 — Post-Deployment Verification

### End-to-End Checklist

- [ ] `GET https://your-project.vercel.app` loads the Obsidian Gourmet Concierge UI
- [ ] Fonts (Plus Jakarta Sans, Inter, Material Symbols) load correctly
- [ ] `GET https://your-api.railway.app/api/health` returns "status": "healthy"
- [ ] Clicking "Discover Curated Dining" returns results within ~10 seconds
- [ ] Rating slider, cuisine tags, budget switcher, toggles work
- [ ] Book Table modal and confirmation toast function correctly
- [ ] Bookmarks persist across page refreshes (localStorage)
- [ ] Browser console shows NO CORS errors

### Performance Targets

| Metric                        | Target    | Tool                 |
|-------------------------------|-----------|----------------------|
| Vercel FCP (First Content.)   | < 1.2s    | PageSpeed Insights   |
| Railway API cold start        | < 8s      | Railway logs         |
| Railway API warm response     | < 6s      | Browser DevTools     |
| Lighthouse Performance Score  | > 90      | Chrome DevTools      |

---

## Phase 5 — Production Hardening

### 5.1 Railway Resource Sizing
- Memory: 512 MB minimum (pandas + CSV dataset uses ~200 MB)
- CPU: 0.5 vCPU for single-user, scale up for concurrent traffic

### 5.2 Prevent Railway Sleep (Free Tier)
- Upgrade to Railway Starter plan ($5/month), OR
- Use UptimeRobot (free) to ping `/api/health` every 5 minutes

### 5.3 Rate Limiting
```python
# pip install slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)
# Decorate: @limiter.limit("10/minute")
```

### 5.4 Monitoring
- Railway: Built-in CPU/memory/request logs in dashboard
- Vercel: Enable Analytics tab for Web Vitals
- Errors: Add Sentry (`pip install sentry-sdk[starlette]`)

---

## Files to Create / Modify

| File                    | Action    | Status    | Purpose                              |
|-------------------------|-----------|-----------|--------------------------------------|
| Procfile                | Created   | [x] Done  | Railway process entrypoint           |
| railway.json            | Created   | [x] Done  | Railway build & deploy config        |
| nixpacks.toml           | Created   | [x] Done  | Railway Nixpacks setup & install cmds|
| runtime.txt             | Created   | [x] Done  | Pin Python 3.11                      |
| .python-version         | Created   | [x] Done  | Pyenv / Nixpacks Python 3.11 pin     |
| requirements-prod.txt   | Created   | [x] Done  | Lean production deps (no Streamlit)  |
| vercel.json             | Created   | [x] Done  | Vercel routing & cache headers       |
| web/vercel.json         | Created   | [x] Done  | Subdirectory Vercel deploy config    |
| .gitignore              | Modified  | [x] Done  | Un-ignore restaurants_clean.csv      |
| web/js/app.js           | Modified  | [x] Done  | Decoupled API_BASE + Telemetry sync  |
| web/index.html          | Modified  | [x] Done  | CONCIERGE_API_BASE + footer health id|
| ui/server.py            | Modified  | [x] Done  | Dynamic CORS, Vercel regex, $PORT    |
| config/settings.py      | Modified  | [x] Done  | Default LLM model for Groq           |

---

## Quick Reference

| Service            | URL                                           | Status |
|--------------------|-----------------------------------------------|--------|
| Frontend (Vercel)  | https://nextleapzomato-web.vercel.app         |  Live  |
| Backend (Railway)  | https://nextleapzomato-production.up.railway.app |  Live  |
| Health Check       | https://nextleapzomato-production.up.railway.app/api/health |  200 OK |
| Recommend API      | POST https://nextleapzomato-production.up.railway.app/api/recommend |  Live  |

---

*Deployment Plan v1.0 — Next Leap AI*
