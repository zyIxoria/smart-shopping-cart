# Build context = thư mục gốc dự án:  docker build -f backend/Dockerfile .
# Giai đoạn 1: build frontend (React) -> frontend/dist
FROM node:22-slim AS web
WORKDIR /src
COPY frontend/package.json frontend/
RUN cd frontend && npm install --no-audit --no-fund
COPY frontend frontend
COPY data data
RUN cd frontend && node build.mjs

# Giai đoạn 2: Backend (Python) phục vụ luôn frontend/dist
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared shared
COPY backend backend
COPY data data
COPY --from=web /src/frontend/dist frontend/dist
ENV DB_PATH=/app/db/smartcart.db
RUN mkdir -p /app/db
EXPOSE 8000 8081
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["python", "-m", "backend.main"]
