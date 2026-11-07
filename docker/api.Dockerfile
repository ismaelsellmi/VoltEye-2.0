FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt
# Modèle de plongements multilingue du RAG, embarqué dans l'image (aucun téléchargement à l'exécution)
ENV VOLTEYE_MODELS=/opt/models
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', cache_dir='/opt/models')"
COPY volteye ./volteye
COPY api ./api
COPY agent ./agent
COPY db ./db
COPY artifacts ./artifacts
COPY docs/*.md ./docs/
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
