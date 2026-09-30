from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.database import get_db
from app.models import StatusHistory, User
from app.auth import SECRET_KEY, ALGORITHM

router = APIRouter()
from app.templates import templates


def get_current_user(request: Request, db: Session):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        return db.query(User).filter(User.id == user_id).first()
    except (JWTError, Exception):
        return None


@router.get("", response_class=HTMLResponse)
async def history_list(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "admin":
        return HTMLResponse("Доступ запрещён", status_code=403)

    history = db.query(StatusHistory).order_by(StatusHistory.changed_at.desc()).limit(100).all()
    return templates.TemplateResponse(
        "history_list.html",
        {"request": request, "history": history, "current_user": user}
    )