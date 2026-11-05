"""
API endpoints for energy management
"""
import json
import os
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from utils.logger import api_logger as logger
from utils.configs import get_data_dir


class EnergySourcePort(BaseModel):
    """Порт для источника энергии"""
    entity_id: str
    sign: str = "+"  # + или -
    filter_positive: bool = False  # Только положительные значения
    filter_negative: bool = False  # Только отрицательные значения
    purpose: Optional[str] = None  # Для осмоса: вход, отход, чистая


class EnergyWaterParams(BaseModel):
    """Параметры для воды (один порт для каждого параметра)"""
    temperature_entity_id: Optional[str] = None  # Температура
    pressure_entity_id: Optional[str] = None  # Давление
    hardness_entity_id: Optional[str] = None  # Жесткость
    ph_entity_id: Optional[str] = None  # Ph


class EnergyOsmosisParams(BaseModel):
    """Параметры для осмоса (3 порта для каждого параметра: вход, отход, чистая)"""
    temperature_input: Optional[str] = None  # Температура - вход
    temperature_waste: Optional[str] = None  # Температура - отход
    temperature_clean: Optional[str] = None  # Температура - чистая
    pressure_input: Optional[str] = None  # Давление - вход
    pressure_waste: Optional[str] = None  # Давление - отход
    pressure_clean: Optional[str] = None  # Давление - чистая
    hardness_input: Optional[str] = None  # Жесткость - вход
    hardness_waste: Optional[str] = None  # Жесткость - отход
    hardness_clean: Optional[str] = None  # Жесткость - чистая
    ph_input: Optional[str] = None  # Ph - вход
    ph_waste: Optional[str] = None  # Ph - отход
    ph_clean: Optional[str] = None  # Ph - чистая


class EnergyOnlinePort(BaseModel):
    """Порт для проверки онлайн статуса"""
    entity_id: str
    logic: str = "and"  # and или or


class EnergySource(BaseModel):
    """Источник энергии"""
    id: Optional[str] = None
    name: str
    group: str  # electric, gas, heat, water, reverse_osmosis
    active: bool = True
    priority: int = 0
    output_power: float = 0.0  # Выдаваемая мощность
    
    # Параметры для электричества
    power_ports: List[EnergySourcePort] = []  # Мощность (несколько портов)
    voltage_entity_id: Optional[str] = None  # Entity для напряжения
    frequency_entity_id: Optional[str] = None  # Entity для частоты
    online_ports: List[EnergyOnlinePort] = []  # Онлайн (несколько портов с логикой)
    counter_ports: List[EnergySourcePort] = []  # Счетчик (несколько портов, аналогично мощности)
    color: Optional[str] = None  # Цвет для электричества
    
    # Параметры для воды, осмоса, газа (расходы)
    consumption_ports: List[EnergySourcePort] = []  # Расходы (несколько портов, аналогично мощности)
    
    # Параметры для воды (один порт для каждого параметра)
    water_params: Optional[EnergyWaterParams] = None
    
    # Параметры для осмоса (3 порта для каждого параметра: вход, отход, чистая)
    osmosis_params: Optional[EnergyOsmosisParams] = None
    
    # Параметры для других групп
    other_color: Optional[str] = None  # Цвет для других групп (не электричество)


class EnergyOutput(BaseModel):
    """Настройки выхода энергии"""
    calculation_mode: str = "sum"  # sum, max, min
    priority_logic: str = "priority"  # priority, power
    selected_source_id: Optional[str] = None


def get_energy_data_file() -> str:
    """Получает путь к файлу с данными энергии"""
    data_dir = get_data_dir()
    energy_file = os.path.join(data_dir, "energy.json")
    return energy_file


def load_energy_data() -> Dict[str, Any]:
    """Загружает данные энергии из файла"""
    energy_file = get_energy_data_file()
    if os.path.exists(energy_file):
        try:
            with open(energy_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.error(f"Error loading energy data: {e}")
            return {"sources": [], "output": {"calculation_mode": "sum", "priority_logic": "priority"}}
    return {"sources": [], "output": {"calculation_mode": "sum", "priority_logic": "priority"}}


def save_energy_data(data: Dict[str, Any]):
    """Сохраняет данные энергии в файл"""
    energy_file = get_energy_data_file()
    try:
        os.makedirs(os.path.dirname(energy_file), exist_ok=True)
        with open(energy_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Energy data saved to {energy_file}")
    except Exception as e:
        logger.error(f"Error saving energy data: {e}")
        raise


def add_energy_routes(app: APIRouter):
    """Добавление маршрутов для управления энергией"""
    
    @app.get("/api/energy/sources", tags=["energy"])
    async def get_energy_sources():
        """Получение всех источников энергии"""
        try:
            data = load_energy_data()
            return {
                "success": True,
                "sources": data.get("sources", [])
            }
        except Exception as e:
            logger.error(f"Error getting energy sources: {e}")
            return {
                "success": False,
                "error": str(e),
                "sources": []
            }
    
    @app.get("/api/energy/sources/{source_id}", tags=["energy"])
    async def get_energy_source(source_id: str):
        """Получение конкретного источника энергии"""
        try:
            data = load_energy_data()
            sources = data.get("sources", [])
            source = next((s for s in sources if s.get("id") == source_id), None)
            
            if not source:
                raise HTTPException(status_code=404, detail="Source not found")
            
            return {
                "success": True,
                "source": source
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting energy source: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/energy/sources", tags=["energy"])
    async def create_energy_source(source: EnergySource):
        """Создание нового источника энергии"""
        try:
            data = load_energy_data()
            sources = data.get("sources", [])
            
            # Генерируем ID если не указан
            import uuid
            if not source.id:
                source.id = str(uuid.uuid4())
            
            # Проверяем уникальность ID
            if any(s.get("id") == source.id for s in sources):
                raise HTTPException(status_code=400, detail="Source with this ID already exists")
            
            # Добавляем источник
            source_dict = source.dict()
            sources.append(source_dict)
            data["sources"] = sources
            
            save_energy_data(data)
            
            return {
                "success": True,
                "source": source_dict
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating energy source: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put("/api/energy/sources/{source_id}", tags=["energy"])
    async def update_energy_source(source_id: str, source: EnergySource):
        """Обновление источника энергии"""
        try:
            data = load_energy_data()
            sources = data.get("sources", [])
            
            # Находим источник
            index = next((i for i, s in enumerate(sources) if s.get("id") == source_id), None)
            if index is None:
                raise HTTPException(status_code=404, detail="Source not found")
            
            # Обновляем источник
            source_dict = source.dict()
            source_dict["id"] = source_id  # Убеждаемся что ID не изменен
            sources[index] = source_dict
            data["sources"] = sources
            
            save_energy_data(data)
            
            return {
                "success": True,
                "source": source_dict
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating energy source: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.delete("/api/energy/sources/{source_id}", tags=["energy"])
    async def delete_energy_source(source_id: str):
        """Удаление источника энергии"""
        try:
            data = load_energy_data()
            sources = data.get("sources", [])
            
            # Находим и удаляем источник
            sources = [s for s in sources if s.get("id") != source_id]
            
            if len(sources) == len(data.get("sources", [])):
                raise HTTPException(status_code=404, detail="Source not found")
            
            data["sources"] = sources
            save_energy_data(data)
            
            return {
                "success": True,
                "message": "Source deleted"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting energy source: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/energy/output", tags=["energy"])
    async def get_energy_output():
        """Получение настроек выхода энергии"""
        try:
            data = load_energy_data()
            return {
                "success": True,
                "output": data.get("output", {
                    "calculation_mode": "sum",
                    "priority_logic": "priority"
                })
            }
        except Exception as e:
            logger.error(f"Error getting energy output: {e}")
            return {
                "success": False,
                "error": str(e),
                "output": {
                    "calculation_mode": "sum",
                    "priority_logic": "priority"
                }
            }
    
    @app.put("/api/energy/output", tags=["energy"])
    async def update_energy_output(output: EnergyOutput):
        """Обновление настроек выхода энергии"""
        try:
            data = load_energy_data()
            data["output"] = output.dict()
            save_energy_data(data)
            
            return {
                "success": True,
                "output": output.dict()
            }
        except Exception as e:
            logger.error(f"Error updating energy output: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/energy/groups", tags=["energy"])
    async def get_energy_groups():
        """Получение списка доступных групп энергии"""
        groups = [
            {
                "id": "electric",
                "name": "Электричество",
                "icon": "mdi-lightning-bolt",
                "default_color": "#FFC107",
                "parameters": [
                    "power_ports",  # Таблица внизу
                    "voltage_entity_id",
                    "frequency_entity_id",
                    "online_ports",  # Таблица внизу
                    "counter_ports"  # Таблица внизу
                ]
            },
            {
                "id": "gas",
                "name": "Газ",
                "icon": "mdi-gas-station",
                "default_color": "#FF5722",
                "parameters": [
                    "consumption_ports"  # Таблица внизу
                ]
            },
            {
                "id": "heat",
                "name": "Тепло",
                "icon": "mdi-radiator",
                "default_color": "#F44336",
                "parameters": []
            },
            {
                "id": "water",
                "name": "Вода",
                "icon": "mdi-water",
                "default_color": "#2196F3",
                "parameters": [
                    "consumption_ports"  # Таблица внизу
                ]
            },
            {
                "id": "reverse_osmosis",
                "name": "Осмос",
                "icon": "mdi-water-opacity",
                "default_color": "#00BCD4",
                "parameters": [
                    "consumption_ports"  # Таблица внизу
                ]
            }
        ]
        
        return {
            "success": True,
            "groups": groups
        }

