# Fleet Controller

A full-stack IoT fleet management system that simulates devices publishing sensor data via MQTT. Includes a FastAPI backend, React dashboard, and 10 simulated device replicas — all orchestrated with Docker Compose.

---

## Architecture

```
┌─────────────────┐      MQTT        ┌──────────────────┐
│ device-simulator│ ─────────────▶  │    Mosquitto     │
│   (×10 replicas)│                  │   MQTT Broker    │
└─────────────────┘                  └────────┬─────────┘
                                              │ MQTT subscribe
                                     ┌────────▼─────────┐
                                     │   fleet-server   │
                                     │   (FastAPI)      │
                                     │   SQLite + WS    │
                                     └────────┬─────────┘
                                              │ REST + WebSocket
                                     ┌────────▼─────────┐
                                     │    frontend      │
                                     │  (React + Vite)  │
                                     └──────────────────┘
```

### Services

| Service | Description | Port |
|---|---|---|
| `mosquitto` | Eclipse Mosquitto MQTT broker | 1883 |
| `fleet-server` | FastAPI backend — MQTT subscriber, REST API, WebSocket | 8000 |
| `frontend` | React dashboard served via nginx | 3000 |
| `device-simulator` | Python device simulator (10 replicas) | — |

---

## Quick Start

### Prerequisites
- Docker >= 24
- Docker Compose >= 2.20

### Run

```bash
# Clone and enter the project
cd fleet-controller

# Build and start all services with 10 device replicas
docker compose up --build --scale device-simulator=10
```

That's it. Open:
- **Dashboard** → http://localhost:3000
- **API docs** → http://localhost:8000/docs

### Stop

```bash
docker compose down
```

---

## Project Structure

```
fleet-controller/
├── docker-compose.yml
├── mosquitto/
│   └── config/
│       └── mosquitto.conf          # MQTT broker config
├── fleet-server/
│   ├── Dockerfile
│   ├── pyproject.toml              # Poetry dependencies
│   ├── alembic.ini                 # Alembic config
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_initial.py      # DB migration
│   └── app/
│       ├── config.py               # pydantic-settings config
│       ├── database.py             # SQLAlchemy engine + session
│       ├── models.py               # DeviceStat + CommandLog ORM models
│       ├── schemas.py              # Pydantic schemas
│       ├── mqtt_client.py          # MQTT subscriber, command publisher, WS broadcast
│       ├── main.py                 # FastAPI app + WebSocket endpoint
│       └── routers/
│           ├── devices.py          # /devices routes + command endpoints
│           └── stats.py            # /stats routes
├── device-simulator/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── simulator.py               # MQTT publisher with random sensors
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── src/
    │   ├── App.tsx
    │   ├── types.ts
    │   ├── api/client.ts           # Axios API wrappers
    │   └── components/
    │       ├── Dashboard.tsx       # Device grid + WebSocket
    │       ├── DeviceCard.tsx      # Per-device summary card
    │       ├── DeviceDetail.tsx    # History view + command panel
    │       └── SensorChart.tsx     # Recharts line chart
    └── ...config files
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/devices` | List all devices with latest stats |
| `GET` | `/devices/{id}/stats` | Latest stats for a specific device |
| `POST` | `/devices/{id}/commands` | Send a command to a device |
| `GET` | `/devices/{id}/commands` | Command history for a device (`?limit=`) |
| `GET` | `/stats` | Latest stats for all devices |
| `GET` | `/stats/history` | Historical data (`?device_id=&limit=`) |
| `GET` | `/health` | Health check |
| `WS` | `/ws` | WebSocket — real-time stats and command responses |

Full interactive docs at **http://localhost:8000/docs**.

---

## Data Flow

1. Each device simulator generates a random `device_id` and publishes JSON stats to `fleet/{device_id}/stats` every 2–5 seconds.
2. Mosquitto broker relays messages to all subscribers.
3. Fleet server subscribes to `fleet/+/stats`, persists each message to SQLite, and broadcasts to connected WebSocket clients.
4. The React dashboard connects via WebSocket for live updates and falls back to polling every 5 seconds.

### Stats message (`fleet/{device_id}/stats`)

```json
{
  "device_id": "device-a3f92c",
  "timestamp": "2024-06-01T12:00:00.000Z",
  "sensor1": 72.34,
  "sensor2": 45.11,
  "sensor3": 23.87
}
```

### Command flow

```
UI  ──POST /devices/{id}/commands──▶  fleet-server
                                           │ publish fleet/{id}/commands
                                           ▼
                                       Mosquitto
                                           │
                                           ▼
                                     device-simulator
                                           │ publish fleet/{id}/commands/response
                                           ▼
                                       Mosquitto
                                           │
                                      fleet-server  ── updates CommandLog in DB
                                           │           broadcasts command_response via WS
                                           ▼
                                          UI  (status updated in real time)
```

#### Command request body (`POST /devices/{id}/commands`)

```json
{
  "command": "reboot",
  "payload": { "delay_seconds": 5 }
}
```

`payload` is optional. Built-in preset commands: `ping`, `reboot`, `reset_sensors`, `report_full`.

#### Device response message (`fleet/{device_id}/commands/response`)

```json
{
  "device_id": "device-a3f92c",
  "command_id": "uuid",
  "status": "executed",
  "timestamp": "2024-06-01T12:00:01.000Z"
}
```

#### Command status lifecycle

| Status | Meaning |
|---|---|
| `sent` | Published to MQTT, awaiting device acknowledgement |
| `executed` | Device confirmed execution |
| `failed` | Device reported failure |

---

## Environment Variables

### fleet-server
| Variable | Default | Description |
|---|---|---|
| `MQTT_BROKER` | `localhost` | MQTT broker hostname |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `DATABASE_URL` | `sqlite:///./fleet.db` | SQLAlchemy DB URL |

### device-simulator
| Variable | Default | Description |
|---|---|---|
| `MQTT_BROKER` | `localhost` | MQTT broker hostname |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `DEVICE_ID` | random UUID | Override device identity |

---

## Local Development (without Docker)

### Backend

```bash
cd fleet-server
poetry install
poetry run uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Device Simulator

```bash
cd device-simulator
poetry install
DEVICE_ID=device-1 poetry run python simulator.py
```

Start Mosquitto separately (e.g. via `docker run -p 1883:1883 eclipse-mosquitto:2`).

---

## Database Migrations

```bash
cd fleet-server
# Apply migrations
poetry run alembic upgrade head

# Create a new migration
poetry run alembic revision --autogenerate -m "description"
```
