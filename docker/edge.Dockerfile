FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
COPY requirements-edge.txt .
RUN pip install --no-cache-dir -r requirements-edge.txt
COPY volteye ./volteye
COPY edge ./edge
COPY artifacts ./artifacts
CMD ["python", "-m", "edge.gateway"]
