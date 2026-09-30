from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, constr, field_validator, model_validator


# ============ ПОЛЬЗОВАТЕЛЬ ============
class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=50, pattern=r'^[A-Za-z0-9_]+$')
    password: constr(min_length=6, max_length=100)
    role: str

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        if v not in ('admin', 'warehouse'):
            raise ValueError('Роль должна быть admin или warehouse')
        return v


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


# ============ ТЕРМИНАЛ ============
class TerminalCreate(BaseModel):
    model: constr(min_length=2, max_length=100)
    firmware_version: constr(min_length=1, max_length=50)
    serial_number: constr(min_length=3, max_length=50, pattern=r'^[A-Za-z0-9\-]+$')
    box_number: constr(min_length=1, max_length=50)
    arrival_date: date

    @field_validator('arrival_date')
    @classmethod
    def validate_arrival_date(cls, v):
        if v > date.today():
            raise ValueError('Дата прихода не может быть в будущем')
        if v.year < 2020:
            raise ValueError('Дата прихода слишком ранняя')
        return v


class TerminalUpdate(BaseModel):
    model: constr(min_length=2, max_length=100)
    firmware_version: constr(min_length=1, max_length=50)
    serial_number: constr(min_length=3, max_length=50, pattern=r'^[A-Za-z0-9\-]+$')
    box_number: constr(min_length=1, max_length=50)
    status: str
    bank: Optional[str] = None
    defect_type: Optional[str] = None
    defect_comment: Optional[str] = None
    arrival_date: date

    @field_validator('arrival_date')
    @classmethod
    def validate_arrival_date(cls, v):
        if v > date.today():
            raise ValueError('Дата прихода не может быть в будущем')
        if v.year < 2020:
            raise ValueError('Дата прихода слишком ранняя')
        return v

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        allowed = ('warehouse', 'reserved', 'defective', 'repair', 'shipped')
        if v not in allowed:
            raise ValueError(f'Недопустимый статус: {v}')
        return v

    @model_validator(mode='after')
    def validate_conditional(self):
        # Банк обязателен для reserved/shipped
        if self.status in ('reserved', 'shipped'):
            if not self.bank or len(self.bank.strip()) < 2:
                raise ValueError('Для статусов "Забронировано" и "Отгружено" нужно указать банк')

        # Тип брака и комментарий обязательны для defective/repair
        if self.status in ('defective', 'repair'):
            if not self.defect_type:
                raise ValueError('Для статусов "Брак" и "Ремонт" нужно указать тип брака')
            if self.defect_type not in ('display', 'battery', 'reader', 'firmware', 'case', 'other'):
                raise ValueError(f'Недопустимый тип брака: {self.defect_type}')
            if not self.defect_comment or len(self.defect_comment.strip()) < 5:
                raise ValueError('Комментарий к браку обязателен (минимум 5 символов)')

        return self


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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ СМЕНА СТАТУСА ============
class StatusChange(BaseModel):
    new_status: str
    bank: Optional[str] = None
    defect_type: Optional[str] = None
    defect_comment: Optional[str] = None
    comment: Optional[str] = None

    @field_validator('new_status')
    @classmethod
    def validate_status(cls, v):
        allowed = ('warehouse', 'reserved', 'defective', 'repair', 'shipped')
        if v not in allowed:
            raise ValueError(f'Недопустимый статус: {v}')
        return v

    @model_validator(mode='after')
    def validate_conditional(self):
        if self.new_status in ('reserved', 'shipped'):
            if not self.bank or len(self.bank.strip()) < 2:
                raise ValueError('Для этого статуса нужно указать банк')

        if self.new_status in ('defective', 'repair'):
            if not self.defect_type:
                raise ValueError('Укажите тип брака')
            if self.defect_type not in ('display', 'battery', 'reader', 'firmware', 'case', 'other'):
                raise ValueError(f'Недопустимый тип брака: {self.defect_type}')
            if not self.defect_comment or len(self.defect_comment.strip()) < 5:
                raise ValueError('Комментарий к браку обязателен (минимум 5 символов)')

        return self


# ============ ИСТОРИЯ ============
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