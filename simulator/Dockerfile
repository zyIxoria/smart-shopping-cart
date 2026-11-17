# Build context = thư mục gốc dự án:  docker build -f simulator/Dockerfile .
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY shared shared
COPY simulator simulator
COPY data data
EXPOSE 8090
CMD ["python", "-m", "simulator.main", "--no-cli"]
