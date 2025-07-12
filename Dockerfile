FROM python:3.10-slim

# Установка системных зависимостей, необходимых для сборки пакетов
RUN apt-get update && apt-get install -y gcc libpq-dev rustc && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование requirements.txt и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . .

# Создание пользователя для запуска приложения
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Открытие порта для webhook
EXPOSE 8000

# Команда запуска
CMD ["python", "main.py"]