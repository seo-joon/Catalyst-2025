import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Query, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse, JSONResponse

import feedparser
from dateutil import parser as dtparse

app = FastAPI(title="benkyou.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "dev-only-secret-change-me"),
    same_site="lax",
)

# --- Sources ---
SOURCES = [
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("ACCC Media Releases", "https://www.accc.gov.au/rss/media_releases.xml"),
    ("RBA Media Releases", "https://www.rba.gov.au/rss/rss-cb-media-releases.xml"),
]

# --- Concept taxonomy: commerce + arts ---
CONCEPTS = {
    "commerce": {
        "Oligopoly": ["cartel", "price fixing", "collusion", "duopoly", "oligopoly", "ACCC", "OPEC", "petrol", "fuel"],
        "Monopoly": ["monopoly", "dominant position", "market power", "antitrust", "competition watchdog", "Section 46"],
        "Mergers_and_Acquisitions": ["merger", "acquisition", "takeover", "M&A", "scheme of arrangement", "bid"],
        "Inflation": ["inflation", "CPI", "consumer price index", "price pressures", "disinflation", "headline inflation"],
        "Monetary_Policy": ["interest rate", "cash rate", "RBA", "rate hike", "rate cut", "QE", "QT", "policy decision"],
        "Fiscal_Policy": ["budget deficit", "surplus", "spending", "tax cut", "stimulus", "fiscal"],
        "Externalities": ["externality", "pollution", "carbon", "emissions", "tax credit", "subsidy"],
        "Asymmetric_Information": ["information asymmetry", "insider", "adverse selection", "moral hazard"],
        "Price_Discrimination": ["price discrimination", "dynamic pricing", "surge pricing", "loyalty pricing"],
        "Competition_Policy": ["ACCC", "antitrust", "competition authority", "undertaking", "court-enforceable"],
        "Game_Theory": ["tacit collusion", "Nash equilibrium", "strategic", "coordination", "prisoners' dilemma"],
    },
    "arts": {
        "Copyright": ["copyright", "intellectual property", "royalties", "licensing", "fair use", "IP"],
        "Censorship": ["censor", "ban", "content moderation", "free speech", "classification board"],
        "Cultural_policy": ["arts funding", "grant", "Creative Australia", "cultural policy", "museum"],
        "Labour_Unions": ["strike", "union", "industrial action", "actors guild"],
    },
}
ALL_CONCEPTS = {**CONCEPTS["commerce"], **CONCEPTS["arts"]}

# --- Helpers ---
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

# --- Health ---
@app.get("/ping")
def ping():
    return {"ok": True}

# --- Auth (fixed admin/admin) ---
@app.post("/auth/login")
async def auth_login(
    request: Request,
    username: str | None = Form(None),
    password: str | None = Form(None),
):
    # Fallback for JSON posts (Postman etc.)
    if username is None and password is None:
        try:
            data = await request.json()
        except Exception:
            data = {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
    else:
        username = (username or "").strip()
        password = (password or "").strip()

    # Special rule: "newuser" is ALWAYS sent to onboarding, but IS logged in
    if username.lower() == "newuser":
        request.session["user"] = {"login": username, "name": username}
        return RedirectResponse(url="/onboarding.html", status_code=303)

    # Normal fixed creds
    if username == "admin" and password == "terry":
        request.session["user"] = {"login": username, "name": username}
        return RedirectResponse(url="/learn.html", status_code=303)

    # invalid creds -> back to login with error flag
    return RedirectResponse(url="/login.html?error=1", status_code=303)

@app.post("/logout")
@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="/login.html", status_code=303)

@app.get("/api/session")
def session(request: Request):
    u = request.session.get("user")
    return {"authenticated": bool(u), "user": u}

# --- API ---
@app.get("/api/concepts")
def list_concepts(track: str | None = Query(None, description="commerce or arts")):
    if track in ("commerce", "arts"):
        return {"track": track, "concepts": sorted(CONCEPTS[track].keys())}
    return {"track": "all", "concepts": sorted(ALL_CONCEPTS.keys())}

@app.get("/api/examples")
def examples(
    request: Request,
    concept: list[str] | None = Query(None, description="one or more concept ids"),
    track: str | None = Query(None, description="commerce or arts"),
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(30, ge=1, le=100),
):
    # To require login for results, uncomment:
    # if not request.session.get("user"):
    #     return JSONResponse({"error": "unauthorized"}, status_code=401)

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
            if selected and not set(concepts).issuperset(selected):  # ALL selected concepts
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

# Serve frontend from ./public
@app.get("/")
def landing(request: Request):
    u = request.session.get("user")
    if not u:
        return RedirectResponse("/login.html", status_code=302)
    if u.get("login","").lower() == "newuser":
        return RedirectResponse("/onboarding.html", status_code=302)
    return FileResponse("public/index.html")

# protect
@app.get("/learn.html")
def serve_learn(request: Request):
    u = request.session.get("user")
    if not u:
        return RedirectResponse("/login.html", status_code=302)
    if u.get("login", "").lower() == "newuser":
        return RedirectResponse("/onboarding.html", status_code=302)
    return FileResponse("public/learn.html")

app.mount("/", StaticFiles(directory="public", html=True), name="static")