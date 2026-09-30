from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, StatusHistory
from app.auth import hash_password
from app.schemas import UserCreate
from app.routers.terminals_router import get_user_from_cookie
from app.templates import templates

router = APIRouter()


def check_admin(request: Request, db: Session):
    user = get_user_from_cookie(request, db)
    if not user or user.role != "admin":
        return None
    return user


def format_validation_error(e):
    """Превращает ошибку Pydantic в читаемый текст"""
    try:
        errors = e.errors()
        messages = []
        for err in errors:
            field = '.'.join(str(x) for x in err['loc'])
            msg = err['msg']
            messages.append(f"{field}: {msg}")
        return '; '.join(messages)
    except Exception:
        return str(e)


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

    # Валидация
    try:
        data = UserCreate(
            username=username.strip(),
            password=password,
            role=role
        )
    except Exception as e:
        users = db.query(User).order_by(User.id).all()
        return templates.TemplateResponse(
            "admin_users.html",
            {
                "request": request,
                "users": users,
                "error": format_validation_error(e),
                "current_user": admin,
                "form_data": {"username": username, "role": role}
            }
        )

    # Проверка на дубликат
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        users = db.query(User).order_by(User.id).all()
        return templates.TemplateResponse(
            "admin_users.html",
            {
                "request": request,
                "users": users,
                "error": f"Пользователь {data.username} уже существует",
                "current_user": admin,
                "form_data": {"username": username, "role": role}
            }
        )

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role
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
            {
                "request": request,
                "users": users,
                "error": "Нельзя удалить самого себя",
                "current_user": admin
            }
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        # Удаляем все записи истории, связанные с этим пользователем
        db.query(StatusHistory).filter(StatusHistory.changed_by == user_id).delete()
        # Удаляем пользователя
        db.delete(user)
        db.commit()

    return RedirectResponse(url="/admin/users", status_code=303)