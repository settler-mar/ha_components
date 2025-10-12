#!/bin/bash

# Скрипт для создания бэкапа только папки данных (без Docker контейнера)
# Предназначен для использования в Home Assistant

set -e

# Конфигурация
CURRENT_DIR=$(dirname "$(readlink -f "$0")")
BACKUP_ROOT="$CURRENT_DIR/backups"
DATA_DIR="$CURRENT_DIR/data"
DATA_SRC_DIR="$CURRENT_DIR/data_src"
TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"

# Создаем директорию для бэкапов если не существует
mkdir -p "$BACKUP_ROOT"

echo "🔄 Начало создания бэкапа данных: $TIMESTAMP"

# Проверяем существование папок данных
if [ ! -d "$DATA_DIR" ] && [ ! -d "$DATA_SRC_DIR" ]; then
    echo "❌ Ошибка: Папки данных не найдены!"
    echo "   Ожидаемые папки: $DATA_DIR, $DATA_SRC_DIR"
    exit 1
fi

# Создаем директорию бэкапа
mkdir -p "$BACKUP_DIR"

# Копируем папку data если существует
if [ -d "$DATA_DIR" ]; then
    echo "📁 Копирование папки data..."
    cp -r "$DATA_DIR" "$BACKUP_DIR/"
    echo "✅ Папка data скопирована"
else
    echo "⚠️  Папка data не найдена, пропускаем"
fi

# Копируем папку data_src если существует
if [ -d "$DATA_SRC_DIR" ]; then
    echo "📁 Копирование папки data_src..."
    cp -r "$DATA_SRC_DIR" "$BACKUP_DIR/"
    echo "✅ Папка data_src скопирована"
else
    echo "⚠️  Папка data_src не найдена, пропускаем"
fi

# Создаем файл с информацией о бэкапе
cat > "$BACKUP_DIR/backup_info.json" << EOF
{
    "timestamp": "$TIMESTAMP",
    "backup_type": "data_only",
    "description": "Backup of data folders only (no Docker container)",
    "data_folders": [
        $(if [ -d "$DATA_DIR" ]; then echo "\"data\""; fi)
        $(if [ -d "$DATA_DIR" ] && [ -d "$DATA_SRC_DIR" ]; then echo ","; fi)
        $(if [ -d "$DATA_SRC_DIR" ]; then echo "\"data_src\""; fi)
    ],
    "created_by": "backup_data_only.sh",
    "home_assistant_compatible": true
}
EOF

# Подсчитываем размер бэкапа
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo "📊 Размер бэкапа: $BACKUP_SIZE"

# Создаем символическую ссылку на последний бэкап
LATEST_LINK="$BACKUP_ROOT/latest"
rm -f "$LATEST_LINK"
ln -s "$TIMESTAMP" "$LATEST_LINK"

echo "✅ Бэкап данных создан успешно!"
echo "   📍 Путь: $BACKUP_DIR"
echo "   🔗 Ссылка: $LATEST_LINK"
echo "   📊 Размер: $BACKUP_SIZE"

# Опционально: удаляем старые бэкапы (старше 30 дней)
if [ "${CLEANUP_OLD_BACKUPS:-true}" = "true" ]; then
    echo "🧹 Очистка старых бэкапов..."
    find "$BACKUP_ROOT" -maxdepth 1 -type d -name "20*" -mtime +30 -exec rm -rf {} \; 2>/dev/null || true
    echo "✅ Старые бэкапы удалены"
fi

echo "🎉 Бэкап завершен: $(date)"


