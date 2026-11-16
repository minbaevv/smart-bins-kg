"""Devices API: registration, snapshot intake and offline detection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from PIL import UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..cv import predict
from ..db import get_db
from ..models import Bin, Device, Snapshot, StatusHistory, utcnow
from ..schemas import DeviceCreate, DeviceOut, OfflineDeviceOut, SnapshotOut
from ..storage import save_image

router = APIRouter(tags=["devices"])


def _to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


@router.post("/devices", response_model=DeviceOut, status_code=201)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db)) -> Device:
    if db.get(Bin, payload.bin_id) is None:
        raise HTTPException(status_code=404, detail="bin not found")
    device = Device(**payload.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get("/devices/offline", response_model=list[OfflineDeviceOut])
def list_offline_devices(
    hours: float | None = Query(default=None, gt=0, le=24 * 30),
    db: Session = Depends(get_db),
) -> list[OfflineDeviceOut]:
    window = settings.offline_after_hours if hours is None else hours
    now = utcnow()
    cutoff = now - timedelta(hours=window)
    rows = db.execute(
        select(Device, Bin)
        .join(Bin, Bin.id == Device.bin_id)
        .where((Device.last_seen_at.is_(None)) | (Device.last_seen_at < cutoff))
        .order_by(Bin.id)
    ).all()
    result: list[OfflineDeviceOut] = []
    for device, bin_obj in rows:
        hours_since = None
        if device.last_seen_at is not None:
            hours_since = round((now - device.last_seen_at).total_seconds() / 3600, 2)
        result.append(
            OfflineDeviceOut(
                device_id=device.id,
                bin_id=bin_obj.id,
                bin_name=bin_obj.name,
                district=bin_obj.district,
                last_seen_at=device.last_seen_at,
                hours_since_seen=hours_since,
            )
        )
    return result


@router.post("/devices/{device_id}/snapshot", response_model=SnapshotOut, status_code=201)
async def upload_snapshot(
    device_id: int,
    image: UploadFile = File(...),
    taken_at: datetime | None = Form(default=None),
    db: Session = Depends(get_db),
) -> Snapshot:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="device not found")

    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty image")
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="image too large")

    try:
        prediction = predict(raw)
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="invalid image") from exc

    image_url, _ = save_image(raw, image.filename)
    received_at = utcnow()
    shot_at = _to_naive_utc(taken_at) if taken_at is not None else received_at

    previous_status = db.execute(
        select(Snapshot.status)
        .where(Snapshot.bin_id == device.bin_id)
        .order_by(Snapshot.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    snapshot = Snapshot(
        bin_id=device.bin_id,
        image_url=image_url,
        taken_at=shot_at,
        status=prediction.status,
        confidence=prediction.confidence,
        fill_ratio=prediction.fill_ratio,
    )
    db.add(snapshot)

    device.last_seen_at = received_at
    device.status = "online"

    if previous_status != prediction.status:
        db.add(StatusHistory(bin_id=device.bin_id, status=prediction.status, changed_at=shot_at))

    db.commit()
    db.refresh(snapshot)
    return snapshot
