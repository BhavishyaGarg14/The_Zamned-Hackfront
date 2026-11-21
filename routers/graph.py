from fastapi import APIRouter
from neo4j_graph import get_graph_insights

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/insights")
def graph_insights():
    """Dark patterns & payment rail exposure queried directly from Neo4j Cypher."""
    return get_graph_insights()