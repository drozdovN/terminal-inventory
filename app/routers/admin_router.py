from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, StatusHistory
from app.auth import hash_password
from app.routers.terminals_router import get_user_from_cookie

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def check_admin(request: Request, db: Session):
    user = get_user_from_cookie(request, db)
    if not user or user.role != "admin":
        return None
    return user


@router.get("/users", response_class=HTMLResponse)
async def users_list(request: Request, db: Session = Depends(get_db)):
    admin = check_admin(request, db)
    if not admin:
        return HTMLResponse("Доступ запрещён. Требуются права администратора.", status_code=403)
    
    users = db.query(User).order_by(User.id).all()
    return templates.TemplateResponse(
        "admin_users.html",
        {"request": request, "users": users, "current_user": admin}
    )


@router.post("/users/add")
async def user_add(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db)
):
    admin = check_admin(request, db)
    if not admin:
        return HTMLResponse("Доступ запрещён", status_code=403)
    
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        users = db.query(User).order_by(User.id).all()
        return templates.TemplateResponse(
            "admin_users.html",
            {"request": request, "users": users, "error": f"Пользователь {username} уже существует", "current_user": admin}
        )
    
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role
    )
    db.add(user)
    db.commit()
    
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/delete")
async def user_delete(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    admin = check_admin(request, db)
    if not admin:
        return HTMLResponse("Доступ запрещён", status_code=403)
    
    if admin.id == user_id:
        users = db.query(User).order_by(User.id).all()
        return templates.TemplateResponse(
            "admin_users.html",
            {"request": request, "users": users, "error": "Нельзя удалить самого себя", "current_user": admin}
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        # Удаляем все записи истории, связанные с этим пользователем
        db.query(StatusHistory).filter(StatusHistory.changed_by == user_id).delete()
        # Удаляем пользователя
        db.delete(user)
        db.commit()
    
    return RedirectResponse(url="/admin/users", status_code=303)