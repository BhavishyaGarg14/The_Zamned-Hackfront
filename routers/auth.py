from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from config import JWT_SECRET
from neo4j_graph import create_user, get_user_hash

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthPayload(BaseModel):
    username: str
    password: str


def _make_token(username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=7)
    return jwt.encode({"sub": username, "exp": exp}, JWT_SECRET, algorithm="HS256")


def get_current_user(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.") from exc


@router.post("/register")
def register(body: AuthPayload):
    username = body.username.strip().lower()
    if len(username) < 3 or len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Username (3+ chars) and password (6+ chars) required.")
    pw_hash = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    if not create_user(username, pw_hash):
        raise HTTPException(status_code=409, detail="Username is already taken.")
    return {"token": _make_token(username), "username": username}


@router.post("/login")
def login(body: AuthPayload):
    username = body.username.strip().lower()
    stored_hash = get_user_hash(username)
    if not stored_hash or not bcrypt.checkpw(body.password.encode("utf-8"), stored_hash.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return {"token": _make_token(username), "username": username}