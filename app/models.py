from datetime import datetime, date, timezone, timedelta

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, ForeignKey, Text, CheckConstraint
)
from sqlalchemy.orm import relationship

from app.database import Base

MSK = timezone(timedelta(hours=3))


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="warehouse")
    created_at = Column(DateTime, default=lambda: datetime.now(MSK))

    status_changes = relationship("StatusHistory", back_populates="changed_by_user")


class Terminal(Base):
    __tablename__ = "terminals"

    id = Column(Integer, primary_key=True, index=True)
    model = Column(String, nullable=False)
    firmware_version = Column(String, nullable=False)
    serial_number = Column(String, unique=True, nullable=False)
    box_number = Column(String, nullable=False, index=True)
    arrival_date = Column(Date, nullable=False, default=date.today)
    status = Column(String, nullable=False, default="warehouse", index=True)
    defect_type = Column(String, nullable=True)
    defect_comment = Column(Text, nullable=True)
    bank = Column(String, nullable=True)
    responsible_person = Column(String, nullable=False)
    last_seen = Column(DateTime, nullable=True)
    brightness = Column(Integer, nullable=True, default=255)
    volume = Column(Integer, nullable=True, default=100)
    bluetooth = Column(Integer, nullable=True, default=0)  # 1 = вкл, 0 = выкл
    created_at = Column(DateTime, default=lambda: datetime.now(MSK))
    updated_at = Column(DateTime, default=lambda: datetime.now(MSK), onupdate=lambda: datetime.now(MSK))

    __table_args__ = (
        CheckConstraint(
            "status IN ('warehouse', 'reserved', 'defective', 'repair', 'shipped')",
            name="check_status"
        ),
        CheckConstraint(
            "defect_type IS NULL OR defect_type IN "
            "('display', 'battery', 'reader', 'firmware', 'case', 'other')",
            name="check_defect_type"
        ),
    )

    history = relationship("StatusHistory", back_populates="terminal", order_by="StatusHistory.changed_at.desc()")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id = Column(Integer, primary_key=True, index=True)
    terminal_id = Column(Integer, ForeignKey("terminals.id"), nullable=False)
    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=False)
    old_bank = Column(String, nullable=True)
    new_bank = Column(String, nullable=True)
    old_defect_type = Column(String, nullable=True)
    new_defect_type = Column(String, nullable=True)
    defect_comment = Column(Text, nullable=True)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime, default=lambda: datetime.now(MSK))
    comment = Column(Text, nullable=True)

    terminal = relationship("Terminal", back_populates="history")
    changed_by_user = relationship("User", back_populates="status_changes")

class ApkFile(Base):
    __tablename__ = "apk_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    version = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    target_serial = Column(String, nullable=True)  # null = всем, "SN123" = конкретному
    uploaded_at = Column(DateTime, default=lambda: datetime.now(MSK))