from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.database import get_db
from app.models import User
from app.auth import SECRET_KEY, ALGORITHM, hash_password, verify_password
from app.templates import templates

router = APIRouter()


def get_user_from_cookie(request: Request, db: Session):
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
async def profile_page(
    request: Request,
    tab: str = "basic",
    db: Session = Depends(get_db)
):
    user = get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    if tab not in ("basic", "password"):
        tab = "basic"

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "active_tab": tab,
            "current_user": user
        }
    )


@router.post("/basic")
async def profile_update_basic(
    request: Request,
    username: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    # Менять логин может только админ
    if user.role not in ("admin", "superadmin"):
        return RedirectResponse(
            url=f"/profile?tab=basic&error={quote('Только администратор может менять логин')}",
            status_code=303
        )

    username = username.strip()

    # Валидация
    if len(username) < 3 or len(username) > 50:
        return RedirectResponse(
            url=f"/profile?tab=basic&error={quote('Логин должен быть от 3 до 50 символов')}",
            status_code=303
        )

    # Проверка на дубликат
    existing = db.query(User).filter(
        User.username == username,
        User.id != user.id
    ).first()
    if existing:
        return RedirectResponse(
            url=f"/profile?tab=basic&error={quote(f'Пользователь {username} уже существует')}",
            status_code=303
        )

    user.username = username
    db.commit()

    return RedirectResponse(
        url=f"/profile?tab=basic&success={quote('Изменения сохранены')}",
        status_code=303
    )


@router.post("/password")
async def profile_update_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    error = None

    # Проверка старого пароля
    if not verify_password(old_password, user.password_hash):
        error = "Неверный текущий пароль"
    elif len(new_password) < 6:
        error = "Новый пароль должен быть минимум 6 символов"
    elif new_password != confirm_password:
        error = "Пароли не совпадают"

    if error:
        return RedirectResponse(
            url=f"/profile?tab=password&error={quote(error)}",
            status_code=303
        )

    user.password_hash = hash_password(new_password)
    db.commit()

    return RedirectResponse(
        url=f"/profile?tab=password&success={quote('Пароль изменён')}",
        status_code=303
    )