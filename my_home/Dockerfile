FROM ghcr.io/home-assistant/devcontainer:addons

RUN apt-get update && \
    apt-get install -y curl && \
    apt install -y --no-install-recommends python3-pip python3-venv && \
    ln -s /usr/bin/python3 /usr/bin/python

# Копируем файлы
COPY backend /backend
COPY data_src /data_src
COPY frontend/dist /backend/dist

WORKDIR /backend
# Установка зависимостей
RUN ls -la && python3 -m pip install -r requirements.txt --break-system-packages

EXPOSE 3000

CMD ["uvicorn", "websrv:app", "--host", "0.0.0.0", "--port", "3000"]