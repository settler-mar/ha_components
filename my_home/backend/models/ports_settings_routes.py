"""
API endpoints for ports settings management
"""
import requests
from fastapi import APIRouter, HTTPException
from utils.db_utils import db_session
from db_models.devices import Devices as DbDevices

def add_ports_settings_routes(app: APIRouter):
    """Add ports settings routes to the app"""
    
    @app.get("/api/devices/{device_id}/logs-config")
    async def get_logs_config(device_id: int, refresh: bool = False):
        """Get logs configuration from device (with caching)"""
        try:
            with db_session() as db:
                device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                # Проверяем кешированную конфигурацию
                if not refresh and device.params and 'logs_config' in device.params:
                    cached_config = device.params['logs_config']
                    # Проверяем, не старше ли кеш 5 минут
                    if 'cached_at' in cached_config:
                        from datetime import datetime, timedelta
                        cached_at = datetime.fromisoformat(cached_config['cached_at'])
                        if datetime.now() - cached_at < timedelta(minutes=5):
                            return cached_config['data']
                
                ip = device.params.get('ip') if device.params else None
                if not ip:
                    raise HTTPException(status_code=400, detail="Device IP not configured")
                
                # Get logs configuration from device
                url = f"http://{ip}/logs"
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                
                config_data = response.json()
                
                # Кешируем конфигурацию
                if not device.params:
                    device.params = {}
                
                device.params['logs_config'] = {
                    'data': config_data,
                    'cached_at': datetime.now().isoformat()
                }
                db.commit()
                db.refresh(device)
                
                return config_data
                
        except requests.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Error connecting to device: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting logs config: {str(e)}")
    
    @app.post("/api/devices/{device_id}/logs-config")
    async def save_logs_config(device_id: int, config: dict):
        """Save logs configuration to device"""
        try:
            with db_session() as db:
                device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                ip = device.params.get('ip') if device.params else None
                if not ip:
                    raise HTTPException(status_code=400, detail="Device IP not configured")
                
                # Save logs configuration to device
                url = f"http://{ip}/logs"
                response = requests.post(url, json=config, timeout=5)
                response.raise_for_status()
                
                return {"message": "Logs configuration saved successfully"}
                
        except requests.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Error connecting to device: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error saving logs config: {str(e)}")
    
    @app.put("/api/devices/{device_id}/port-param/{port_code}")
    async def update_port_param(device_id: int, port_code: str, updates: dict):
        """Update port parameters"""
        try:
            with db_session() as db:
                device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                ip = device.params.get('ip') if device.params else None
                if not ip:
                    raise HTTPException(status_code=400, detail="Device IP not configured")
                
                # Update port parameter on device
                url = f"http://{ip}/set-param"
                data = {
                    "code": port_code,
                    "updates": updates
                }
                response = requests.post(url, json=data, timeout=5)
                response.raise_for_status()
                
                return {"message": "Port parameter updated successfully"}
                
        except requests.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Error connecting to device: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating port param: {str(e)}")
    
    @app.put("/api/devices/{device_id}/ha-settings")
    async def update_ha_settings(device_id: int, settings: dict):
        """Update HA publishing settings"""
        try:
            with db_session() as db:
                device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                # Update HA settings in database
                if not device.params:
                    device.params = {}
                
                device.params['haSettings'] = settings
                db.commit()
                db.refresh(device)
                
                return {"message": "HA settings updated successfully"}
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating HA settings: {str(e)}")
    
    @app.put("/api/devices/{device_id}/favorite-ports")
    async def update_favorite_ports(device_id: int, favorite_ports: list):
        """Update favorite ports list"""
        try:
            with db_session() as db:
                device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                # Update favorite ports in database
                if not device.params:
                    device.params = {}
                
                device.params['favoritePorts'] = favorite_ports
                db.commit()
                db.refresh(device)
                
                return {"message": "Favorite ports updated successfully"}
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating favorite ports: {str(e)}")
