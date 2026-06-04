from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import engine, Base, get_db
from app.routers import auth_router, terminals_router, boxes_router, history_router, admin_router
from app.models import Terminal

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Terminal Inventory")
templates = Jinja2Templates(directory="app/templates")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_router.router, prefix="/auth", tags=["auth"])
app.include_router(terminals_router.router, prefix="/terminals", tags=["terminals"])
app.include_router(boxes_router.router, prefix="/boxes", tags=["boxes"])
app.include_router(history_router.router, prefix="/history", tags=["history"])
app.include_router(admin_router.router, prefix="/admin", tags=["admin"])


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    total = db.query(Terminal).count()
    statuses = db.query(Terminal.status, func.count(Terminal.id)).group_by(Terminal.status).all()
    by_status = {s: c for s, c in statuses}
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "total": total, "by_status": by_status}
    )