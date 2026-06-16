from pydantic import BaseModel
from typing import List, Optional


class SensorReading(BaseModel):
    sensor_id: str
    layer: int
    angle: int
    temperature: float
    timestamp: float


class SensorBatch(BaseModel):
    readings: List[SensorReading]


class HeatmapData(BaseModel):
    layers: int
    angles: int
    temperatures: List[List[float]]


class ThicknessPoint(BaseModel):
    layer: int
    angle: int
    remaining_thickness_mm: float
    original_thickness_mm: float
    erosion_ratio: float


class ThicknessOverview(BaseModel):
    points: List[ThicknessPoint]
    timestamp: float


class LayerThicknessSeries(BaseModel):
    layer: int
    angles: List[int]
    thicknesses: List[float]


class FurnaceStatus(BaseModel):
    total_sensors: int
    active_sensors: int
    min_thickness_mm: float
    max_erosion_ratio: float
    alert_level: str
