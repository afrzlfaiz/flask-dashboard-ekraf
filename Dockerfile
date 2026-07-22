FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','10000')+'/healthz', timeout=3)"

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-10000} --worker-class gthread --workers 1 --threads 4 --timeout 120 --access-logfile - --error-logfile - 'app:create_app()'"]
