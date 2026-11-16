"""API tests: snapshot intake, live statuses, history and offline detection."""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw


def make_image(fill: float, size: int = 128) -> bytes:
    """Build a synthetic bin photo: ``fill`` is the dark (content) share."""
    image = Image.new("RGB", (size, size), (245, 245, 245))
    if fill > 0:
        draw = ImageDraw.Draw(image)
        height = int(size * fill)
        draw.rectangle((0, size - height, size, size), fill=(25, 25, 25))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def post_snapshot(client: TestClient, device_id: int, fill: float) -> dict:
    response = client.post(
        f"/devices/{device_id}/snapshot",
        files={"image": ("bin.png", make_image(fill), "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_create_bin_returns_unknown_status(client: TestClient, bin_factory) -> None:
    created = bin_factory("Бак у ЦУМа")
    assert created["status"] == "unknown"
    assert created["device_status"] == "unknown"

    listed = client.get("/bins").json()
    assert any(item["id"] == created["id"] for item in listed)


def test_snapshot_updates_bin_status_and_history(client: TestClient, bin_factory, device_factory) -> None:
    bin_obj = bin_factory("Бак на Токтогула")
    device = device_factory(bin_obj["id"])

    empty = post_snapshot(client, device["id"], fill=0.0)
    assert empty["status"] == "green"
    assert empty["confidence"] is not None and empty["confidence"] > 0.5
    assert empty["fill_ratio"] == 0.0

    image_response = client.get(empty["image_url"])
    assert image_response.status_code == 200
    assert image_response.headers["content-type"] == "image/png"

    statuses = {item["id"]: item["status"] for item in client.get("/bins").json()}
    assert statuses[bin_obj["id"]] == "green"

    full = post_snapshot(client, device["id"], fill=1.0)
    assert full["status"] == "red"
    assert full["fill_ratio"] == 1.0

    # Repeating the same status must not duplicate history rows.
    latest = post_snapshot(client, device["id"], fill=1.0)

    history = client.get(f"/bins/{bin_obj['id']}/history").json()
    assert [point["status"] for point in history] == ["green", "red"]

    detail = client.get(f"/bins/{bin_obj['id']}").json()
    assert detail["status"] == "red"
    assert detail["last_snapshot"]["id"] == latest["id"]
    assert detail["device_status"] == "online"
    assert len(detail["devices"]) == 1


def test_half_full_bin_is_yellow(client: TestClient, bin_factory, device_factory) -> None:
    bin_obj = bin_factory("Бак в парке")
    device = device_factory(bin_obj["id"])

    snapshot = post_snapshot(client, device["id"], fill=0.5)
    assert snapshot["status"] == "yellow"
    assert 0.4 < snapshot["fill_ratio"] < 0.6


def test_snapshot_rejects_invalid_payload(client: TestClient, bin_factory, device_factory) -> None:
    bin_obj = bin_factory("Бак для плохого фото")
    device = device_factory(bin_obj["id"])

    not_an_image = client.post(
        f"/devices/{device['id']}/snapshot",
        files={"image": ("note.txt", b"hello", "text/plain")},
    )
    assert not_an_image.status_code == 400

    unknown_device = client.post(
        "/devices/999999/snapshot",
        files={"image": ("bin.png", make_image(0.1), "image/png")},
    )
    assert unknown_device.status_code == 404


def test_history_range_filter(client: TestClient, bin_factory, device_factory) -> None:
    bin_obj = bin_factory("Бак с историей")
    device = device_factory(bin_obj["id"])
    post_snapshot(client, device["id"], fill=0.0)
    post_snapshot(client, device["id"], fill=0.8)

    future = client.get(
        f"/bins/{bin_obj['id']}/history", params={"from": "2999-01-01T00:00:00"}
    ).json()
    assert future == []

    everything = client.get(
        f"/bins/{bin_obj['id']}/history", params={"from": "2000-01-01T00:00:00"}
    ).json()
    assert len(everything) == 2


def test_offline_devices(client: TestClient, bin_factory, device_factory) -> None:
    bin_obj = bin_factory("Бак без связи")
    device = device_factory(bin_obj["id"])

    offline = client.get("/devices/offline").json()
    assert any(item["device_id"] == device["id"] for item in offline)

    post_snapshot(client, device["id"], fill=0.1)

    still_offline = client.get("/devices/offline").json()
    assert all(item["device_id"] != device["id"] for item in still_offline)

    device_detail = client.get(f"/bins/{bin_obj['id']}").json()["devices"][0]
    assert device_detail["status"] == "online"
    assert device_detail["last_seen_at"] is not None
