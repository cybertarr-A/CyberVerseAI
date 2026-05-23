FROM python:3.11

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

RUN mkdir -p /tmp/cyberverse_scans && \
    chmod -R 777 /tmp/cyberverse_scans

RUN adduser --disabled-password --gecos "" appuser

USER appuser

CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
