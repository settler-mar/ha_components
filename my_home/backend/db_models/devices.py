from models.base_db_model import BaseModelDB
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey
from pydantic import BaseModel
from sqlalchemy import TypeDecorator, types
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.mutable import MutableDict
from db_models.common.json import Json
from sqlalchemy.ext.declarative import declared_attr


class Devices(BaseModelDB):
  __tablename__ = "devices"

  id = Column(Integer, primary_key=True, index=True, autoincrement=True)
  code = Column(String(100), unique=True, index=True, nullable=False)
  name = Column(String(100), unique=True, index=True, nullable=False)
  model = Column(String(100))
  vendor = Column(String(100))
  description = Column(String(255))
  type = Column(String(20))
  online = Column(Boolean, default=False)
  last_seen = Column(DateTime, nullable=True)
  params = Column(MutableDict.as_mutable(Json))

  def on_create(self):
    # Устройство уже добавлено в MyHomeClass при инициализации
    print("Device created:", self.id, self.name)

  def on_update(self):
    # Обновление устройства обрабатывается отдельно
    print("Device updated:", self.id, self.name)

  def on_delete(self):
    print("Device deleted:", self.id, self.name)
