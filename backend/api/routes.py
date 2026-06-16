from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json

router = APIRouter()


@router.get("/status")
async def get_status(request: Request):
    simulator = request.app.state.simulator
    data = simulator.get_current_data()
    if not data:
        return JSONResponse({"error": "数据尚未就绪"}, status_code=503)
    return data.get("status", {})


@router.get("/sensors")
async def get_sensors(request: Request):
    simulator = request.app.state.simulator
    data = simulator.get_current_data()
    if not data:
        return JSONResponse({"error": "数据尚未就绪"}, status_code=503)
    return {"readings": data.get("sensors", [])}


@router.get("/heatmap")
async def get_heatmap(request: Request):
    simulator = request.app.state.simulator
    data = simulator.get_current_data()
    if not data:
        return JSONResponse({"error": "数据尚未就绪"}, status_code=503)
    return {"layers": 8, "angles": 36, "temperatures": data.get("heatmap", [])}


@router.get("/thickness")
async def get_thickness(request: Request):
    simulator = request.app.state.simulator
    data = simulator.get_current_data()
    if not data:
        return JSONResponse({"error": "数据尚未就绪"}, status_code=503)
    return {"thickness_map": data.get("thickness_map", []), "status": data.get("status", {})}


@router.get("/thickness/layer/{layer_id}")
async def get_layer_thickness(layer_id: int, request: Request):
    simulator = request.app.state.simulator
    data = simulator.get_current_data()
    if not data:
        return JSONResponse({"error": "数据尚未就绪"}, status_code=503)
    thickness_map = data.get("thickness_map", [])
    if layer_id < 0 or layer_id >= len(thickness_map):
        return JSONResponse({"error": f"层 {layer_id} 不存在"}, status_code=404)
    angles = [i * 10 for i in range(36)]
    return {
        "layer": layer_id,
        "angles": angles,
        "thicknesses": thickness_map[layer_id],
    }


@router.get("/temperature/layer/{layer_id}")
async def get_layer_temperature(layer_id: int, request: Request):
    simulator = request.app.state.simulator
    data = simulator.get_current_data()
    if not data:
        return JSONResponse({"error": "数据尚未就绪"}, status_code=503)
    heatmap = data.get("heatmap", [])
    if layer_id < 0 or layer_id >= len(heatmap):
        return JSONResponse({"error": f"层 {layer_id} 不存在"}, status_code=404)
    angles = [i * 10 for i in range(36)]
    return {
        "layer": layer_id,
        "angles": angles,
        "temperatures": heatmap[layer_id],
    }
