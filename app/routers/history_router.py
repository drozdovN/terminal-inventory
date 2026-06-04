from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StatusHistory

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def history_list(
    request: Request,
    db: Session = Depends(get_db)
):
    history = db.query(StatusHistory).order_by(StatusHistory.changed_at.desc()).limit(100).all()
    return templates.TemplateResponse(
        "history_list.html",
        {"request": request, "history": history}
    )