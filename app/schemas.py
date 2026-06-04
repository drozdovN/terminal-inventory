from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, constr


class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=50)
    password: constr(min_length=4)
    role: str = "warehouse"


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class TerminalCreate(BaseModel):
    model: str
    firmware_version: str
    serial_number: str
    box_number: str
    arrival_date: date
    responsible_person: str


class TerminalUpdate(BaseModel):
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    box_number: Optional[str] = None
    responsible_person: Optional[str] = None


class TerminalOut(BaseModel):
    id: int
    model: str
    firmware_version: str
    serial_number: str
    box_number: str
    arrival_date: date
    status: str
    defect_type: Optional[str] = None
    defect_comment: Optional[str] = None
    bank: Optional[str] = None
    responsible_person: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StatusChange(BaseModel):
    new_status: str
    bank: Optional[str] = None
    defect_type: Optional[str] = None
    defect_comment: Optional[str] = None
    comment: Optional[str] = None


class StatusHistoryOut(BaseModel):
    id: int
    terminal_id: int
    old_status: Optional[str] = None
    new_status: str
    old_bank: Optional[str] = None
    new_bank: Optional[str] = None
    old_defect_type: Optional[str] = None
    new_defect_type: Optional[str] = None
    defect_comment: Optional[str] = None
    changed_by: int
    changed_at: datetime
    comment: Optional[str] = None

    class Config:
        from_attributes = True