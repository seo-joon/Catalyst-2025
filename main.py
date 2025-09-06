import os, re
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, Query, Request, Form
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import feedparser
from dateutil import parser as dtparse

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "public"

app = FastAPI(title="benkyou.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "dev-only-secret-change-me"),
    same_site="lax",
)

# --- health ---
@app.get("/ping")
def ping():
    return {"ok": True}

# --- your existing SOURCES / CONCEPTS unchanged ---
SOURCES = [
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("ACCC Media Releases", "https://www.accc.gov.au/rss/media_releases.xml"),
    ("RBA Media Releases", "https://www.rba.gov.au/rss/rss-cb-media-releases.xml"),
]
CONCEPTS = {
    "commerce": {
        "Oligopoly": ["cartel","price fixing","collusion","duopoly","oligopoly","ACCC","OPEC","petrol","fuel"],
        "Monopoly": ["monopoly","dominant position","market power","antitrust","competition watchdog","Section 46"],
        "Mergers_and_Acquisitions": ["merger","acquisition","takeover","M&A","scheme of arrangement","bid"],
        "Inflation": ["inflation","CPI","consumer price index","price pressures","disinflation","headline inflation"],
        "Monetary_Policy": ["interest rate","cash rate","RBA","rate hike","rate cut","QE","QT","policy decision"],
        "Fiscal_Policy": ["budget deficit","surplus","spending","tax cut","stimulus","fiscal"],
        "Externalities": ["externality","pollution","carbon","emissions","tax credit","subsidy"],
        "Asymmetric_Information": ["information asymmetry","insider","adverse selection","moral hazard"],
        "Price_Discrimination": ["price discrimination","dynamic pricing","surge pricing","loyalty pricing"],
        "Competition_Policy": ["ACCC","antitrust","competition authority","undertaking","court-enforceable"],
        "Game_Theory": ["tacit collusion","Nash equilibrium","strategic","coordination","prisoners' dilemma"],
    },
    "arts": {
        "Copyright": ["copyright","intellectual property","royalties","licensing","fair use","IP"],
        "Censorship": ["censor","ban","content moderation","free speech","classification board"],
        "Cultural_policy": ["arts funding","grant","Creative Australia","cultural policy","museum"],
        "Labour_Unions": ["strike","union","industrial action","actors guild"],
    },
}
ALL_CONCEPTS = {**CONCEPTS["commerce"], **CONCEPTS["arts"]}

TAG_RE = re.compile(r"<[^>]+>")
def strip_html(text: str) -> str:
    return TAG_RE.sub("", text or "").strip()

def match_concepts(text: str):
    text_l = (text or "").lower()
    matched = set()
    for concept, kws in ALL_CONCEPTS.items():
        for kw in kws:
            if kw.lower() in text_l:
                matched.add(concept)
                break
    return sorted(matched)

# --- landing & guarding learn.html (you renamed index.html -> learn.html) ---
@app.get("/")
def landing(request: Request):
    u = request.session.get("user")
    if not u:
        return RedirectResponse("/login.html", status_code=302)
    if u.get("login", "").lower() == "newuser":
        return RedirectResponse("/onboarding.html", status_code=302)
    return RedirectResponse("/learn.html", status_code=302)

@app.get("/learn.html")
def serve_learn(request: Request):
    u = request.session.get("user")
    if not u:
        return RedirectResponse("/login.html", status_code=302)
    if u.get("login", "").lower() == "newuser":
        return RedirectResponse("/onboarding.html", status_code=302)
    return FileResponse(str(STATIC_DIR / "learn.html"))

# --- login (admin/admin; newuser always to onboarding) ---
@app.post("/login")
async def auth_login(request: Request):
    username = password = ""
    ctype = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in ctype:
        body = (await request.body()).decode("utf-8", "ignore")
        data = {k: v[0] for k, v in parse_qs(body).items()}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
    else:
        # Fallback: JSON payloads (Postman etc.)
        try:
            data = await request.json()
        except Exception:
            data = {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()

    # Special rule: newuser is always sent to onboarding (but is logged in)
    if username.lower() == "newuser":
        request.session["user"] = {"login": username, "name": username}
        return RedirectResponse("/onboarding.html", status_code=303)

    # Fixed creds
    if username == "admin" and password == "terry":
        request.session["user"] = {"login": username, "name": username}
        return RedirectResponse("/learn.html", status_code=303)

    return RedirectResponse("/login.html?error=1", status_code=303)


@app.post("/logout")
@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse("/login.html", status_code=303)

@app.get("/api/session")
def session(request: Request):
    u = request.session.get("user")
    return {"authenticated": bool(u), "user": u}

# --- API ---
@app.get("/api/concepts")
def list_concepts(track: Optional[str] = Query(None, description="commerce or arts")):
    if track in ("commerce", "arts"):
        return {"track": track, "concepts": sorted(CONCEPTS[track].keys())}
    return {"track": "all", "concepts": sorted(ALL_CONCEPTS.keys())}

@app.get("/api/examples")
def examples(
    request: Request,
    concept: Optional[List[str]] = Query(None, description="one or more concept ids"),
    track: Optional[str] = Query(None, description="commerce or arts"),
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(30, ge=1, le=100),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    selected = set(concept or [])
    results = []
    for source_name, feed_url in SOURCES:
        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            continue
        for e in getattr(feed, "entries", []):
            title = e.get("title", "")
            summary = e.get("summary", "")
            text = f"{title} {summary}"
            concepts = match_concepts(text)
            if track in ("commerce", "arts"):
                concepts = [c for c in concepts if c in CONCEPTS[track]]
            if selected and not set(concepts).issuperset(selected):
                continue
            published_raw = e.get("published") or e.get("updated") or ""
            published = None
            if published_raw:
                try:
                    published = dtparse.parse(published_raw)
                except Exception:
                    published = None
            if published and published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            if published and published < cutoff:
                continue
            results.append({
                "source": source_name,
                "title": title,
                "url": e.get("link"),
                "published": published.isoformat() if published else None,
                "concepts": concepts,
                "summary": strip_html(summary)[:300] + ("…" if len(strip_html(summary)) > 300 else ""),
            })
    results.sort(key=lambda x: (x["published"] or "", x["title"] or ""), reverse=True)
    return results[:limit]

# --- static ---
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
