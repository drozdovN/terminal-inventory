from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


def get_current_user_from_request(request):
    return getattr(request.state, "current_user", None)


templates.env.globals["get_current_user"] = get_current_user_from_request