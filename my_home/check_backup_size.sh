#!/bin/bash

# Скрипт для проверки размера бэкапа и сравнения с Docker образом
# Помогает убедиться, что настройки бэкапа работают корректно

set -e

CURRENT_DIR=$(dirname "$(readlink -f "$0")")
DATA_DIR="$CURRENT_DIR/data"
DATA_SRC_DIR="$CURRENT_DIR/data_src"

echo "🔍 Проверка размера данных для бэкапа"
echo "=================================="

# Проверяем размер папки data
if [ -d "$DATA_DIR" ]; then
    DATA_SIZE=$(du -sh "$DATA_DIR" | cut -f1)
    DATA_SIZE_BYTES=$(du -sb "$DATA_DIR" | cut -f1)
    echo "📁 Папка data: $DATA_SIZE ($DATA_SIZE_BYTES байт)"
else
    echo "⚠️  Папка data не найдена"
    DATA_SIZE_BYTES=0
fi

# Проверяем размер папки data_src
if [ -d "$DATA_SRC_DIR" ]; then
    DATA_SRC_SIZE=$(du -sh "$DATA_SRC_DIR" | cut -f1)
    DATA_SRC_SIZE_BYTES=$(du -sb "$DATA_SRC_DIR" | cut -f1)
    echo "📁 Папка data_src: $DATA_SRC_SIZE ($DATA_SRC_SIZE_BYTES байт)"
else
    echo "⚠️  Папка data_src не найдена"
    DATA_SRC_SIZE_BYTES=0
fi

# Общий размер данных
TOTAL_DATA_SIZE_BYTES=$((DATA_SIZE_BYTES + DATA_SRC_SIZE_BYTES))
TOTAL_DATA_SIZE_MB=$((TOTAL_DATA_SIZE_BYTES / 1024 / 1024))

echo ""
echo "📊 Итоговый размер данных: $TOTAL_DATA_SIZE_MB МБ"

# Проверяем размер Docker образа
echo ""
echo "🐳 Проверка размера Docker образа"
echo "================================="

if command -v docker &> /dev/null; then
    # Ищем образы связанные с проектом
    DOCKER_IMAGES=$(docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | grep -E "(my_home|app_server|server)" || true)
    
    if [ -n "$DOCKER_IMAGES" ]; then
        echo "Найденные Docker образы:"
        echo "$DOCKER_IMAGES"
        
        # Извлекаем размеры образов
        DOCKER_SIZES=$(echo "$DOCKER_IMAGES" | tail -n +2 | awk '{print $3}' | sed 's/[^0-9.]//g')
        TOTAL_DOCKER_SIZE=0
        
        for size in $DOCKER_SIZES; do
            if [[ $size =~ ^[0-9]+\.?[0-9]*$ ]]; then
                TOTAL_DOCKER_SIZE=$(echo "$TOTAL_DOCKER_SIZE + $size" | bc -l 2>/dev/null || echo "$TOTAL_DOCKER_SIZE")
            fi
        done
        
        echo ""
        echo "📊 Общий размер Docker образов: ~${TOTAL_DOCKER_SIZE} МБ"
    else
        echo "⚠️  Docker образы проекта не найдены"
        TOTAL_DOCKER_SIZE=0
    fi
else
    echo "⚠️  Docker не установлен или недоступен"
    TOTAL_DOCKER_SIZE=0
fi

# Сравнение размеров
echo ""
echo "📈 Сравнение размеров"
echo "===================="
echo "Данные (только папки):     ~$TOTAL_DATA_SIZE_MB МБ"
echo "Docker образы:             ~${TOTAL_DOCKER_SIZE} МБ"
echo "Экономия при бэкапе:       ~${TOTAL_DOCKER_SIZE} МБ"

# Проверяем конфигурацию
echo ""
echo "⚙️  Проверка конфигурации бэкапа"
echo "==============================="

if [ -f "$CURRENT_DIR/config.yaml" ]; then
    if grep -q "map:" "$CURRENT_DIR/config.yaml"; then
        echo "✅ Параметр 'map' найден в config.yaml"
        echo "📋 Настроенные папки для бэкапа:"
        grep -A 10 "map:" "$CURRENT_DIR/config.yaml" | grep "^-" | sed 's/^/   /'
    else
        echo "❌ Параметр 'map' не найден в config.yaml"
        echo "   Добавьте следующие строки в config.yaml:"
        echo "   map:"
        echo "     - data"
        echo "     - data_src"
    fi
else
    echo "❌ Файл config.yaml не найден"
fi

# Рекомендации
echo ""
echo "💡 Рекомендации"
echo "==============="

if [ $TOTAL_DATA_SIZE_MB -lt 10 ]; then
    echo "✅ Размер данных оптимален для бэкапа (< 10 МБ)"
else
    echo "⚠️  Размер данных больше 10 МБ, проверьте содержимое папок"
fi

if [ $(echo "$TOTAL_DOCKER_SIZE > 100" | bc -l 2>/dev/null || echo "0") -eq 1 ]; then
    echo "✅ Исключение Docker образа даст значительную экономию места"
else
    echo "ℹ️  Размер Docker образа относительно небольшой"
fi

echo ""
echo "🎯 Ожидаемый размер бэкапа после настройки: ~$TOTAL_DATA_SIZE_MB МБ"
echo "   (вместо ~$((TOTAL_DATA_SIZE_MB + ${TOTAL_DOCKER_SIZE%.*})) МБ с Docker образом)"


