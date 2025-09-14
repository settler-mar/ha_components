FROM ghcr.io/home-assistant/devcontainer:addons

RUN apt-get update && \
    apt-get install -y curl && \
    apt install -y --no-install-recommends python3-pip python3-venv

# Копируем файлы
COPY backend /backend
COPY data_src /data_src

WORKDIR /backend
# Установка зависимостей
RUN python -m pip install uvicorn pyyaml websockets --break-system-packages
RUN python -m pip install -r requirements.txt --break-system-packages

EXPOSE 3000

CMD ["uvicorn", "websrv:app", "--host", "0.0.0.0", "--port", "3000"]