"""Pydantic schemas for the public API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BinCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    district: str | None = Field(default=None, max_length=120)


class BinOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    lat: float
    lon: float
    district: str | None
    installed_at: datetime
    status: str
    confidence: float | None = None
    fill_ratio: float | None = None
    last_snapshot_at: datetime | None = None
    device_status: str = "unknown"
    last_seen_at: datetime | None = None


class DeviceCreate(BaseModel):
    bin_id: int = Field(gt=0)
    type: str = Field(default="virtual", max_length=40)


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bin_id: int
    type: str
    last_seen_at: datetime | None
    status: str


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bin_id: int
    image_url: str
    taken_at: datetime
    status: str
    confidence: float | None
    fill_ratio: float | None


class HistoryPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    changed_at: datetime


class BinDetail(BinOut):
    devices: list[DeviceOut] = Field(default_factory=list)
    history: list[HistoryPoint] = Field(default_factory=list)
    last_snapshot: SnapshotOut | None = None


class OfflineDeviceOut(BaseModel):
    device_id: int
    bin_id: int
    bin_name: str
    district: str | None
    last_seen_at: datetime | None
    hours_since_seen: float | None


class HealthOut(BaseModel):
    status: str
