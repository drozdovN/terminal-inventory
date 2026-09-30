from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
from app.auth import SECRET_KEY, ALGORITHM
from app.database import SessionLocal
from app.models import User


class CurrentUserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.current_user = None
        token = request.cookies.get("access_token")
        if token:
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                user_id = int(payload.get("sub"))
                db = SessionLocal()
                try:
                    user = db.query(User).filter(User.id == user_id).first()
                    request.state.current_user = user
                finally:
                    db.close()
            except (JWTError, Exception):
                pass

        response = await call_next(request)
        return response