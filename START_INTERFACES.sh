#!/bin/bash
# Скрипт для запуска всех интерфейсов проекта 3dtoday

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Используем скрипт из scripts/
bash scripts/start_interfaces.sh
