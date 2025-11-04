#!/bin/bash
set -e

# Путь к рабочей директории проекта
PROJECT_DIR="/my_home"
SOURCE_DIR="/addons/my_addons/my_home"
BACKEND_DIR="${PROJECT_DIR}/backend"

echo "=== Starting entrypoint script ==="

# Копируем dist из исходной директории (если существует)
if [ -d "${SOURCE_DIR}/dist" ]; then
    echo "Copying dist from ${SOURCE_DIR}/dist to ${PROJECT_DIR}/dist..."
    rm -rf "${PROJECT_DIR}/dist" 2>/dev/null || true
    cp -r "${SOURCE_DIR}/dist" "${PROJECT_DIR}/dist" 2>/dev/null || true
    echo "Dist copied successfully"
else
    echo "Warning: ${SOURCE_DIR}/dist not found, skipping dist copy"
fi

# Копируем backend из исходной директории (если существует)
# Обновляем только исходные файлы, сохраняя __pycache__, установленные пакеты и .venv
if [ -d "${SOURCE_DIR}/backend" ]; then
    echo "Updating backend from ${SOURCE_DIR}/backend to ${BACKEND_DIR}..."
    # Используем rsync для синхронизации, исключая кэш, виртуальные окружения и установленные пакеты
    if command -v rsync &> /dev/null; then
        rsync -av \
            --exclude='__pycache__' \
            --exclude='*.pyc' \
            --exclude='.venv' \
            --exclude='venv' \
            --exclude='env' \
            --exclude='.env' \
            --exclude='*.egg-info' \
            --exclude='.requirements.txt.hash' \
            "${SOURCE_DIR}/backend/" "${BACKEND_DIR}/" || true
    else
        # Fallback на cp если rsync недоступен
        find "${SOURCE_DIR}/backend" -type f \
            -not -path "*/__pycache__/*" \
            -not -name "*.pyc" \
            -not -path "*/.venv/*" \
            -not -path "*/venv/*" \
            -not -path "*/env/*" \
            -not -path "*/.env/*" \
            -not -name "*.egg-info" \
            -not -name ".requirements.txt.hash" | while read file; do
            rel_path="${file#${SOURCE_DIR}/backend/}"
            dest_path="${BACKEND_DIR}/${rel_path}"
            mkdir -p "$(dirname "$dest_path")"
            cp "$file" "$dest_path" 2>/dev/null || true
        done
    fi
    echo "Backend updated successfully"
else
    echo "Warning: ${SOURCE_DIR}/backend not found, skipping backend update"
fi

# Инициализация data_src: копируем файлы из data_src в /data при первом запуске
DATA_SRC_DIR="${PROJECT_DIR}/data_src"
DATA_DIR="/data"

if [ -d "${DATA_SRC_DIR}" ]; then
    echo "Checking data initialization..."
    
    # Проверяем наличие файлов в data_src
    if [ "$(ls -A ${DATA_SRC_DIR} 2>/dev/null)" ]; then
        echo "Found data_src directory with files"
        
        # Для каждого файла/директории в data_src проверяем наличие в /data
        for item in "${DATA_SRC_DIR}"/*; do
            if [ -e "$item" ]; then
                item_name=$(basename "$item")
                dest_path="${DATA_DIR}/${item_name}"
                
                # Проверяем, существует ли файл в /data
                if [ ! -e "$dest_path" ]; then
                    echo "Copying ${item_name} to ${DATA_DIR}..."
                    
                    # Создаем директорию /data если её нет
                    mkdir -p "${DATA_DIR}"
                    
                    # Копируем файл или директорию
                    if [ -d "$item" ]; then
                        cp -r "$item" "$dest_path" 2>/dev/null || true
                        echo "  Directory ${item_name} copied successfully"
                    else
                        cp "$item" "$dest_path" 2>/dev/null || true
                        echo "  File ${item_name} copied successfully"
                    fi
                else
                    echo "  ${item_name} already exists in ${DATA_DIR}, skipping"
                fi
            fi
        done
        echo "Data initialization completed"
    else
        echo "data_src directory is empty, skipping initialization"
    fi
else
    echo "Warning: data_src directory not found at ${DATA_SRC_DIR}, skipping data initialization"
fi

echo "=== Entrypoint script completed ==="

# Выполняем переданную команду
exec "$@"

