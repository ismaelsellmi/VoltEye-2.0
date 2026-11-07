FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt
COPY volteye ./volteye
COPY api ./api
COPY db ./db
COPY artifacts ./artifacts
COPY docs/*.md ./docs/
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
