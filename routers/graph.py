from fastapi import APIRouter, Depends
from neo4j_graph import get_graph_insights
from routers.auth import get_current_user

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/insights")
def graph_insights(username: str = Depends(get_current_user)):
    """Dark patterns & payment rail exposure queried directly from Neo4j Cypher."""
    return get_graph_insights(username)
