"""SQLAlchemy models: bins, devices, snapshots, status history."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# Statuses stored in the database.
SNAPSHOT_STATUSES = ("pending", "green", "yellow", "red", "needs_review")


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite has no timezone support)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Bin(Base):
    __tablename__ = "bins"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    district: Mapped[str | None] = mapped_column(String(120))
    installed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    devices: Mapped[list["Device"]] = relationship(
        back_populates="bin", cascade="all, delete-orphan", order_by="Device.id"
    )
    snapshots: Mapped[list["Snapshot"]] = relationship(
        back_populates="bin", cascade="all, delete-orphan"
    )
    history: Mapped[list["StatusHistory"]] = relationship(
        back_populates="bin", cascade="all, delete-orphan"
    )


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    bin_id: Mapped[int] = mapped_column(ForeignKey("bins.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(40), default="virtual", nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="offline", nullable=False)

    bin: Mapped[Bin] = relationship(back_populates="devices")


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    bin_id: Mapped[int] = mapped_column(ForeignKey("bins.id", ondelete="CASCADE"), index=True)
    image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    taken_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    fill_ratio: Mapped[float | None] = mapped_column(Float)

    bin: Mapped[Bin] = relationship(back_populates="snapshots")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    bin_id: Mapped[int] = mapped_column(ForeignKey("bins.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)

    bin: Mapped[Bin] = relationship(back_populates="history")
