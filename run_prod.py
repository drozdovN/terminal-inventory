from waitress import serve
from app.main import app

if __name__ == "__main__":
    print("Продакшен-сервер запущен на http://0.0.0.0:8000")
    serve(app, host="0.0.0.0", port=8000)