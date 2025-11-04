#!/bin/bash

# Скрипт для развертывания проекта в Home Assistant
# Использование: ./deploy.sh [путь_к_ha_addons]

set -e  # Выход при ошибке

# Путь к файлу с сохраненными учетными данными
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/deploy.conf"

# Определяем корневую директорию проекта (там где находится my_home)
PROJECT_ROOT="$SCRIPT_DIR"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
log() {
    echo "[INFO] $1"
}

success() {
    echo "[SUCCESS] $1"
}

warning() {
    echo "[WARNING] $1"
}

error() {
    echo "[ERROR] $1"
}

# Загрузка nvm если он не загружен
load_nvm() {
    if ! type nvm &> /dev/null; then
        log "Попытка загрузить nvm..."
        
        # Попробуем найти nvm в стандартных местах
        local nvm_paths=(
            "$HOME/.nvm/nvm.sh"
            "/usr/local/opt/nvm/nvm.sh"
            "/opt/homebrew/opt/nvm/nvm.sh"
        )
        
        for nvm_path in "${nvm_paths[@]}"; do
            if [ -f "$nvm_path" ]; then
                log "Найден nvm в: $nvm_path"
                source "$nvm_path"
                break
            fi
        done
        
        # Проверяем еще раз после загрузки
        if ! type nvm &> /dev/null; then
            error "nvm не найден. Установите Node Version Manager"
            error "Или убедитесь, что nvm загружен в текущей сессии"
            exit 1
        fi
    fi
}

# Проверка структуры проекта
check_project_structure() {
    log "Проверка структуры проекта..."
    
    # Переходим в корневую директорию проекта
    cd "$PROJECT_ROOT"
    
    # Проверяем, что мы в правильной папке
    if [ ! -d "my_home" ]; then
        error "Папка my_home не найдена в текущей директории"
        error "Убедитесь, что вы запускаете скрипт из папки home_assiastent_addons"
        exit 1
    fi
    
    local required_dirs=("my_home/frontend" "my_home/backend")
    local missing_dirs=()
    
    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            missing_dirs+=("$dir")
        fi
    done
    
    if [ ${#missing_dirs[@]} -gt 0 ]; then
        error "Отсутствуют необходимые папки: ${missing_dirs[*]}"
        error "Структура проекта должна содержать:"
        error "  - my_home/frontend/ (папка с Vue.js приложением)"
        error "  - my_home/backend/ (папка с Python бэкендом)"
        exit 1
    fi
    
    success "Структура проекта корректна"
}

# Проверка наличия необходимых команд
check_requirements() {
    log "Проверка требований..."
    
    # Загрузка nvm
    load_nvm
    
    if ! command -v yarn &> /dev/null; then
        error "yarn не найден. Установите Yarn"
        exit 1
    fi
    
    if ! command -v scp &> /dev/null; then
        error "scp не найден. Установите OpenSSH"
        exit 1
    fi
    
    # Проверяем наличие sshpass (предупреждение, но не блокируем, если есть SSH ключи)
    if ! command -v sshpass &> /dev/null; then
        warning "sshpass не найден. Если используете пароль из конфига, установите sshpass"
        warning "Для установки: sudo apt-get install sshpass (или sudo yum install sshpass)"
    fi
    
    success "Все требования выполнены"
}

# Загрузка сохраненных учетных данных
load_credentials() {
    if [ -f "$CONFIG_FILE" ]; then
        log "Загрузка сохраненных учетных данных из $CONFIG_FILE" >&2
        # Загружаем переменные из файла
        source "$CONFIG_FILE"
    fi
    
    # Удаляем кавычки из переменных (если они есть)
    # Функция для удаления кавычек с начала и конца строки
    strip_quotes() {
        local var="$1"
        var="${var#\"}"  # Удаляем открывающую кавычку
        var="${var%\"}"  # Удаляем закрывающую кавычку
        var="${var#\'}"  # Удаляем открывающий апостроф
        var="${var%\'}"  # Удаляем закрывающий апостроф
        echo "$var"
    }
    
    # Экспортируем переменные, удаляя кавычки
    export DEPLOY_HOST="$(strip_quotes "${DEPLOY_HOST:-}")"
    export DEPLOY_USER="$(strip_quotes "${DEPLOY_USER:-}")"
    export DEPLOY_PASSWORD="$(strip_quotes "${DEPLOY_PASSWORD:-}")"
    export DEPLOY_REMOTE_PATH="$(strip_quotes "${DEPLOY_REMOTE_PATH:-}")"
}

# Сохранение учетных данных
save_credentials() {
    local host="$1"
    local user="$2"
    local password="$3"
    local remote_path="$4"
    
    log "Сохранение учетных данных в $CONFIG_FILE" >&2
    
    # Создаем файл с правами только для чтения владельцем
    cat > "$CONFIG_FILE" <<EOF
# Конфигурация деплоя (создано автоматически)
# ВНИМАНИЕ: Файл содержит пароль в открытом виде!
DEPLOY_HOST="$host"
DEPLOY_USER="$user"
DEPLOY_PASSWORD="$password"
DEPLOY_REMOTE_PATH="$remote_path"
EOF
    
    # Устанавливаем права доступа (только для владельца)
    chmod 600 "$CONFIG_FILE"
    
    success "Учетные данные сохранены" >&2
}

# Получение учетных данных от пользователя (только если конфиг не существует)
get_credentials() {
    # Загружаем сохраненные данные как дефолт
    load_credentials >&2
    
    # Если конфиг уже существует и есть все данные, не запрашиваем повторно
    if [ -f "$CONFIG_FILE" ] && [ -n "$DEPLOY_HOST" ] && [ -n "$DEPLOY_USER" ] && [ -n "$DEPLOY_PASSWORD" ] && [ -n "$DEPLOY_REMOTE_PATH" ]; then
        log "Используются сохраненные учетные данные из $CONFIG_FILE" >&2
        return 0
    fi
    
    # Запрашиваем хост
    echo -n "Введите хост сервера [${DEPLOY_HOST:-192.168.0.78}]: " >&2
    read host_input </dev/tty
    local host="${host_input:-${DEPLOY_HOST:-192.168.0.78}}"
    
    # Запрашиваем пользователя
    echo -n "Введите имя пользователя [${DEPLOY_USER:-root}]: " >&2
    read user_input </dev/tty
    local user="${user_input:-${DEPLOY_USER:-root}}"
    
    # Запрашиваем пароль только если его нет в конфиге
    local password=""
    if [ -z "$DEPLOY_PASSWORD" ]; then
        echo "" >&2
        echo -n "Введите пароль: " >&2
        read -s password </dev/tty
        echo "" >&2
        log "Пароль введен" >&2
        
        # Проверяем, что пароль не пустой
        if [ -z "$password" ]; then
            error "Пароль не может быть пустым" >&2
            exit 1
        fi
    else
        # Используем пароль из конфига
        password="$DEPLOY_PASSWORD"
        log "Используется пароль из конфига" >&2
    fi
    
    # Запрашиваем удаленный путь
    echo -n "Введите удаленный путь [${DEPLOY_REMOTE_PATH:-/var/lib/homeassistant/addons/local/my_addons/my_home}]: " >&2
    read path_input </dev/tty
    local remote_path="${path_input:-${DEPLOY_REMOTE_PATH:-/var/lib/homeassistant/addons/local/my_addons/my_home}}"
    
    # Сохраняем учетные данные
    save_credentials "$host" "$user" "$password" "$remote_path" >&2
    
    # Экспортируем для использования
    export DEPLOY_HOST="$host"
    export DEPLOY_USER="$user"
    export DEPLOY_PASSWORD="$password"
    export DEPLOY_REMOTE_PATH="$remote_path"
    
    # Убираем кавычки при логировании (если они были в дефолтных значениях)
    local log_host="${host#\"}"
    log_host="${log_host%\"}"
    log_host="${log_host#\'}"
    log_host="${log_host%\'}"
    local log_user="${user#\"}"
    log_user="${log_user%\"}"
    log_user="${log_user#\'}"
    log_user="${log_user%\'}"
    local log_path="${remote_path#\"}"
    log_path="${log_path%\"}"
    log_path="${log_path#\'}"
    log_path="${log_path%\'}"
    
    log "Хост: $log_host" >&2
    log "Пользователь: $log_user" >&2
    log "Удаленный путь: $log_path" >&2
}

# Получение пути к HA addons
get_ha_path() {
    # Если путь передан как аргумент, используем его
    if [ -n "$1" ]; then
        echo "$1"
        return
    fi
    
    # Загружаем сохраненные данные (без вывода в stdout)
    load_credentials >&2
    
    # Если есть сохраненные данные, используем их (без запроса подтверждения)
    if [ -n "$DEPLOY_HOST" ] && [ -n "$DEPLOY_USER" ] && [ -n "$DEPLOY_REMOTE_PATH" ]; then
        log "Используются сохраненные учетные данные" >&2
        # Убираем кавычки при логировании
        local log_host="${DEPLOY_HOST#\"}"
        log_host="${log_host%\"}"
        log_host="${log_host#\'}"
        log_host="${log_host%\'}"
        local log_user="${DEPLOY_USER#\"}"
        log_user="${log_user%\"}"
        log_user="${log_user#\'}"
        log_user="${log_user%\'}"
        local log_path="${DEPLOY_REMOTE_PATH#\"}"
        log_path="${log_path%\"}"
        log_path="${log_path#\'}"
        log_path="${log_path%\'}"
        log "Хост: $log_host" >&2
        log "Пользователь: $log_user" >&2
        log "Удаленный путь: $log_path" >&2
        
        # Выводим только результат в stdout
        echo "scp://${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_REMOTE_PATH}"
        return
    fi
    
    # Если данных нет - запрашиваем их один раз (при создании конфига)
    get_credentials >&2
    
    # Выводим только результат в stdout
    echo "scp://${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_REMOTE_PATH}"
}

# Сборка frontend
build_frontend() {
    log "Начинаем сборку frontend..."
    
    # Проверяем существование папки frontend
    if [ ! -d "my_home/frontend" ]; then
        error "Папка my_home/frontend не найдена"
        exit 1
    fi
    
    # Убеждаемся, что nvm загружен
    load_nvm
    
    cd my_home/frontend
    
    # Переключение на Node.js 21
    log "Переключение на Node.js 21..."
    nvm use 21
    
    # Проверяем, что переключение прошло успешно
    local current_node=$(node --version 2>/dev/null || echo "не установлен")
    log "Текущая версия Node.js: $current_node"
    
    # Установка зависимостей (если нужно)
    if [ ! -d "node_modules" ]; then
        log "Установка зависимостей..."
        yarn install
    fi
    
    # Сборка проекта
    log "Сборка проекта..."
    yarn run build
    
    if [ $? -eq 0 ]; then
        success "Frontend собран успешно"
    else
        error "Ошибка при сборке frontend"
        exit 1
    fi
    
    cd ..
}

# Создание временной папки для развертывания
create_temp_dir() {
    local temp_dir=$(mktemp -d)
    log "Создана временная папка: $temp_dir" >&2
    echo "$temp_dir"
    mkdir -p "$temp_dir"
}

# Копирование файлов в временную папку
copy_files() {
    local temp_dir="$1"
    
    log "Копирование файлов в временную папку..."
    
    # Убеждаемся, что мы в корневой директории проекта
    cd "$PROJECT_ROOT"
    
    # Создание структуры папок
    mkdir -p "$temp_dir/data_src"
    mkdir -p "$temp_dir/backend"
    mkdir -p "$temp_dir/dist"
    
    # Копирование data_src
    log "Копирование data_src..."
    if [ -d "$PROJECT_ROOT/my_home/data_src" ]; then
        cp -r "$PROJECT_ROOT/my_home/data_src/"* "$temp_dir/data_src/" 2>/dev/null || warning "Папка data_src пуста"
    else
        warning "Папка my_home/data_src не найдена"
    fi
    
    # Копирование backend (исключая системные папки и архивы)
    log "Копирование backend..."
    rsync -av --exclude='__pycache__' \
              --exclude='*.pyc' \
              --exclude='*.pyo' \
              --exclude='.pytest_cache' \
              --exclude='.coverage' \
              --exclude='.mypy_cache' \
              --exclude='.DS_Store' \
              --exclude='Thumbs.db' \
              --exclude='*.log' \
              --exclude='*.tmp' \
              --exclude='tmp' \
              --exclude='temp' \
              --exclude='.env' \
              --exclude='venv' \
              --exclude='.venv' \
              --exclude='node_modules' \
              --exclude='backend*.zip' \
              --exclude='*.zip' \
              --exclude='*.tar.gz' \
              --exclude='*.tar' \
              --exclude='*.tgz' \
              --exclude='dist' \
              "$PROJECT_ROOT/my_home/backend/" "$temp_dir/backend/"
    
    # Копирование собранного frontend в /dist (на верхний уровень)
    log "Копирование собранного frontend в /dist..."
    if [ -d "$PROJECT_ROOT/my_home/frontend/dist" ]; then
        cp -r "$PROJECT_ROOT/my_home/frontend/dist/"* "$temp_dir/dist/"
        success "Frontend скопирован в /dist"
    else
        error "Папка my_home/frontend/dist не найдена. Сначала выполните сборку"
        exit 1
    fi
    
    # Копирование дополнительных файлов проекта
    log "Копирование дополнительных файлов..."
    for file in "docker-compose.yml" "Dockerfile" "README.md" "config.yaml" "makefile"; do
        if [ -f "$PROJECT_ROOT/my_home/$file" ]; then
            cp "$PROJECT_ROOT/my_home/$file" "$temp_dir/"
            log "Скопирован $file"
        fi
    done
    
    success "Все файлы скопированы в временную папку"
}

# Загрузка файлов на удаленный сервер
upload_files() {
    local temp_dir="$1"
    local ha_path="$2"
    
    log "Загрузка файлов на удаленный сервер..."
    
    # Определение протокола и пути
    if [[ "$ha_path" == scp://* ]]; then
        # Загружаем учетные данные из переменных окружения (уже без кавычек)
        load_credentials >&2
        
        # Извлечение хоста и пути из SCP URL (для проверки, но используем переменные)
        local scp_path=$(echo "$ha_path" | sed 's|scp://||')
        local user_host=$(echo "$scp_path" | cut -d':' -f1)
        if [[ "$user_host" == *"@"* ]]; then
            # get host from user_host
            local host=$(echo "$user_host" | cut -d'@' -f2)
        else
            local host="${DEPLOY_HOST}"
        fi
        
        local remote_path="${DEPLOY_REMOTE_PATH}"
        local user="${DEPLOY_USER}"
        local password="${DEPLOY_PASSWORD}"
        
        # Удаляем кавычки если они есть
        user="${user#\"}"
        user="${user%\"}"
        user="${user#\'}"
        user="${user%\'}"
        password="${password#\"}"
        password="${password%\"}"
        password="${password#\'}"
        password="${password%\'}"
        remote_path="${remote_path#\"}"
        remote_path="${remote_path%\"}"
        remote_path="${remote_path#\'}"
        remote_path="${remote_path%\'}"
        
        log "SCP хост: $host"
        log "Пользователь: $user"
        log "Удаленный путь: $remote_path"
        
        # Создание директории на удаленном сервере
        log "Создание директории на удаленном сервере..."
        
        # Определяем метод авторизации
        # Приоритет: sshpass с паролем из конфига > SSH ключи (без пароля) > ошибка
        local use_sshpass=false
        
        # Проверяем наличие sshpass и пароля из конфига
        if [ -n "$password" ]; then
            if command -v sshpass &> /dev/null 2>&1; then
                use_sshpass=true
                log "Используется sshpass для авторизации по паролю из конфига"
            else
                error "Пароль указан в конфиге, но sshpass не установлен."
                error "Установите sshpass одним из способов:"
                error "  Ubuntu/Debian: sudo apt-get install sshpass"
                error "  CentOS/RHEL: sudo yum install sshpass"
                error "  Arch: sudo pacman -S sshpass"
                error "Или настройте SSH ключи и удалите пароль из конфига."
                exit 1
            fi
        # Если пароля нет, проверяем наличие SSH ключей
        elif [ -n "$SSH_AUTH_SOCK" ] || [ -f "$HOME/.ssh/id_rsa" ] || [ -f "$HOME/.ssh/id_ed25519" ]; then
            log "Используется SSH ключ для авторизации"
        else
            error "SSH ключи не найдены и пароль не указан в конфиге."
            error "Настройте SSH ключи или добавьте пароль в конфиг ($CONFIG_FILE) и установите sshpass."
            exit 1
        fi
        
        # Создаем директорию (только через sshpass или SSH ключи, без интерактивного ввода)
        if [ "$use_sshpass" = true ]; then
            # Для sshpass: отключаем использование публичных ключей, оставляем только пароль
            sshpass -p "$password" ssh \
                -o StrictHostKeyChecking=no \
                -o PasswordAuthentication=yes \
                -o PubkeyAuthentication=no \
                -o PreferredAuthentications=password \
                "${user}@${host}" "mkdir -p $remote_path" || {
                error "Не удалось создать директорию на удаленном сервере"
                error "Проверьте правильность пароля в конфиге"
                exit 1
            }
            # Очищаем папку dist на удаленном сервере
            log "Очистка папки dist на удаленном сервере..."
            sshpass -p "$password" ssh \
                -o StrictHostKeyChecking=no \
                -o PasswordAuthentication=yes \
                -o PubkeyAuthentication=no \
                -o PreferredAuthentications=password \
                "${user}@${host}" "rm -rf $remote_path/dist" 2>/dev/null || {
                log "Папка dist не найдена или уже очищена"
            }
        else
            # Для SSH ключей используем BatchMode, чтобы исключить интерактивный ввод пароля
            ssh -o StrictHostKeyChecking=no -o BatchMode=yes "${user}@${host}" "mkdir -p $remote_path" || {
                error "Не удалось создать директорию на удаленном сервере"
                error "Проверьте наличие SSH ключей и правильность настройки SSH"
                exit 1
            }
            # Очищаем папку dist на удаленном сервере
            log "Очистка папки dist на удаленном сервере..."
            ssh -o StrictHostKeyChecking=no -o BatchMode=yes "${user}@${host}" "rm -rf $remote_path/dist" 2>/dev/null || {
                log "Папка dist не найдена или уже очищена"
            }
        fi
        
        # Загружаем файлы через scp (только через sshpass или SSH ключи, без интерактивного ввода)
        log "Загрузка файлов через scp..."
        if [ "$use_sshpass" = true ]; then
            # Для sshpass: отключаем использование публичных ключей, оставляем только пароль
            sshpass -p "$password" scp -r \
                -o StrictHostKeyChecking=no \
                -o PasswordAuthentication=yes \
                -o PubkeyAuthentication=no \
                -o PreferredAuthentications=password \
                "$temp_dir/"* "${user}@${host}:${remote_path}/" || {
                error "Не удалось загрузить файлы на сервер"
                error "Проверьте правильность пароля в конфиге"
                exit 1
            }
        else
            # Для SSH ключей используем BatchMode, чтобы исключить интерактивный ввод пароля
            scp -r -o StrictHostKeyChecking=no -o BatchMode=yes "$temp_dir/"* "${user}@${host}:${remote_path}/" || {
                error "Не удалось загрузить файлы на сервер"
                error "Проверьте наличие SSH ключей и правильность настройки SSH"
                exit 1
            }
        fi
        
        success "Файлы успешно загружены на сервер"
        
    elif [[ "$ha_path" == sftp://* ]]; then
        # Старый формат SFTP (для обратной совместимости)
        warning "Используется устаревший формат sftp://, рекомендуется использовать scp://"
        
        local sftp_host=$(echo "$ha_path" | sed 's|sftp://||' | cut -d'/' -f1)
        local remote_path="/$(echo "$ha_path" | sed 's|sftp://[^/]*/||')"
        
        log "SFTP хост: $sftp_host"
        log "Удаленный путь: $remote_path"
        
        # Создание директории на удаленном сервере
        log "Создание директории на удаленном сервере..."
        ssh "$sftp_host" "mkdir -p $remote_path"
        
        # Загрузка файлов через scp
        log "Загрузка файлов через scp..."
        scp -r "$temp_dir/"* "$sftp_host:$remote_path/"
              
    elif [[ "$ha_path" == /mnt/* ]] || [[ "$ha_path" == /* ]]; then
        # Локальный путь
        log "Копирование в локальную папку: $ha_path"
        mkdir -p "$ha_path"
        cp -r "$temp_dir/"* "$ha_path/"
        
    else
        error "Неподдерживаемый формат пути: $ha_path"
        error "Поддерживаются: scp://user@host/path или /local/path"
        exit 1
    fi
    
    success "Файлы успешно загружены"
}

# Очистка временных файлов
cleanup() {
    local temp_dir="$1"
    
    if [ -n "$temp_dir" ] && [ -d "$temp_dir" ]; then
        log "Очистка временных файлов..."
        rm -rf "$temp_dir"
        success "Временные файлы удалены"
    fi
}

# Основная функция
main() {
    log "=== Начинаем развертывание проекта в Home Assistant ==="
    
    # Проверка структуры проекта
    check_project_structure
    
    # Проверка требований
    check_requirements
    
    # Получение пути к HA (логи идут в stderr, путь - в stdout)
    local ha_path=$(get_ha_path "$1" 2>/dev/tty)
    log "Путь к HA addons: $ha_path"

    # Сборка frontend
    build_frontend
    
    # Создание временной папки
    local temp_dir=$(create_temp_dir)
    echo "temp_dir: $temp_dir"
    
    # Обработка ошибок и очистка
    trap "cleanup '$temp_dir'" EXIT
    
    # Копирование файлов
    copy_files "$temp_dir"
    
    # Загрузка файлов
    upload_files "$temp_dir" "$ha_path"
    
    success "=== Развертывание завершено успешно! ==="
    log "Проект развернут в: $ha_path"
    log "Для применения изменений перезапустите addon в Home Assistant"

}

# Обработка аргументов командной строки
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Использование: $0 [путь_к_ha_addons]"
    echo ""
    echo "Аргументы:"
    echo "  путь_к_ha_addons    Путь к папке HA addons (опционально)"
    echo "                      По умолчанию: sftp://root@192.168.0.78/var/lib/homeassistant/addons/local/my_addons"
    echo ""
    echo "Примеры:"
    echo "  $0"
    echo "  $0 scp://user@192.168.1.100/var/lib/homeassistant/addons/local/my_addons/my_home"
    echo "  $0 /mnt/usb/addons/my_addons"
    echo ""
    echo "Требования:"
    echo "  - nvm (Node Version Manager)"
    echo "  - yarn"
    echo "  - scp (OpenSSH)"
    echo "  - ssh (для подключения)"
    echo "  - sshpass (опционально, для авторизации по паролю)"
    echo ""
    echo "Учетные данные:"
    echo "  Учетные данные сохраняются в файле deploy.conf рядом со скриптом"
    echo "  При первом запуске будет запрошен хост, логин, пароль и путь"
    echo "  В дальнейшем можно использовать сохраненные данные"
    exit 0
fi

# Запуск основной функции
main "$@"
