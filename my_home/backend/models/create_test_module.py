"""
Скрипт для создания тестового модуля автоматизации
"""
import json
import os
import uuid
from utils.configs import get_data_dir
from utils.logger import api_logger as logger


def create_test_module():
    """Создает тестовый модуль автоматизации"""
    data_dir = get_data_dir()
    automation_file = os.path.join(data_dir, "automation.json")
    modules_dir = os.path.join(data_dir, "automation_modules")
    os.makedirs(modules_dir, exist_ok=True)
    
    # Загружаем существующие данные
    if os.path.exists(automation_file):
        with open(automation_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {"modules": [], "instances": []}
    
    # Проверяем, существует ли уже тестовый модуль
    test_module = next((m for m in data.get("modules", []) if m.get("name") == "Тестовый модуль"), None)
    if test_module:
        logger.info("Тестовый модуль уже существует")
        return test_module["id"]
    
    # Создаем тестовый модуль
    module_id = str(uuid.uuid4())
    
    # Создаем директорию для версий модуля
    versions_dir = os.path.join(modules_dir, module_id, "versions")
    os.makedirs(versions_dir, exist_ok=True)
    
    # Создаем тестовый файл версии
    version_file_content = '''"""
MODULE_METADATA:
name: "Тестовый модуль"
description: "Пример модуля автоматизации для тестирования"
icon: "mdi-test-tube"
color: "#4CAF50"
version: "1.0.0"
min_compatible_version: null
class_name: "AutomationModule"
input_ports:
  - name: "temperature"
    description: "Температура"
    required: true
  - name: "humidity"
    description: "Влажность"
    required: false
output_ports:
  - name: "heater_status"
    description: "Статус обогревателя"
    required: false
parameters:
  - name: "target_temperature"
    description: "Целевая температура"
    type: "float"
    default: 22.0
    allowed_sources: ["fixed", "ha", "myhome"]
  - name: "hysteresis"
    description: "Гистерезис"
    type: "float"
    default: 1.0
    allowed_sources: ["fixed", "ha"]
visual_components:
  - name: "Панель управления обогревателем"
    description: "Визуальный компонент для управления обогревателем на панели Home Assistant"
    parameters:
      type: "card"
      title: "Управление обогревателем"
      entity: "climate.heater"
      icon: "mdi-radiator"
"""

class AutomationModule:
    """Класс модуля автоматизации"""
    
    def process(self, input_ports, output_ports, parameters):
        """
        Основная функция обработки модуля
        
        Args:
            input_ports: Словарь входных портов
            output_ports: Словарь выходных портов
            parameters: Словарь параметров модуля
        
        Returns:
            Словарь с результатами обработки
        """
        # Получаем значения входных портов
        temperature = input_ports.get('temperature', 0)
        humidity = input_ports.get('humidity', 0)
        
        # Используем значение из входного порта
        current_temp = temperature
        
        # Получаем параметры
        target_temp = parameters.get('target_temperature', 22.0)
        hysteresis = parameters.get('hysteresis', 1.0)
        
        # Логика управления обогревателем
        heater_status = False
        if current_temp < (target_temp - hysteresis):
            heater_status = True
        elif current_temp > (target_temp + hysteresis):
            heater_status = False
        
        # Устанавливаем значение выходного порта
        output_ports['heater_status'] = heater_status
        
        # Возвращаем результаты
        return {
            'status': 'success',
            'temperature': current_temp,
            'humidity': humidity,
            'heater_status': heater_status,
            'target_temperature': target_temp
        }
    
    def validate(self, input_ports, output_ports, parameters):
        """
        Валидация входных данных
        
        Returns:
            tuple: (is_valid, error_message)
        """
        if 'temperature' not in input_ports:
            return False, "Требуется входной порт 'temperature'"
        
        if 'target_temperature' not in parameters:
            return False, "Требуется параметр 'target_temperature'"
        
        return True, None
'''
    
    version_filename = "1.0.0.py"
    version_file_path = os.path.join(versions_dir, version_filename)
    with open(version_file_path, 'w', encoding='utf-8') as f:
        f.write(version_file_content)
    
    module = {
        "id": module_id,
        "name": "Тестовый модуль",
        "description": "Пример модуля автоматизации для тестирования",
        "icon": "mdi-test-tube",
        "color": "#4CAF50",
        "file_path": None,  # Основной файл модуля не используется, только версии
        "versions": [
            {
                "version": "1.0.0",
                "min_compatible_version": None,
                "created_at": "2024-01-01T00:00:00",
                "file_path": version_filename,
                # Метаданные могут быть извлечены из файла позже
                "input_ports": [],
                "output_ports": [],
                "parameters": [],
                "visual_components": []
            }
        ],
        "current_version": "1.0.0"
    }
    
    
    # Добавляем модуль в данные
    data["modules"].append(module)
    
    # Сохраняем данные
    with open(automation_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Тестовый модуль создан: {module_id}")
    logger.info(f"Файл модуля: {version_file_path}")
    
    return module_id


if __name__ == "__main__":
    create_test_module()

