"""Dashboard API. Endpoints are plain `def` (not async) so FastAPI runs them in a worker thread,
which means the slow Gemini call never freezes other requests."""
from fastapi import APIRouter, Depends
from core import build_alerts, dashboard_metrics
from routers.auth import get_current_user
from store import get_commitments, get_status

router = APIRouter(prefix="/api", tags=["analysis"])


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/analysis")
def analysis(refresh: bool = False, username: str = Depends(get_current_user)):
    commitments = get_commitments(username, refresh)
    return {
        "commitments": commitments,
        "metrics": dashboard_metrics(commitments),
        "alerts": build_alerts(commitments),
        "meta": get_status(username),
    }


@router.get("/commitments")
def commitments(username: str = Depends(get_current_user)):
    return get_commitments(username)


@router.get("/alerts")
def alerts(username: str = Depends(get_current_user)):
    return build_alerts(get_commitments(username))
