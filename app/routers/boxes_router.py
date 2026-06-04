from typing import Optional

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Terminal

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def boxes_list(
    request: Request,
    box: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    boxes_query = db.query(
        Terminal.box_number,
        func.count(Terminal.id).label("total"),
        func.sum(func.iif(Terminal.status == "warehouse", 1, 0)).label("warehouse"),
        func.sum(func.iif(Terminal.status == "reserved", 1, 0)).label("reserved"),
        func.sum(func.iif(Terminal.status == "defective", 1, 0)).label("defective"),
        func.sum(func.iif(Terminal.status == "repair", 1, 0)).label("repair"),
        func.sum(func.iif(Terminal.status == "shipped", 1, 0)).label("shipped"),
    ).group_by(Terminal.box_number).order_by(Terminal.box_number)
    
    boxes = boxes_query.all()
    
    terminals = []
    if box:
        terminals = db.query(Terminal).filter(Terminal.box_number == box).order_by(Terminal.id).all()
    
    return templates.TemplateResponse(
        "boxes_list.html",
        {"request": request, "boxes": boxes, "terminals": terminals, "selected_box": box}
    )