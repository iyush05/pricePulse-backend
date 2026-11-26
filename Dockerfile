FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN sed -i 's|URIs: http://deb.debian.org/debian$|URIs: http://ftp.us.debian.org/debian|' /etc/apt/sources.list.d/debian.sources && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get -o Acquire::ForceIPv4=true \
            -o Acquire::http::No-Cache=true \
            -o Acquire::Pipeline-Depth=0 \
            -o Acquire::BrokenProxy=true \
            -o Acquire::Retries=3 \
            update && \
    apt-get -o Acquire::ForceIPv4=true \
            install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
