"""API HTTP + interface do SOFA SD."""
import math
from fastapi import FastAPI, Body
from fastapi.responses import FileResponse, JSONResponse
from .config import ROOT, LEAGUES, save_keys
from .service import Service

app = FastAPI(title="SOFA SD")
svc = Service()


def clean(o):
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if hasattr(o, "item"):
        return clean(o.item())
    return o


def J(x, code=200):
    return JSONResponse(clean(x), status_code=code, headers={"Cache-Control": "no-store"})


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "dist" / "index.html", headers={"Cache-Control": "no-store"})

@app.get("/api/leagues")
def leagues():
    return J([dict(code=k, name=v["name"], country=v["country"]) for k, v in LEAGUES.items()])

@app.get("/api/status")
def status():
    return J(svc.status())

@app.get("/api/matches")
def matches(scope: str = "today", league: str | None = None):
    if league and league not in LEAGUES: return J(dict(error="liga desconhecida"), 404)
    return J(svc.results(league) if scope == "results" else svc.matches(scope, league))

@app.get("/api/match")
def match(id: str):
    m = svc.match(id)
    return J(m) if m else J(dict(error="partida não encontrada"), 404)

@app.get("/api/standings/{league}")
def standings(league: str):
    if league not in LEAGUES: return J(dict(error="liga desconhecida"), 404)
    return J(svc.standings(league))

@app.get("/api/scorers/{league}")
def scorers(league: str):
    if league not in LEAGUES: return J(dict(error="liga desconhecida"), 404)
    return J(svc.scorers(league))

@app.get("/api/highlights")
def highlights():
    return J(svc.highlights())

@app.get("/api/intelligence")
def intelligence():
    return J(svc.intelligence())

@app.get("/api/crests")
def crests():
    return J(svc.crests())

@app.get("/api/team")
def team(league: str, name: str):
    if league not in LEAGUES: return J(dict(error="liga desconhecida"), 404)
    return J(svc.team(league, name))

@app.post("/api/keys")
def set_keys(body: dict = Body(...)):
    save_keys(body.get("fdorg"), body.get("apifootball"))
    svc.refresh(force=True)
    return J(svc.status())

@app.post("/api/refresh")
def refresh():
    svc.refresh(force=True)
    return J(svc.status())

@app.post("/api/retrain")
def retrain():
    return J(dict(started=svc.retrain()))
