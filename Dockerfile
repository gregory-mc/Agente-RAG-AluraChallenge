# Imagen del agente Techie (TechNova) — issue #7 (deploy en OCI)
# Self-contained: el corpus y el índice Chroma se hornean en la imagen (lectura),
# así el contenedor es stateless y apto para OCI Container Instances.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PORT=8000

WORKDIR /app

# 1) Dependencias primero (capa cacheable).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 2) Código + corpus + índice vectorial ya construido.
COPY src/ ./src/
COPY data/documents/ ./data/documents/
COPY chroma_db/ ./chroma_db/

# 3) Usuario no-root y permisos (logs/feedback se escriben bajo /app/data).
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/data/logs /app/data/feedback \
    && chown -R app:app /app
USER app

EXPOSE 8000

# Healthcheck para OCI / orquestadores.
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=4).status==200 else sys.exit(1)"

# Arranque del servidor web (usa el CLI del paquete, que envuelve uvicorn).
CMD ["python", "-m", "rag", "serve", "--host", "0.0.0.0", "--port", "8000"]
