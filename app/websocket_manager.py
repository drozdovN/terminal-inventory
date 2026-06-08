from typing import Dict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # Терминалы: serial_number -> WebSocket
        self.terminals: Dict[str, WebSocket] = {}
        # Браузеры поддержки: terminal_id -> WebSocket
        self.support: Dict[int, WebSocket] = {}

    async def connect_terminal(self, serial_number: str, websocket: WebSocket):
        await websocket.accept()
        self.terminals[serial_number] = websocket
        print(f"Терминал {serial_number} подключён")

    def disconnect_terminal(self, serial_number: str):
        self.terminals.pop(serial_number, None)
        print(f"Терминал {serial_number} отключён")

    async def connect_support(self, terminal_id: int, websocket: WebSocket):
        await websocket.accept()
        self.support[terminal_id] = websocket
        print(f"Поддержка подключена к терминалу #{terminal_id}")

    def disconnect_support(self, terminal_id: int):
        self.support.pop(terminal_id, None)
        print(f"Поддержка отключена от терминала #{terminal_id}")

    async def send_to_support(self, terminal_id: int, data: dict):
        ws = self.support.get(terminal_id)
        if ws:
            try:
                await ws.send_json(data)
            except:
                self.disconnect_support(terminal_id)

    async def send_to_terminal(self, serial_number: str, data: dict):
        ws = self.terminals.get(serial_number)
        if ws:
            try:
                await ws.send_json(data)
            except:
                self.disconnect_terminal(serial_number)

    def get_support_count(self, terminal_id: int) -> int:
        return 1 if terminal_id in self.support else 0


manager = ConnectionManager()