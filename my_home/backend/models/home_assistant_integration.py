"""
Интеграция с Home Assistant для публикации данных устройств
"""
import asyncio
import aiohttp
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from db_models.devices import Devices
from db_models.ports import Ports
from utils.db_utils import db_session
from utils.configs import config


class HomeAssistantClient:
    """Клиент для работы с Home Assistant API"""
    
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.session = None
        self._connected = False
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={'Authorization': f'Bearer {self.token}'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_connection(self) -> bool:
        """Тестирование подключения к Home Assistant"""
        try:
            async with self.session.get(f'{self.base_url}/api/') as response:
                self._connected = response.status == 200
                return self._connected
        except Exception as e:
            print(f"[HA] Connection test failed: {e}")
            self._connected = False
            return False
    
    async def create_entity(self, entity_data: Dict[str, Any]) -> bool:
        """Создание сущности в Home Assistant"""
        try:
            async with self.session.post(
                f'{self.base_url}/api/states/{entity_data["entity_id"]}',
                json=entity_data
            ) as response:
                return response.status in [200, 201]
        except Exception as e:
            print(f"[HA] Failed to create entity {entity_data.get('entity_id')}: {e}")
            return False
    
    async def update_entity(self, entity_id: str, state: Any, attributes: Dict[str, Any] = None) -> bool:
        """Обновление состояния сущности"""
        try:
            data = {
                'state': state,
                'attributes': attributes or {}
            }
            async with self.session.post(
                f'{self.base_url}/api/states/{entity_id}',
                json=data
            ) as response:
                return response.status in [200, 201]
        except Exception as e:
            print(f"[HA] Failed to update entity {entity_id}: {e}")
            return False
    
    async def get_entities(self, domain: str = None) -> List[Dict[str, Any]]:
        """Получение списка сущностей"""
        try:
            url = f'{self.base_url}/api/states'
            if domain:
                url += f'?domain={domain}'
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return []
        except Exception as e:
            print(f"[HA] Failed to get entities: {e}")
            return []


class DeviceDataPublisher:
    """Публикация данных устройств в Home Assistant"""
    
    def __init__(self):
        self.ha_client = None
        self.publish_tasks = {}
        self.entity_cache = {}
    
    async def initialize(self):
        """Инициализация клиента Home Assistant"""
        ha_config = config.get('home_assistant', {})
        if not ha_config.get('enabled', False):
            return False
        
        base_url = ha_config.get('base_url')
        token = ha_config.get('token')
        
        if not base_url or not token:
            print("[HA] Home Assistant configuration missing")
            return False
        
        self.ha_client = HomeAssistantClient(base_url, token)
        await self.ha_client.__aenter__()
        
        connected = await self.ha_client.test_connection()
        if connected:
            print("[HA] Connected to Home Assistant")
        else:
            print("[HA] Failed to connect to Home Assistant")
        
        return connected
    
    def _get_entity_id(self, device_id: int, port_code: str, prefix: str = 'my_home') -> str:
        """Генерация ID сущности"""
        return f"{prefix}.device_{device_id}_{port_code.replace('.', '_').replace('-', '_')}"
    
    def _get_entity_data(self, device: Devices, port_data: Dict[str, Any], prefix: str) -> Dict[str, Any]:
        """Создание данных сущности для Home Assistant"""
        entity_id = self._get_entity_id(device.id, port_data['code'], prefix)
        
        # Определяем тип сущности
        port_type = port_data.get('type', '')
        if 'analog' in port_type:
            if 'temp' in port_data.get('class', ''):
                domain = 'sensor'
                unit = port_data.get('unit', '°C')
            elif 'voltage' in port_data.get('unit_name', '').lower():
                domain = 'sensor'
                unit = port_data.get('unit', 'V')
            elif 'current' in port_data.get('unit_name', '').lower():
                domain = 'sensor'
                unit = port_data.get('unit', 'A')
            elif 'power' in port_data.get('unit_name', '').lower():
                domain = 'sensor'
                unit = port_data.get('unit', 'W')
            else:
                domain = 'sensor'
                unit = port_data.get('unit', '')
        elif 'didgi' in port_type:
            domain = 'switch' if port_type.startswith('out.') else 'binary_sensor'
            unit = None
        else:
            domain = 'sensor'
            unit = port_data.get('unit', '')
        
        attributes = {
            'friendly_name': port_data.get('title', port_data['code']),
            'device_class': self._get_device_class(port_data),
            'unit_of_measurement': unit,
            'device': {
                'identifiers': [f"my_home_device_{device.id}"],
                'name': device.name,
                'model': device.model,
                'manufacturer': device.vendor
            }
        }
        
        # Добавляем дополнительные атрибуты
        if port_data.get('min') is not None:
            attributes['min_value'] = port_data['min']
        if port_data.get('max') is not None:
            attributes['max_value'] = port_data['max']
        if port_data.get('mqtt'):
            attributes['mqtt_topic'] = port_data['mqtt']
        
        return {
            'entity_id': entity_id,
            'state': port_data.get('val', 'unknown'),
            'attributes': attributes
        }
    
    def _get_device_class(self, port_data: Dict[str, Any]) -> Optional[str]:
        """Определение класса устройства"""
        unit_name = port_data.get('unit_name', '').lower()
        port_class = port_data.get('class', '').lower()
        
        if 'temp' in port_class or 'temperature' in unit_name:
            return 'temperature'
        elif 'voltage' in unit_name:
            return 'voltage'
        elif 'current' in unit_name:
            return 'current'
        elif 'power' in unit_name:
            return 'power'
        elif 'energy' in unit_name:
            return 'energy'
        elif 'frequency' in unit_name:
            return 'frequency'
        
        return None
    
    def _should_publish_item(self, item: Dict[str, Any], publish_level: str, 
                           selected_ports: List[str] = None, selected_groups: List[str] = None) -> bool:
        """Определение, нужно ли публиковать элемент в зависимости от уровня публикации"""
        
        if publish_level == 'all':
            return True
        
        elif publish_level == 'groups':
            # Публикуем только выбранные группы
            if not selected_groups:
                return False
            
            group_title = item.get('title', '')
            return group_title in selected_groups
        
        elif publish_level == 'individual':
            # Для индивидуального уровня проверяем каждый порт отдельно
            # Этот метод вызывается для групп, а проверка отдельных портов происходит внутри
            return True
        
        return False
    
    async def publish_device_data(self, device_id: int, values: List[Dict[str, Any]], 
                                publish_level: str = 'all', selected_ports: List[str] = None, 
                                selected_groups: List[str] = None, prefix: str = 'my_home') -> Dict[str, Any]:
        """Публикация данных устройства в Home Assistant"""
        if not self.ha_client:
            return {'success': False, 'error': 'Home Assistant not connected'}
        
        with db_session() as db:
            device = db.query(Devices).filter(Devices.id == device_id).first()
            if not device:
                return {'success': False, 'error': 'Device not found'}
        
        published_entities = []
        failed_entities = []
        
        # Обрабатываем порты в зависимости от уровня публикации
        for item in values:
            if item.get('type') == 'file_list':
                continue
            
            # Проверяем уровень публикации
            should_publish = self._should_publish_item(item, publish_level, selected_ports, selected_groups)
            if not should_publish:
                continue
            
            # Обрабатываем простые порты
            if item.get('data') and isinstance(item['data'], list):
                # Группа портов
                group_published = 0
                for sub_item in item['data']:
                    if sub_item.get('type') and (sub_item['type'].startswith('in.') or sub_item['type'].startswith('out.')):
                        # Для уровня 'individual' проверяем каждый порт отдельно
                        if publish_level == 'individual':
                            if selected_ports and sub_item.get('code') not in selected_ports:
                                continue
                        
                        entity_data = self._get_entity_data(device, sub_item, prefix)
                        success = await self.ha_client.create_entity(entity_data)
                        
                        if success:
                            published_entities.append(entity_data['entity_id'])
                            group_published += 1
                        else:
                            failed_entities.append(sub_item['code'])
                
                print(f"[HA] Published {group_published} ports from group '{item.get('title', 'Unknown')}'")
            else:
                # Простой порт
                if item.get('type') and (item['type'].startswith('in.') or item['type'].startswith('out.')):
                    entity_data = self._get_entity_data(device, item, prefix)
                    success = await self.ha_client.create_entity(entity_data)
                    
                    if success:
                        published_entities.append(entity_data['entity_id'])
                    else:
                        failed_entities.append(item['code'])
        
        return {
            'success': True,
            'published_entities': published_entities,
            'failed_entities': failed_entities,
            'total_published': len(published_entities),
            'total_failed': len(failed_entities)
        }
    
    async def get_published_entities(self, device_id: int, prefix: str = 'my_home') -> List[Dict[str, Any]]:
        """Получение списка опубликованных сущностей для устройства"""
        if not self.ha_client:
            return []
        
        try:
            all_entities = await self.ha_client.get_entities()
            device_entities = []
            
            for entity in all_entities:
                entity_id = entity.get('entity_id', '')
                if entity_id.startswith(f'{prefix}.device_{device_id}_'):
                    device_entities.append({
                        'entity_id': entity_id,
                        'state': entity.get('state'),
                        'attributes': entity.get('attributes', {}),
                        'last_seen': entity.get('last_changed'),
                        'name': entity.get('attributes', {}).get('friendly_name', entity_id)
                    })
            
            return device_entities
        except Exception as e:
            print(f"[HA] Failed to get published entities: {e}")
            return []
    
    async def stop_publishing(self, device_id: int):
        """Остановка публикации данных для устройства"""
        if device_id in self.publish_tasks:
            task = self.publish_tasks[device_id]
            task.cancel()
            del self.publish_tasks[device_id]
    
    async def cleanup(self):
        """Очистка ресурсов"""
        if self.ha_client:
            await self.ha_client.__aexit__(None, None, None)


# Глобальный экземпляр публикатора
data_publisher = DeviceDataPublisher()
