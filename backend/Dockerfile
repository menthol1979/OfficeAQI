FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app ./backend/app
COPY frontend ./frontend

ENV FRONTEND_DIR=/app/frontend \
    DB_PATH=/data/env.db \
    PORT=8090 \
    HOST=0.0.0.0

VOLUME ["/data"]
EXPOSE 8090

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8090"]
