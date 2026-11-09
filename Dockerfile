
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/orbita.sqlite3

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt \
    && mkdir -p /data /app/dist/assets

COPY app.py schema.sql ./

# Copy frontend files from GitHub repository root
COPY index.html registro.html procedimiento.html styles.css crud.css crud.js logo-orbita.svg universo.jpg ./dist/

# Also make images available through the /assets/ route
RUN cp /app/dist/logo-orbita.svg /app/dist/assets/ \
    && cp /app/dist/universo.jpg /app/dist/assets/

EXPOSE 8080

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 30 --no-control-socket app:app"]
