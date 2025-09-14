import yaml
from typing import Any

from fastapi import FastAPI
import random
import string
import os
import json

default_config = {
  'db': {
    'url': 'sqlite:///../data/sql_app.db',
    'echo': False,
    'echo_pool': False,
    'check_same_thread': True
  },
  'gsheet': '',
  'local_networks': "192.168.0.1/24",
  'scan_timeout': 2,
  'is_fast_scan': True,
}


class AppConfig:
  _config: dict = {}
  _need_save: bool = False

  def __init__(self, config_path: str = None):
    config_dir = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data'))
    if not os.path.exists(config_dir):
      os.makedirs(config_dir)
    if config_path is None:
      config_path = os.path.join(config_dir, 'config.yaml')
    self._config_path = config_path
    self._config = self._load_yaml()
    self._config.update(self._load_json())
    self._test_config()
    if self._need_save:
      self.save_yaml()

  def _load_yaml(self) -> dict:
    try:
      with open(self._config_path, 'r') as file:
        return yaml.safe_load(file) or {}
    except FileNotFoundError:
      return {}

  def _load_json(self) -> dict:
    try:
      import json
      json_path = self._config_path.replace('.yaml', '.json')
      with open(json_path, 'r') as file:
        return json.load(file) or {}
    except (FileNotFoundError, json.JSONDecodeError):
      return {}

  def _test_config(self, root_config: dict = None, root_default: dict = None) -> None:
    root_config = root_config or self._config
    root_default = root_default or default_config
    for key, value in root_default.items():
      if key not in root_config:
        root_config[key] = value
        self._need_save = True
      elif isinstance(value, dict):
        self._test_config(root_config[key], value)

  def save_yaml(self) -> None:
    with open(self._config_path, 'w') as file:
      yaml.safe_dump(self._config, file)

  def __getitem__(self, key: str) -> Any:
    return self._config.get(key, None)

  def __setitem__(self, key: str, value: Any) -> None:
    raise AttributeError("Direct assignment is not allowed. Use set_value instead.")

  def set_value(self, path: list, value: Any, _config: dict) -> None:
    key = path[0]
    path = path[1:]
    if not path:
      _config[key] = value
    else:
      if key not in _config:
        _config[key] = {}
      if not isinstance(_config[key], dict):
        raise AttributeError(f"Path {key} is not a dictionary")
      self.set_value(path, value, _config[key])

  def __repr__(self) -> str:
    return f"AppConfig({self._config})"

  def create_routes(self, app: FastAPI):
    @app.get(f"/api/config", tags=["config"], response_model=dict)
    def get_config():
      return self._config

    @app.put(f"/api/config", tags=["config"])
    def set_config(path: str, value: Any):
      """
      Set config parameter.
      :param path: - path to parameter in config. Example: 'auth/algorithm'
      :param value:
      :return:
      """
      self.set_value([p for p in path.split('/') if p], value, self._config)
      self.save_yaml()
      return {'status': 'ok'}


config = AppConfig()
