FROM ghcr.io/home-assistant/devcontainer:addons

RUN apt-get update && \
    apt-get install -y curl && \
    apt install -y --no-install-recommends python3-pip python3-venv && \
    ln -s /usr/bin/python3 /usr/bin/python

# Рабочая директория проекта
WORKDIR /my_home

# Копируем backend при билде (как вложенную папку)
COPY backend /my_home/backend

# Копируем data_src для инициализации данных при первом запуске
COPY data_src /my_home/data_src

# Копируем startup script
COPY docker-entrypoint.sh /my_home/docker-entrypoint.sh
RUN chmod +x /my_home/docker-entrypoint.sh

# Установка базовых зависимостей при билде
WORKDIR /my_home/backend
RUN python3 -m pip install -r requirements.txt --break-system-packages

EXPOSE 3000

# Используем entrypoint script для копирования файлов при старте
ENTRYPOINT ["/my_home/docker-entrypoint.sh"]
CMD ["uvicorn", "websrv:app", "--host", "0.0.0.0", "--port", "3000"]
