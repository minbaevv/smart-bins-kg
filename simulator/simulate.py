"""Virtual IoT camera: posts synthetic bin photos to the backend on a timer.

Stage 2 of the plan: no hardware required. Fill level grows every tick, and
after a full bin it drops to empty — imitating a collection round.
"""

from __future__ import annotations

import io
import os
import random
import time

import httpx
from PIL import Image, ImageDraw

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
INTERVAL = float(os.getenv("SIM_INTERVAL", "10"))
IMAGE_SIZE = 320
MAX_TICKS = int(os.getenv("SIM_MAX_TICKS", "0"))  # 0 = run forever

DEMO_BINS = [
    {"name": "Бак №1 — ул. Киевская", "lat": 42.8746, "lon": 74.5698, "district": "Бишкек"},
    {"name": "Бак №2 — ул. Чуй, 120", "lat": 42.8769, "lon": 74.5901, "district": "Бишкек"},
    {"name": "Бак №3 — Ош, ул. Ленина", "lat": 40.5283, "lon": 72.7985, "district": "Ош"},
]


def wait_for_backend(client: httpx.Client, attempts: int = 30) -> None:
    for attempt in range(1, attempts + 1):
        try:
            if client.get(f"{API_URL}/health").status_code == 200:
                print(f"backend is up ({API_URL})")
                return
        except httpx.HTTPError:
            pass
        print(f"waiting for backend, attempt {attempt}/{attempts}")
        time.sleep(2)
    raise SystemExit(f"backend at {API_URL} is not reachable")


def render_bin_photo(fill: float) -> bytes:
    """Draw a bright yard frame with a dark rectangle of bin content."""
    image = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), (232, 235, 238))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, int(IMAGE_SIZE * 0.75), IMAGE_SIZE, IMAGE_SIZE), fill=(120, 122, 124))
    if fill > 0:
        height = int(IMAGE_SIZE * 0.75 * fill)
        draw.rectangle(
            (0, int(IMAGE_SIZE * 0.75) - height, IMAGE_SIZE, int(IMAGE_SIZE * 0.75)),
            fill=(28, 30, 32),
        )
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def ensure_demo_fleet(client: httpx.Client) -> list[dict]:
    bins = client.get(f"{API_URL}/bins").json()
    devices = []
    for bin_payload in bins:
        for device in client.get(f"{API_URL}/bins/{bin_payload['id']}").json()["devices"]:
            devices.append({"device_id": device["id"], "name": bin_payload["name"], "fill": 0.0})
    if devices:
        print(f"using existing fleet: {len(devices)} device(s)")
        return devices

    for spec in DEMO_BINS:
        created_bin = client.post(f"{API_URL}/bins", json=spec).json()
        created_device = client.post(
            f"{API_URL}/devices", json={"bin_id": created_bin["id"], "type": "virtual"}
        ).json()
        devices.append(
            {"device_id": created_device["id"], "name": created_bin["name"], "fill": 0.0}
        )
    print(f"created demo fleet: {len(devices)} bins")
    return devices


def main() -> None:
    with httpx.Client(timeout=10.0) as client:
        wait_for_backend(client)
        devices = ensure_demo_fleet(client)
        tick = 0
        while True:
            tick += 1
            for device in devices:
                device["fill"] = min(1.0, device["fill"] + random.uniform(0.12, 0.3))
                if device["fill"] >= 1.0:
                    device["fill"] = 1.0
                response = client.post(
                    f"{API_URL}/devices/{device['device_id']}/snapshot",
                    files={"image": ("frame.jpg", render_bin_photo(device["fill"]), "image/jpeg")},
                )
                payload = response.json()
                print(
                    f"[tick {tick:03d}] {device['name']}: fill={device['fill']:.2f} "
                    f"-> {payload.get('status')} ({payload.get('confidence')})"
                )
                if device["fill"] >= 1.0:
                    device["fill"] = 0.0  # emulated collection round
            if MAX_TICKS and tick >= MAX_TICKS:
                break
            time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
