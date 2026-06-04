FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости системы для Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем Playwright браузеры
RUN playwright install chromium
RUN playwright install-deps

# Копируем код
COPY . .

# Создаём папку для куков
RUN mkdir -p /app/data

# Запускаем бота
CMD ["python", "bot.py"]