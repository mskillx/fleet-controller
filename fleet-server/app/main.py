import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app import models
from app.mqtt_client import start_mqtt_client, websocket_clients
from app.routers import devices, stats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)

mqtt_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global mqtt_client
    mqtt_client = start_mqtt_client()
    yield
    if mqtt_client:
        mqtt_client.disconnect()


app = FastAPI(title="Fleet Controller API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(devices.router)
app.include_router(stats.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    import asyncio

    websocket._loop = asyncio.get_event_loop()
    websocket_clients.add(websocket)
    logger.info(f"WebSocket client connected. Total: {len(websocket_clients)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_clients.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(websocket_clients)}")
