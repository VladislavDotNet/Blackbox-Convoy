
.PHONY: install test lint format run clean help  # Объявляем таргеты как "phony" (не файлы)

help:  # Таргет для вывода списка всех доступных команд
	@echo "Доступные команды:"  # Выводим текст в консоль (@ скрывает саму команду echo)
	@echo "  make install  - Установить все зависимости"
	@echo "  make test     - Запустить тесты"
	@echo "  make lint     - Проверить код линтером"
	@echo "  make format   - Отформатировать код"
	@echo "  make run      - Запустить ETL пайплайн локально"
	@echo "  make clean    - Удалить временные файлы и кэш"

install:  # Таргет для установки зависимостей
	pip install --upgrade pip  # Сначала обновляем pip
	pip install -r requirements.txt  # Устанавливаем основные зависимости
	pip install -r requirements-dev.txt  # Устанавливаем dev-зависимости

test:  # Таргет для запуска тестов
	pytest tests/ -v --cov=src  # Запускаем pytest с подробным выводом (-v) и замером покрытия (--cov)

lint:  # Таргет для проверки кода на ошибки
	flake8 src/ tests/  # Проверяем папки src и tests через flake8

format:  # Таргет для автоформатирования кода
	black src/ tests/  # Форматируем код через black
	isort src/ tests/  # Сортируем импорты через isort

run:  # Таргет для локального запуска основного скрипта
	python -m src.extract.extract  # Запускаем модуль extract как скрипт

clean:  # Таргет для очистки мусора
	find . -type d -name "__pycache__" -exec rm -rf {} +  # Удаляем все папки __pycache__
	find . -type f -name "*.pyc" -delete  # Удаляем все .pyc файлы
	rm -rf .pytest_cache htmlcov .coverage  # Удаляем артефакты тестов