"""Bins API: CRUD-lite, live statuses and fill history."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Bin, Device, Snapshot, StatusHistory, utcnow
from ..schemas import BinCreate, BinDetail, BinOut, HistoryPoint

router = APIRouter(prefix="/bins", tags=["bins"])

HISTORY_LIMIT = 200


def _latest_snapshot_id():
    return (
        select(func.max(Snapshot.id))
        .where(Snapshot.bin_id == Bin.id)
        .correlate(Bin)
        .scalar_subquery()
    )


def _latest_device_id():
    return (
        select(func.max(Device.id))
        .where(Device.bin_id == Bin.id)
        .correlate(Bin)
        .scalar_subquery()
    )


def _device_status(device: Device | None, now: datetime) -> str:
    if device is None or device.last_seen_at is None:
        return "unknown" if device is None else "offline"
    fresh_after = now - timedelta(hours=settings.offline_after_hours)
    return "online" if device.last_seen_at >= fresh_after else "offline"


def _status_payload(bin_obj: Bin, snapshot: Snapshot | None, device: Device | None) -> dict:
    return {
        "id": bin_obj.id,
        "name": bin_obj.name,
        "lat": bin_obj.lat,
        "lon": bin_obj.lon,
        "district": bin_obj.district,
        "installed_at": bin_obj.installed_at,
        "status": snapshot.status if snapshot else "unknown",
        "confidence": snapshot.confidence if snapshot else None,
        "fill_ratio": snapshot.fill_ratio if snapshot else None,
        "last_snapshot_at": snapshot.taken_at if snapshot else None,
        "device_status": _device_status(device, utcnow()),
        "last_seen_at": device.last_seen_at if device else None,
    }


def _get_bin_or_404(db: Session, bin_id: int) -> Bin:
    bin_obj = db.get(Bin, bin_id)
    if bin_obj is None:
        raise HTTPException(status_code=404, detail="bin not found")
    return bin_obj


def _latest_snapshot(db: Session, bin_id: int) -> Snapshot | None:
    return db.execute(
        select(Snapshot)
        .where(Snapshot.bin_id == bin_id)
        .order_by(Snapshot.taken_at.desc(), Snapshot.id.desc())
        .limit(1)
    ).scalar_one_or_none()


@router.post("", response_model=BinOut, status_code=201)
def create_bin(payload: BinCreate, db: Session = Depends(get_db)) -> dict:
    bin_obj = Bin(**payload.model_dump())
    db.add(bin_obj)
    db.commit()
    db.refresh(bin_obj)
    return _status_payload(bin_obj, None, None)


@router.get("", response_model=list[BinOut])
def list_bins(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(Bin, Snapshot, Device)
        .outerjoin(Snapshot, Snapshot.id == _latest_snapshot_id())
        .outerjoin(Device, Device.id == _latest_device_id())
        .order_by(Bin.id)
    ).all()
    return [_status_payload(bin_obj, snapshot, device) for bin_obj, snapshot, device in rows]


@router.get("/{bin_id}", response_model=BinDetail)
def get_bin(bin_id: int, db: Session = Depends(get_db)) -> dict:
    bin_obj = _get_bin_or_404(db, bin_id)
    snapshot = _latest_snapshot(db, bin_id)
    device = bin_obj.devices[-1] if bin_obj.devices else None
    payload = _status_payload(bin_obj, snapshot, device)
    payload.update(
        {
            "devices": bin_obj.devices,
            "history": bin_obj.history[-HISTORY_LIMIT:],
            "last_snapshot": snapshot,
        }
    )
    return payload


@router.get("/{bin_id}/history", response_model=list[HistoryPoint])
def get_history(
    bin_id: int,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[StatusHistory]:
    _get_bin_or_404(db, bin_id)
    query = select(StatusHistory).where(StatusHistory.bin_id == bin_id)
    if from_ is not None:
        query = query.where(StatusHistory.changed_at >= from_)
    if to is not None:
        query = query.where(StatusHistory.changed_at <= to)
    return list(
        db.execute(query.order_by(StatusHistory.changed_at, StatusHistory.id).limit(HISTORY_LIMIT))
        .scalars()
        .all()
    )
