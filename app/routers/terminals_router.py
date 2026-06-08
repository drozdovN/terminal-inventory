from typing import Optional, List
from datetime import date
from datetime import datetime, date, timezone, timedelta
MSK = timezone(timedelta(hours=3))

from fastapi import APIRouter, Depends, Request, Form, Query, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import io
from openpyxl import Workbook
from openpyxl import load_workbook

from app.database import get_db
from app.models import Terminal, StatusHistory, User
from app.auth import SECRET_KEY, ALGORITHM
from app.models import Terminal, StatusHistory, User, ApkFile
from fastapi import WebSocket, WebSocketDisconnect
from app.websocket_manager import manager
import os

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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
async def terminals_list(
    request: Request,
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Terminal)
    if status:
        query = query.filter(Terminal.status == status)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Terminal.serial_number.ilike(search_term)) |
            (Terminal.model.ilike(search_term)) |
            (Terminal.box_number.ilike(search_term)) |
            (Terminal.responsible_person.ilike(search_term)) |
            (Terminal.bank.ilike(search_term))
        )
    terminals = query.order_by(Terminal.id.asc()).all()
    return templates.TemplateResponse(
        "terminals_list.html",
        {"request": request, "terminals": terminals, "search": search}
    )


@router.get("/export")
async def terminals_export(db: Session = Depends(get_db)):
    terminals = db.query(Terminal).order_by(Terminal.id).all()
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Терминалы"
    
    headers = ["ID", "Модель", "Прошивка", "Серийный номер", "Коробка",
               "Статус", "Банк", "Тип брака", "Комментарий к браку",
               "Ответственный", "Дата прихода"]
    ws.append(headers)
    
    for t in terminals:
        ws.append([
            t.id,
            t.model,
            t.firmware_version,
            t.serial_number,
            t.box_number,
            t.status,
            t.bank or '',
            t.defect_type or '',
            t.defect_comment or '',
            t.responsible_person,
            t.arrival_date.strftime('%Y-%m-%d') if t.arrival_date else ''
        ])
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetmlm.sheet",
        headers={"Content-Disposition": "attachment; filename=terminals.xlsx"}
    )


@router.get("/import", response_class=HTMLResponse)
async def terminal_import_form(request: Request):
    return templates.TemplateResponse(
        "terminal_import.html",
        {"request": request}
    )


@router.post("/import")
async def terminal_import(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user = get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return templates.TemplateResponse(
            "terminal_import.html",
            {"request": request, "error": "Неверный формат файла. Ожидается .xlsx или .xls"}
        )
    
    try:
        contents = await file.read()
        wb = load_workbook(filename=io.BytesIO(contents), read_only=True)
        ws = wb.active
        
        imported = 0
        skipped = 0
        errors = []
        
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not row[0]:
                continue
            
            try:
                model = str(row[0]).strip()
                firmware = str(row[1]).strip() if row[1] else ""
                serial = str(row[2]).strip() if row[2] else ""
                box = str(row[3]).strip() if row[3] else ""
                
                arrival = row[4]
                if hasattr(arrival, 'strftime'):
                    arrival_str = arrival.strftime('%Y-%m-%d')
                else:
                    arrival_str = str(arrival).strip() if arrival else ""
                
                responsible = str(row[5]).strip() if len(row) > 5 and row[5] else ""
                
                if not serial:
                    skipped += 1
                    continue
                
                existing = db.query(Terminal).filter(Terminal.serial_number == serial).first()
                if existing:
                    skipped += 1
                    continue
                
                terminal = Terminal(
                    model=model or "Не указано",
                    firmware_version=firmware or "—",
                    serial_number=serial,
                    box_number=box or "—",
                    arrival_date=date.fromisoformat(arrival_str) if arrival_str else date.today(),
                    responsible_person=responsible or "—",
                    status="warehouse"
                )
                db.add(terminal)
                db.flush()
                
                history = StatusHistory(
                    terminal_id=terminal.id,
                    old_status=None,
                    new_status="warehouse",
                    changed_by=user.id,
                    comment="Импортирован из Excel"
                )
                db.add(history)
                imported += 1
                
            except Exception as e:
                errors.append(f"Строка {row_idx}: {str(e)}")
                skipped += 1
        
        db.commit()
        
        return templates.TemplateResponse(
            "terminal_import.html",
            {
                "request": request,
                "success": f"Импортировано: {imported}, пропущено: {skipped}",
                "errors": errors[:10]
            }
        )
    
    except Exception as e:
        return templates.TemplateResponse(
            "terminal_import.html",
            {"request": request, "error": f"Ошибка чтения файла: {str(e)}"}
        )


@router.get("/add", response_class=HTMLResponse)
async def terminal_add_form(request: Request):
    return templates.TemplateResponse(
        "terminal_add.html",
        {"request": request}
    )


@router.post("/add")
async def terminal_add(
    request: Request,
    model: str = Form(...),
    firmware_version: str = Form(...),
    serial_number: str = Form(...),
    box_number: str = Form(...),
    arrival_date: str = Form(...),
    responsible_person: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    
    existing = db.query(Terminal).filter(Terminal.serial_number == serial_number).first()
    if existing:
        return templates.TemplateResponse(
            "terminal_add.html",
            {"request": request, "error": f"Терминал с серийным номером {serial_number} уже существует"}
        )
    
    terminal = Terminal(
        model=model,
        firmware_version=firmware_version,
        serial_number=serial_number,
        box_number=box_number,
        arrival_date=date.fromisoformat(arrival_date),
        responsible_person=responsible_person,
        status="warehouse"
    )
    db.add(terminal)
    db.flush()
    
    history = StatusHistory(
        terminal_id=terminal.id,
        old_status=None,
        new_status="warehouse",
        changed_by=user.id,
        comment="Терминал добавлен на склад"
    )
    db.add(history)
    db.commit()
    
    return RedirectResponse(url="/terminals", status_code=303)

@router.post("/bulk-status")
async def bulk_change_status(
    request: Request,
    terminal_ids: str = Form(...),
    new_status: str = Form(...),
    bank: Optional[str] = Form(None),
    defect_type: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    
    updated = 0
    for tid in terminal_ids.split(','):
        tid = tid.strip()
        if not tid:
            continue
        terminal = db.query(Terminal).filter(Terminal.id == int(tid)).first()
        if terminal:
            old_status = terminal.status
            terminal.status = new_status
            
            if new_status in ("reserved", "shipped") and bank:
                terminal.bank = bank
            else:
                terminal.bank = None
            
            if new_status == "defective":
                if defect_type:
                    terminal.defect_type = defect_type
            else:
                terminal.defect_type = None
                terminal.defect_comment = None
            
            history = StatusHistory(
                terminal_id=terminal.id,
                old_status=old_status,
                new_status=new_status,
                old_bank=terminal.bank,
                new_bank=terminal.bank if new_status in ("reserved", "shipped") else None,
                old_defect_type=terminal.defect_type,
                new_defect_type=defect_type if new_status == "defective" else None,
                changed_by=user.id,
                comment=comment or "Массовая смена статуса"
            )
            db.add(history)
            updated += 1
    
    db.commit()
    return RedirectResponse(url="/terminals", status_code=303)


@router.post("/ping")
async def terminal_ping(
    serial_number: str = Form(...),
    db: Session = Depends(get_db)
):
    terminal = db.query(Terminal).filter(Terminal.serial_number == serial_number).first()
    if terminal:
        terminal.last_seen = datetime.now(MSK)
        db.commit()
        latest_apk = db.query(ApkFile).order_by(ApkFile.id.desc()).first()
        apk_url = None
        apk_version = None
        if latest_apk:
                if latest_apk.target_serial is None or latest_apk.target_serial == terminal.serial_number:
                    apk_url = f"/static/apk/{latest_apk.filename}"
                    apk_version = latest_apk.version

        return {
                "status": "ok",
                "last_seen": terminal.last_seen.isoformat(),
                "brightness": terminal.brightness or 255,
                "volume": terminal.volume or 100,
                "bluetooth": terminal.bluetooth if terminal.bluetooth is not None else 1,
                "apk_url": apk_url,
                "apk_version": apk_version
            }
    return {"status": "error", "detail": "Terminal not found", "apk_url": None}
    

@router.get("/check-online")
async def terminal_online_status(
    serial_number: str = Query(...),
    db: Session = Depends(get_db)
):
    terminal = db.query(Terminal).filter(Terminal.serial_number == serial_number).first()
    if not terminal:
        return {"online": False, "last_seen": None}
    
    now = datetime.now(MSK)
    is_online = False
    if terminal.last_seen:
        last_seen_naive = terminal.last_seen.replace(tzinfo=None)
        now_naive = now.replace(tzinfo=None)
        delta = now_naive - last_seen_naive
        is_online = delta.total_seconds() < 60
    
    return {
        "online": is_online,
        "last_seen": terminal.last_seen.strftime('%d.%m.%Y %H:%M:%S') if terminal.last_seen else None,
        "terminal_id": terminal.id
    }

@router.get("/apk/list", response_class=HTMLResponse)
async def apk_list(request: Request, db: Session = Depends(get_db)):
    apks = db.query(ApkFile).order_by(ApkFile.id.desc()).all()
    return templates.TemplateResponse("apk_list.html", {
        "request": request,
        "apks": apks
    })


@router.post("/apk/upload")
async def apk_upload(
    request: Request,
    file: UploadFile = File(...),
    version: str = Form(...),
    description: str = Form(""),
    target_serial: str = Form(""),
    db: Session = Depends(get_db)
):
    user = get_user_from_cookie(request, db)
    if not user or user.role != "admin":
        return HTMLResponse("Доступ запрещён", status_code=403)

    if not file.filename or not file.filename.endswith('.apk'):
        return HTMLResponse("Только APK файлы", status_code=400)

    filepath = f"app/static/apk/{file.filename}"
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    apk = ApkFile(
        filename=file.filename,
        version=version,
        description=description or "",
        target_serial=target_serial or None
    )
    db.add(apk)
    db.commit()

    return RedirectResponse(url="/terminals/apk/list", status_code=303)

@router.post("/apk/{apk_id}/delete")
async def apk_delete(apk_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_from_cookie(request, db)
    if not user or user.role != "admin":
        return HTMLResponse("Доступ запрещён", status_code=403)

    apk = db.query(ApkFile).filter(ApkFile.id == apk_id).first()
    if apk:
        # Удаляем файл
        filepath = f"app/static/apk/{apk.filename}"
        if os.path.exists(filepath):
            os.remove(filepath)
        db.delete(apk)
        db.commit()

    return RedirectResponse(url="/terminals/apk/list", status_code=303)

@router.get("/apk/upload", response_class=HTMLResponse)
async def apk_upload_form(request: Request, db: Session = Depends(get_db)):
    terminals = db.query(Terminal).order_by(Terminal.serial_number).all()
    return templates.TemplateResponse("apk_upload.html", {
        "request": request,
        "terminals": terminals
    })


@router.post("/apk/upload")
async def apk_upload(
    request: Request,
    file: UploadFile = File(...),
    version: str = Form(...),
    description: str = Form(""),
    target_serial: str = Form(""),
    db: Session = Depends(get_db)
):
    user = get_user_from_cookie(request, db)
    if not user or user.role != "admin":
        return HTMLResponse("Доступ запрещён", status_code=403)

    if not file.filename or not file.filename.endswith('.apk'):
        return HTMLResponse("Только APK файлы", status_code=400)

    filepath = f"app/static/apk/{file.filename}"
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    apk = ApkFile(
        filename=file.filename,
        version=version,
        description=description or "",
        target_serial=target_serial if target_serial else None
    )
    db.add(apk)
    db.commit()

    return RedirectResponse(url="/terminals/apk/list", status_code=303)

@router.websocket("/ws/terminal/{serial_number}")
async def websocket_terminal(websocket: WebSocket, serial_number: str, db: Session = Depends(get_db)):
    # Проверяем, существует ли терминал
    terminal = db.query(Terminal).filter(Terminal.serial_number == serial_number).first()
    if not terminal:
        await websocket.close(code=4004, reason="Terminal not found")
        return

    await manager.connect_terminal(serial_number, websocket)
    try:
        while True:
            # Получаем кадр от терминала
            data = await websocket.receive_json()
            # Пересылаем в браузер поддержки
            await manager.send_to_support(terminal.id, data)
    except WebSocketDisconnect:
        manager.disconnect_terminal(serial_number)
    except Exception:
        manager.disconnect_terminal(serial_number)


@router.websocket("/ws/support/{terminal_id}")
async def websocket_support(websocket: WebSocket, terminal_id: int, db: Session = Depends(get_db)):
    terminal = db.query(Terminal).filter(Terminal.id == terminal_id).first()
    if not terminal:
        await websocket.close(code=4004, reason="Terminal not found")
        return

    await manager.connect_support(terminal_id, websocket)
    try:
        while True:
            # Получаем клик/команду от браузера
            data = await websocket.receive_json()
            # Пересылаем на терминал
            await manager.send_to_terminal(terminal.serial_number, data)
    except WebSocketDisconnect:
        manager.disconnect_support(terminal_id)
    except Exception:
        manager.disconnect_support(terminal_id)

@router.get("/{terminal_id}/support", response_class=HTMLResponse)
async def terminal_support_page(terminal_id: int, request: Request, db: Session = Depends(get_db)):
    terminal = db.query(Terminal).filter(Terminal.id == terminal_id).first()
    if not terminal:
        return HTMLResponse("Терминал не найден", status_code=404)
    return templates.TemplateResponse("terminal_support.html", {
        "request": request,
        "terminal": terminal
    })        

@router.get("/{terminal_id}", response_class=HTMLResponse)
async def terminal_card(
    terminal_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    terminal = db.query(Terminal).filter(Terminal.id == terminal_id).first()
    if not terminal:
        return HTMLResponse("Терминал не найден", status_code=404)
    
    history = db.query(StatusHistory).filter(
        StatusHistory.terminal_id == terminal_id
    ).order_by(StatusHistory.changed_at.desc()).all()
    
    return templates.TemplateResponse(
        "terminal_card.html",
        {"request": request, "terminal": terminal, "history": history}
    )


@router.post("/{terminal_id}/status")
async def terminal_change_status(
    terminal_id: int,
    request: Request,
    new_status: str = Form(...),
    bank: Optional[str] = Form(None),
    defect_type: Optional[str] = Form(None),
    defect_comment: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    
    terminal = db.query(Terminal).filter(Terminal.id == terminal_id).first()
    if not terminal:
        return HTMLResponse("Терминал не найден", status_code=404)
    
    old_status = terminal.status
    old_bank = terminal.bank
    old_defect_type = terminal.defect_type
    
    terminal.status = new_status
    
    if new_status in ("reserved", "shipped"):
        terminal.bank = bank
    else:
        terminal.bank = None
    
    if new_status == "defective":
        terminal.defect_type = defect_type
        terminal.defect_comment = defect_comment
    else:
        terminal.defect_type = None
        terminal.defect_comment = None
    
    history = StatusHistory(
        terminal_id=terminal.id,
        old_status=old_status,
        new_status=new_status,
        old_bank=old_bank,
        new_bank=terminal.bank,
        old_defect_type=old_defect_type,
        new_defect_type=terminal.defect_type,
        defect_comment=defect_comment,
        changed_by=user.id,
        comment=comment
    )
    db.add(history)
    db.commit()
    
    return RedirectResponse(url=f"/terminals/{terminal_id}", status_code=303)



@router.post("/{terminal_id}/settings")
async def terminal_settings(
    terminal_id: int,
    request: Request,
    brightness: int = Form(...),
    volume: int = Form(...),
    bluetooth: int = Form(...),
    db: Session = Depends(get_db)
):
    user = get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    
    terminal = db.query(Terminal).filter(Terminal.id == terminal_id).first()
    if terminal:
        terminal.brightness = brightness
        terminal.volume = volume
        terminal.bluetooth = bluetooth
        db.commit()
    
    return RedirectResponse(url=f"/terminals/{terminal_id}", status_code=303)




@router.get("/{terminal_id}/edit", response_class=HTMLResponse)
async def terminal_edit_form(
    terminal_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user = get_user_from_cookie(request, db)
    if not user or user.role != "admin":
        return HTMLResponse("Доступ запрещён. Требуются права администратора.", status_code=403)
    
    terminal = db.query(Terminal).filter(Terminal.id == terminal_id).first()
    if not terminal:
        return HTMLResponse("Терминал не найден", status_code=404)
    
    return templates.TemplateResponse(
        "terminal_edit.html",
        {"request": request, "terminal": terminal}
    )


@router.post("/{terminal_id}/edit")
async def terminal_edit(
    terminal_id: int,
    request: Request,
    model: str = Form(...),
    firmware_version: str = Form(...),
    serial_number: str = Form(...),
    box_number: str = Form(...),
    status: str = Form(...),
    bank: Optional[str] = Form(None),
    defect_type: Optional[str] = Form(None),
    defect_comment: Optional[str] = Form(None),
    responsible_person: str = Form(...),
    arrival_date: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_user_from_cookie(request, db)
    if not user or user.role != "admin":
        return HTMLResponse("Доступ запрещён. Требуются права администратора.", status_code=403)
    
    terminal = db.query(Terminal).filter(Terminal.id == terminal_id).first()
    if not terminal:
        return HTMLResponse("Терминал не найден", status_code=404)
    
    # Проверка на дубликат серийника
    existing = db.query(Terminal).filter(
        Terminal.serial_number == serial_number,
        Terminal.id != terminal_id
    ).first()
    if existing:
        return templates.TemplateResponse(
            "terminal_edit.html",
            {"request": request, "terminal": terminal, "error": f"Терминал с серийным номером {serial_number} уже существует"}
        )
    
    # Сохраняем старые значения для истории
    old_status = terminal.status
    old_bank = terminal.bank
    old_defect_type = terminal.defect_type
    
    # Обновляем все поля
    terminal.model = model
    terminal.firmware_version = firmware_version
    terminal.serial_number = serial_number
    terminal.box_number = box_number
    terminal.status = status
    terminal.bank = bank if status in ("reserved", "shipped") else None
    terminal.defect_type = defect_type if status == "defective" else None
    terminal.defect_comment = defect_comment if status == "defective" else None
    terminal.responsible_person = responsible_person
    terminal.arrival_date = date.fromisoformat(arrival_date)
    
    # Пишем в историю, если статус изменился
    if old_status != status or old_bank != terminal.bank or old_defect_type != terminal.defect_type:
        history = StatusHistory(
            terminal_id=terminal.id,
            old_status=old_status,
            new_status=status,
            old_bank=old_bank,
            new_bank=terminal.bank,
            old_defect_type=old_defect_type,
            new_defect_type=terminal.defect_type,
            defect_comment=defect_comment if status == "defective" else None,
            changed_by=user.id,
            comment="Изменено администратором через редактирование"
        )
        db.add(history)
    
    db.commit()
    
    return RedirectResponse(url=f"/terminals/{terminal_id}", status_code=303)


@router.post("/{terminal_id}/delete")
async def terminal_delete(
    terminal_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user = get_user_from_cookie(request, db)
    if not user or user.role != "admin":
        return HTMLResponse("Доступ запрещён. Требуются права администратора.", status_code=403)
    
    terminal = db.query(Terminal).filter(Terminal.id == terminal_id).first()
    if not terminal:
        return HTMLResponse("Терминал не найден", status_code=404)
    
    db.query(StatusHistory).filter(StatusHistory.terminal_id == terminal_id).delete()
    db.delete(terminal)
    db.commit()
    
    return RedirectResponse(url="/terminals", status_code=303)

