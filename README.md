# Smart Bins KG

Мониторинг заполненности мусорных баков для Кыргызстана: IoT-камеры (или
симулятор) → Computer Vision → статус бака на карте в реальном времени.

MVP по плану: сеть баков, автоматическое обновление статуса по фото,
история изменений и REST API для коммунальных служб.

## Что уже работает (этапы 0–2)

- [x] Структура репозитория: `backend/`, `frontend/`, `simulator/`, `infra/`
- [x] FastAPI + SQLAlchemy: `bins`, `devices`, `snapshots`, `status_history`
- [x] Приём фото: `POST /devices/{device_id}/snapshot` (multipart), файл сохраняется, статус считается
- [x] CV-baseline: ROI + ресайз (`app/cv/preprocessing.py`) и классификатор `empty/half/full` с confidence
- [x] `GET /bins` — баки со статусом, уверенностью и состоянием устройства
- [x] `GET /bins/{id}` — детали, устройства, последний снимок, история
- [x] `GET /bins/{id}/history?from=&to=` — история заполненности
- [x] `GET /devices/offline?hours=` — баки без связи
- [x] Симулятор виртуальных камер (`simulator/simulate.py`)
- [x] Карта на Leaflet + список баков + фильтры (`frontend/`)
- [x] Docker Compose: postgres/PostGIS, redis, backend, simulator, frontend
- [x] CI: pytest на каждый push
- [ ] Alembic-миграции (сейчас таблицы создаются на старте)
- [ ] Обученный CNN (MobileNetV3/ResNet18) вместо эвристики
- [ ] Celery-воркер вместо синхронной обработки
- [ ] LangChain-агент и оптимизация маршрутов (после MVP)

## Быстрый старт

### Docker Compose (весь стек)

```bash
cd infra
docker compose up --build
```

- Карта: http://localhost:8080
- API: http://localhost:8000/docs
- Симулятор сам создаёт 3 демо-бака и шлёт фото каждые 10 секунд.

### Локально (только backend + тесты)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
pytest
```

SQLite используется по умолчанию (`DATABASE_URL=sqlite:///./smart_bins.db`),
PostgreSQL — через переменную окружения.

### Симулятор отдельно

```bash
cd simulator
pip install -r requirements.txt
python simulate.py              # API_URL=http://localhost:8000
```

### Карта без Docker

```bash
python -m http.server 8080 -d frontend
# открыть http://localhost:8080/?api=http://localhost:8000
```

## API

| Метод | Путь | Назначение |
| --- | --- | --- |
| `POST` | `/bins` | создать бак |
| `GET` | `/bins` | список баков со статусами |
| `GET` | `/bins/{id}` | бак + устройства + последнее фото + история |
| `GET` | `/bins/{id}/history?from=&to=` | история статусов |
| `POST` | `/devices` | зарегистрировать устройство |
| `POST` | `/devices/{id}/snapshot` | принять фото (`multipart/form-data`, поле `image`) |
| `GET` | `/devices/offline?hours=6` | устройства без связи |
| `GET` | `/health` | проверка живости |

Пример:

```bash
curl -X POST http://localhost:8000/devices/1/snapshot -F "image=@bin.jpg"
```

Ответ:

```json
{"id": 1, "bin_id": 1, "image_url": "/media/6f1c....jpg",
 "taken_at": "2026-11-16T10:00:00", "status": "red",
 "confidence": 0.95, "fill_ratio": 0.82}
```

## Статусы

| Статус | Значение |
| --- | --- |
| `green` | бак пустой |
| `yellow` | наполовину |
| `red` | полный |
| `needs_review` | низкая уверенность модели, нужен человек |
| `unknown` | снимков ещё не было |

## Про CV

`backend/app/cv/classifier.py` — **baseline, а не обученная модель**: внутри ROI
считается доля тёмных пикселей (содержимое бака) и по порогам выдаётся статус и
confidence. Это позволяет проверить весь пайплайн без датасета и железа.

`CV_MODE=stub` возвращает `needs_review` с confidence 0 — режим для демо, где
нельзя показывать выдуманные статусы.

Замена на MobileNetV3/ResNet18 — это правка одной функции `predict()`: вход
(байты изображения) и выход (`Prediction`) уже зафиксированы. Препроцессинг
(фиксированный ROI + ресайз 224×224) переносится в обучение один в один.

## Структура

```
backend/
  app/
    main.py            FastAPI, CORS, /media
    config.py          настройки из env
    db.py              engine + сессии
    models.py          bins / devices / snapshots / status_history
    schemas.py         Pydantic-схемы API
    routers/           bins.py, devices.py
    cv/                preprocessing.py, classifier.py
    storage.py         сохранение фото (позже — S3/MinIO)
  tests/               pytest + TestClient, изолированная SQLite
simulator/             виртуальные IoT-камеры
frontend/              Leaflet-карта + дэшборд
infra/                 docker-compose.yml
.github/workflows/ci.yml
```

## Ограничения MVP

- Обработка снимка синхронная, без очереди — на реальном потоке камер это
  узкое место, поэтому в compose уже стоит Redis под Celery.
- Эвристический классификатор чувствителен к освещению: нужен обученный CNN.
- Нет аутентификации API (планируется на этапе 6).
- Фото лежат на локальном диске; в проде — S3/MinIO.
