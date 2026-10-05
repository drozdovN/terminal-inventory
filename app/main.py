from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import engine, Base, get_db
from app.routers import auth_router, terminals_router, boxes_router, history_router, admin_router
from app.models import Terminal, StatusHistory
from app.middleware import CurrentUserMiddleware
from app.templates import templates
from app.routers import auth_router, terminals_router, boxes_router, history_router, admin_router, profile_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Terminal Inventory")
app.add_middleware(CurrentUserMiddleware)


def render(request, template_name, context=None):
    """Хелпер для рендера с автоматической подстановкой current_user"""
    ctx = context or {}
    ctx["request"] = request
    ctx["current_user"] = getattr(request.state, "current_user", None)
    return templates.TemplateResponse(template_name, ctx)


app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_router.router, prefix="/auth", tags=["auth"])
app.include_router(terminals_router.router, prefix="/terminals", tags=["terminals"])
app.include_router(boxes_router.router, prefix="/boxes", tags=["boxes"])
app.include_router(history_router.router, prefix="/history", tags=["history"])
app.include_router(admin_router.router, prefix="/admin", tags=["admin"])
app.include_router(profile_router.router, prefix="/profile", tags=["profile"])

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    total = db.query(Terminal).count()
    statuses = db.query(Terminal.status, func.count(Terminal.id)).group_by(Terminal.status).all()
    by_status = {s: c for s, c in statuses}

    # Распределение по банкам (только reserved/shipped с заполненным банком)
    by_bank_query = db.query(
        Terminal.bank, func.count(Terminal.id)
    ).filter(
        Terminal.bank.isnot(None),
        Terminal.bank != '',
        Terminal.status.in_(['reserved', 'shipped'])
    ).group_by(Terminal.bank).order_by(func.count(Terminal.id).desc()).all()

    by_bank = [{"bank": b, "count": c} for b, c in by_bank_query]

    recent_history = db.query(StatusHistory).order_by(
        StatusHistory.changed_at.desc()
    ).limit(5).all()

    return render(request, "dashboard.html", {
        "total": total,
        "by_status": by_status,
        "by_bank": by_bank,
        "recent_history": recent_history
    })