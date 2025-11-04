"""
API endpoints for ports settings management
"""
import aiohttp
import asyncio
import json as json_lib
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from utils.db_utils import db_session
from db_models.devices import Devices as DbDevices
from utils.logger import api_logger as logger

def add_ports_settings_routes(app: APIRouter):
    """Add ports settings routes to the app"""
    
    @app.get("/api/devices/{device_id}/logs-config")
    async def get_logs_config(device_id: int, refresh: bool = False):
        """Get logs configuration from device (with caching)"""
        try:
            logger.info(f"Getting logs config for device {device_id}, refresh={refresh}")
            with db_session() as db:
                device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
                if not device:
                    logger.warning(f"Device {device_id} not found in database")
                    raise HTTPException(status_code=404, detail="Device not found")
                
                logger.debug(f"Device {device_id} found: {device.name if hasattr(device, 'name') else 'unknown'}")
                
                # Получаем params как словарь
                params = device.params if isinstance(device.params, dict) else {}
                
                # Проверяем кешированную конфигурацию
                if not refresh and 'logs_config' in params:
                    cached_config = params['logs_config']
                    # Проверяем, не старше ли кеш 5 минут
                    if isinstance(cached_config, dict) and 'cached_at' in cached_config:
                        try:
                            cached_at = datetime.fromisoformat(cached_config['cached_at'])
                            if datetime.now() - cached_at < timedelta(minutes=5):
                                logger.info(f"Returning cached logs config for device {device_id}")
                                return cached_config.get('data', {})
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Invalid cache date for device {device_id}: {e}")
                            # Если дата невалидна, пропускаем кеш
                            pass
                
                ip = params.get('ip')
                if not ip:
                    logger.warning(f"Device {device_id} IP not configured in params: {params}")
                    raise HTTPException(status_code=400, detail="Device IP not configured")
                
                logger.info(f"Fetching logs config from device {device_id} at IP {ip}")
                
                # Get logs configuration from device
                url = f"http://{ip}/logs"
                config_data = {}
                
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                            response_text = await response.text()
                            logger.debug(f"Device {device_id} response status: {response.status}, length: {len(response_text)}")
                            
                            if response.status != 200:
                                logger.error(f"Device {device_id} returned status {response.status}: {response_text[:500]}")
                                raise HTTPException(
                                    status_code=500,
                                    detail=f"Device returned status {response.status}: {response_text[:200]}"
                                )
                            
                            # Пытаемся получить JSON
                            try:
                                config_data = await response.json()
                                logger.debug(f"Successfully parsed JSON from device {device_id}, keys: {list(config_data.keys()) if isinstance(config_data, dict) else 'not a dict'}")
                            except (json_lib.JSONDecodeError, aiohttp.ContentTypeError) as e:
                                logger.warning(f"Invalid JSON response from device {device_id}: {str(e)}, response: {response_text[:500]}")
                                # Возвращаем пустой словарь, если устройство не поддерживает logs-config или вернуло невалидный JSON
                                config_data = {}
                except asyncio.TimeoutError:
                    logger.error(f"Timeout connecting to device {device_id} at {url}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Timeout connecting to device"
                    )
                except aiohttp.ClientConnectorError as e:
                    logger.error(f"Cannot connect to device {device_id} at {url}: {str(e)}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Cannot connect to device: {str(e)}"
                    )
                except aiohttp.ClientError as e:
                    logger.error(f"Client error connecting to device {device_id} at {url}: {str(e)}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error connecting to device: {str(e)}"
                    )
                
                # Кешируем конфигурацию (даже если она пустая)
                try:
                    params['logs_config'] = {
                        'data': config_data,
                        'cached_at': datetime.now().isoformat()
                    }
                    device.params = params
                    db.commit()
                    db.refresh(device)
                    logger.debug(f"Cached logs config for device {device_id}")
                except Exception as e:
                    logger.error(f"Error caching logs config for device {device_id}: {str(e)}", exc_info=True)
                    # Не падаем, если кеширование не удалось
                
                return config_data
                
        except HTTPException:
            # Пробрасываем HTTPException без изменений
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting logs config for device {device_id}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error getting logs config: {str(e)}")
    
    @app.post("/api/devices/{device_id}/logs-config")
    async def save_logs_config(device_id: int, config: dict):
        """Save logs configuration to device"""
        try:
            with db_session() as db:
                device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                params = device.params if isinstance(device.params, dict) else {}
                ip = params.get('ip')
                if not ip:
                    raise HTTPException(status_code=400, detail="Device IP not configured")
                
                # Save logs configuration to device
                url = f"http://{ip}/logs"
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=config, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        if response.status != 200:
                            raise HTTPException(
                                status_code=response.status,
                                detail=f"Device returned status {response.status}"
                            )
                
                return {"message": "Logs configuration saved successfully"}
                
        except aiohttp.ClientError as e:
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
                
                params = device.params if isinstance(device.params, dict) else {}
                ip = params.get('ip')
                if not ip:
                    raise HTTPException(status_code=400, detail="Device IP not configured")
                
                # Update port parameter on device
                url = f"http://{ip}/set-param"
                data = {
                    "code": port_code,
                    "updates": updates
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        if response.status != 200:
                            raise HTTPException(
                                status_code=response.status,
                                detail=f"Device returned status {response.status}"
                            )
                
                return {"message": "Port parameter updated successfully"}
                
        except aiohttp.ClientError as e:
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
                params = device.params if isinstance(device.params, dict) else {}
                params['haSettings'] = settings
                device.params = params
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
                params = device.params if isinstance(device.params, dict) else {}
                params['favoritePorts'] = favorite_ports
                device.params = params
                db.commit()
                db.refresh(device)
                
                return {"message": "Favorite ports updated successfully"}
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating favorite ports: {str(e)}")
