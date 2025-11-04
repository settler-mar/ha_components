"""
Value Mapper для преобразования значений между Home Assistant и устройствами MyHome
Поддерживает двунаправленное преобразование:
- HA → Device (для команд от HA к устройству)
- Device → HA (для состояний от устройства к HA)
"""
from typing import Any, Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class ValueMapper:
  """Класс для преобразования значений между HA и устройствами"""

  def __init__(self):
    self.color_map = {
      'red': '#FF0000',
      'green': '#00FF00',
      'blue': '#0000FF',
      'white': '#FFFFFF',
      'black': '#000000',
      'yellow': '#FFFF00',
      'cyan': '#00FFFF',
      'magenta': '#FF00FF',
      'orange': '#FFA500',
      'purple': '#800080',
      'pink': '#FFC0CB',
      'brown': '#A52A2A',
      'gray': '#808080',
      'grey': '#808080'
    }

  def map_ha_to_device(self, port_code: str, ha_value: Any, port_info: Optional[Dict[str, Any]] = None) -> Any:
    """Преобразует значение из HA в формат устройства"""
    try:
      if not port_info:
        logger.warning(f"Port info not found for {port_code}, using default mapping")
        return self._default_ha_to_device_mapping(ha_value)

      port_type = port_info.get('kind', 'unknown')
      port_direction = port_info.get('direction', 'unknown')

      logger.debug(
        f"Mapping HA value {ha_value} to device for port {port_code} (type: {port_type}, direction: {port_direction})")

      # Маппинг в зависимости от типа порта
      if port_type in ['switch', 'button', 'relay']:
        return self._map_switch_ha_to_device(ha_value)
      elif port_type in ['sensor', 'analog', 'temperature', 'humidity', 'pressure']:
        return self._map_sensor_ha_to_device(ha_value)
      elif port_type in ['pwm', 'dimmer']:
        return self._map_pwm_ha_to_device(ha_value)
      elif port_type in ['color', 'rgb', 'rgbw']:
        return self._map_color_ha_to_device(ha_value)
      elif port_type in ['text', 'string']:
        return self._map_text_ha_to_device(ha_value)
      else:
        logger.warning(f"Unknown port type {port_type} for {port_code}, using default mapping")
        return self._default_ha_to_device_mapping(ha_value)

    except Exception as e:
      logger.error(f"Error mapping HA value to device: {e}")
      return self._default_ha_to_device_mapping(ha_value)

  def map_device_to_ha(self, port_code: str, device_value: Any, port_info: Optional[Dict[str, Any]] = None) -> Any:
    """Преобразует значение от устройства в формат HA"""
    try:
      if not port_info:
        logger.warning(f"Port info not found for {port_code}, using default mapping")
        return self._default_device_to_ha_mapping(device_value)

      port_type = port_info.get('kind', 'unknown')
      port_direction = port_info.get('direction', 'unknown')

      logger.debug(
        f"Mapping device value {device_value} to HA for port {port_code} (type: {port_type}, direction: {port_direction})")

      # Маппинг в зависимости от типа порта
      if port_type in ['switch', 'button', 'relay']:
        return self._map_switch_device_to_ha(device_value)
      elif port_type in ['sensor', 'analog', 'temperature', 'humidity', 'pressure']:
        return self._map_sensor_device_to_ha(device_value)
      elif port_type in ['pwm', 'dimmer']:
        return self._map_pwm_device_to_ha(device_value)
      elif port_type in ['color', 'rgb', 'rgbw']:
        return self._map_color_device_to_ha(device_value)
      elif port_type in ['text', 'string']:
        return self._map_text_device_to_ha(device_value)
      else:
        logger.warning(f"Unknown port type {port_type} for {port_code}, using default mapping")
        return self._default_device_to_ha_mapping(device_value)

    except Exception as e:
      logger.error(f"Error mapping device value to HA: {e}")
      return self._default_device_to_ha_mapping(device_value)

  # ========== HA → Device мапперы ==========

  def _map_switch_ha_to_device(self, ha_value: Any) -> int:
    """Маппинг переключателей HA → Device"""
    if isinstance(ha_value, bool):
      return 1 if ha_value else 0
    elif isinstance(ha_value, str):
      if ha_value.lower() in ['on', 'true', '1', 'yes']:
        return 1
      elif ha_value.lower() in ['off', 'false', '0', 'no']:
        return 0
    elif isinstance(ha_value, (int, float)):
      return 1 if ha_value else 0
    return 0

  def _map_sensor_ha_to_device(self, ha_value: Any) -> float:
    """Маппинг датчиков HA → Device"""
    if isinstance(ha_value, (int, float)):
      return float(ha_value)
    elif isinstance(ha_value, str):
      try:
        return float(ha_value)
      except ValueError:
        logger.warning(f"Cannot convert string '{ha_value}' to float for sensor")
        return 0.0
    return 0.0

  def _map_pwm_ha_to_device(self, ha_value: Any) -> int:
    """Маппинг PWM/диммеров HA → Device (0-255)"""
    if isinstance(ha_value, (int, float)):
      if ha_value > 1:
        if ha_value <= 100:
          # Процент от 0-100% → 0-255
          return int((ha_value / 100) * 255)
        elif ha_value <= 255:
          # Прямое значение 0-255
          return int(ha_value)
        else:
          # Больше 255, ограничиваем
          return 255
      else:
        # Значение 0-1 → 0-255
        return int(ha_value * 255)
    elif isinstance(ha_value, str):
      if ha_value.lower() in ['on', 'true', '1', 'yes']:
        return 255
      elif ha_value.lower() in ['off', 'false', '0', 'no']:
        return 0
      else:
        try:
          val = float(ha_value)
          return self._map_pwm_ha_to_device(val)
        except ValueError:
          return 0
    return 0

  def _map_color_ha_to_device(self, ha_value: Any) -> str:
    """Маппинг цветов HA → Device"""
    if isinstance(ha_value, str):
      if ha_value.startswith('#'):
        return ha_value
      elif ',' in ha_value:
        return ha_value
      else:
        return self._color_name_to_hex(ha_value)
    elif isinstance(ha_value, (list, tuple)) and len(ha_value) >= 3:
      if len(ha_value) == 3:
        return f"#{ha_value[0]:02x}{ha_value[1]:02x}{ha_value[2]:02x}"
      elif len(ha_value) == 4:
        return f"#{ha_value[0]:02x}{ha_value[1]:02x}{ha_value[2]:02x}{ha_value[3]:02x}"
    return "#000000"

  def _map_text_ha_to_device(self, ha_value: Any) -> str:
    """Маппинг текста HA → Device"""
    return str(ha_value) if ha_value is not None else ""

  def _default_ha_to_device_mapping(self, ha_value: Any) -> Any:
    """Маппинг по умолчанию HA → Device"""
    if isinstance(ha_value, bool):
      return 1 if ha_value else 0
    elif isinstance(ha_value, (int, float)):
      return ha_value
    elif isinstance(ha_value, str):
      return ha_value
    else:
      return str(ha_value)

  # ========== Device → HA мапперы ==========

  def _map_switch_device_to_ha(self, device_value: Any) -> str:
    """Маппинг переключателей Device → HA"""
    if isinstance(device_value, (int, float)):
      return "on" if device_value else "off"
    elif isinstance(device_value, str):
      if device_value.lower() in ['1', 'true', 'on', 'yes']:
        return "on"
      elif device_value.lower() in ['0', 'false', 'off', 'no']:
        return "off"
    elif isinstance(device_value, bool):
      return "on" if device_value else "off"
    return "off"

  def _map_sensor_device_to_ha(self, device_value: Any) -> float:
    """Маппинг датчиков Device → HA"""
    if isinstance(device_value, (int, float)):
      return float(device_value)
    elif isinstance(device_value, str):
      try:
        return float(device_value)
      except ValueError:
        logger.warning(f"Cannot convert device value '{device_value}' to float for sensor")
        return 0.0
    return 0.0

  def _map_pwm_device_to_ha(self, device_value: Any) -> int:
    """Маппинг PWM/диммеров Device → HA (0-255)"""
    if isinstance(device_value, (int, float)):
      # Устройство работает с 0-255, HA тоже может принимать 0-255
      return int(device_value)
    elif isinstance(device_value, str):
      try:
        return int(float(device_value))
      except ValueError:
        return 0
    return 0

  def _map_color_device_to_ha(self, device_value: Any) -> str:
    """Маппинг цветов Device → HA"""
    if isinstance(device_value, str):
      if device_value.startswith('#'):
        return device_value
      elif ',' in device_value:
        # RGB значения через запятую -> hex
        try:
          rgb = [int(x.strip()) for x in device_value.split(',')]
          if len(rgb) >= 3:
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        except ValueError:
          pass
    elif isinstance(device_value, (list, tuple)) and len(device_value) >= 3:
      if len(device_value) == 3:
        return f"#{device_value[0]:02x}{device_value[1]:02x}{device_value[2]:02x}"
      elif len(device_value) == 4:
        return f"#{device_value[0]:02x}{device_value[1]:02x}{device_value[2]:02x}{device_value[3]:02x}"
    return "#000000"

  def _map_text_device_to_ha(self, device_value: Any) -> str:
    """Маппинг текста Device → HA"""
    return str(device_value) if device_value is not None else ""

  def _default_device_to_ha_mapping(self, device_value: Any) -> str:
    """Маппинг по умолчанию Device → HA"""
    if isinstance(device_value, bool):
      return "on" if device_value else "off"
    elif isinstance(device_value, (int, float)):
      return str(device_value)
    elif isinstance(device_value, str):
      return device_value
    else:
      return str(device_value)

  # ========== Вспомогательные функции ==========

  def _color_name_to_hex(self, color_name: str) -> str:
    """Конвертирует название цвета в hex"""
    return self.color_map.get(color_name.lower(), '#000000')

  def get_supported_port_types(self) -> List[str]:
    """Возвращает список поддерживаемых типов портов"""
    return ['switch', 'button', 'relay', 'sensor', 'analog', 'temperature',
            'humidity', 'pressure', 'pwm', 'dimmer', 'color', 'rgb', 'rgbw',
            'text', 'string']

  def get_mapping_info(self, port_type: str) -> Dict[str, str]:
    """Возвращает информацию о маппинге для типа порта"""
    info = {
      'switch': 'HA: on/off → Device: 1/0',
      'button': 'HA: on/off → Device: 1/0',
      'relay': 'HA: on/off → Device: 1/0',
      'sensor': 'HA: number → Device: float',
      'analog': 'HA: number → Device: float',
      'temperature': 'HA: number → Device: float',
      'humidity': 'HA: number → Device: float',
      'pressure': 'HA: number → Device: float',
      'pwm': 'HA: 0-255 or 0-100% → Device: 0-255',
      'dimmer': 'HA: 0-255 or 0-100% → Device: 0-255',
      'color': 'HA: #RRGGBB or [R,G,B] → Device: #RRGGBB',
      'rgb': 'HA: #RRGGBB or [R,G,B] → Device: #RRGGBB',
      'rgbw': 'HA: #RRGGBB or [R,G,B] → Device: #RRGGBB',
      'text': 'HA: string → Device: string',
      'string': 'HA: string → Device: string'
    }
    return {port_type: info.get(port_type, 'Unknown mapping')}


# Глобальный экземпляр маппера
value_mapper = ValueMapper()
