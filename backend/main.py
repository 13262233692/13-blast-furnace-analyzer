from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.api.routes import router
from backend.core.simulator_v2 import SensorSimulatorV2


@asynccontextmanager
async def lifespan(app: FastAPI):
    simulator = SensorSimulatorV2()
    app.state.simulator = simulator
    simulator.start()
    yield
    simulator.stop()


app = FastAPI(title="高炉侵蚀监测平台 V2 (高性能重构版)", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
