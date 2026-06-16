from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.api.routes import router
from backend.core.simulator import SensorSimulator


@asynccontextmanager
async def lifespan(app: FastAPI):
    simulator = SensorSimulator()
    app.state.simulator = simulator
    simulator.start()
    yield
    simulator.stop()


app = FastAPI(title="高炉侵蚀监测平台", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
