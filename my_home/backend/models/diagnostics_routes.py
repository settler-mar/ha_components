from fastapi import HTTPException, Query
from fastapi.responses import FileResponse

from utils.diagnostics import diagnostics


def add_diagnostics_routes(app, resolver):
    @app.get("/api/diagnostics/config-policy", tags=["diagnostics"])
    async def get_config_policy():
        return {"success": True, "policy": diagnostics.get_config_policy()}

    @app.put("/api/diagnostics/config-policy", tags=["diagnostics"])
    async def put_config_policy(payload: dict):
        try:
            return {"success": True, "policy": diagnostics.set_config_policy(payload)}
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))

    @app.get("/api/diagnostics/events", tags=["diagnostics"])
    async def diagnostic_events(limit: int = Query(500, ge=1, le=10000), event_type: str = None):
        return {"success": True, "events": diagnostics.events(limit, event_type)}

    @app.get("/api/diagnostics/coredumps/{device_id}/{filename}", tags=["diagnostics"])
    async def diagnostic_coredump(device_id: int, filename: str):
        try:
            path = diagnostics.dump_path(device_id, filename)
        except (ValueError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="Coredump not found")
        return FileResponse(path, filename=path.name, media_type="application/octet-stream")

    @app.get("/api/diagnostics/config-backup/{device_id}/{backup}/{filename:path}", tags=["diagnostics"])
    async def diagnostic_config_backup_file(device_id: int, backup: str, filename: str):
        try:
            path = diagnostics.config_backup_file(device_id, backup, filename)
        except (ValueError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="Configuration backup file not found")
        return FileResponse(path, filename=path.name, media_type="application/octet-stream")

    @app.post("/api/diagnostics/rollback", tags=["diagnostics"])
    async def rollback_configuration(payload: dict):
        device_id = payload.get("device_id")
        backup = payload.get("backup")
        if not device_id or not backup:
            raise HTTPException(status_code=400, detail="device_id and backup are required")
        client = resolver(int(device_id))
        if not client or not client.ip:
            raise HTTPException(status_code=404, detail="Device not found or IP is not configured")
        try:
            result = await diagnostics.rollback_to_backup(
                device_id=int(device_id), device_name=client.name, ip=client.ip,
                backup_name=backup, reason="manual_rollback_from_diagnostics",
            )
            return {"success": True, "result": result}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Configuration backup not found")
        except Exception as error:
            raise HTTPException(status_code=502, detail=str(error))
