import json
from sqlalchemy import TypeDecorator, types

class Json(TypeDecorator):
  @property
  def python_type(self):
    return object

  impl = types.Text

  def process_bind_param(self, value, dialect):
    if value is None:
      return None
    return json.dumps(value)

  def process_literal_param(self, value, dialect):
    return value

  def process_result_value(self, value, dialect):
    try:
      if value is None or value == '':
        return {}
      result = json.loads(value)
      # Если результат не словарь, возвращаем пустой словарь
      if not isinstance(result, dict):
        print(f"[Json] Warning: json.loads returned {type(result)} instead of dict, value was: {value}")
        return {}
      return result
    except (TypeError, ValueError) as e:
      print(f"[Json] Error parsing JSON: {e}, value was: {value}")
      return {}