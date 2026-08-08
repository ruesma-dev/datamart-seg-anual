# Dockerfile
# ETL datamart-seg-anual como job (ejecución puntual, no servidor).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config/ config/
COPY etl_sigrid/ etl_sigrid/
COPY main.py .

# Identidad de la build, la que reporta `python main.py version`. Va al final
# a propósito: cambia en cada build y aquí no invalida las capas de arriba.
ARG IMAGE_TAG=local
ARG BUILD_DATE=local
ENV IMAGE_TAG=${IMAGE_TAG} \
    BUILD_DATE=${BUILD_DATE}

# El job nocturno SIEMPRE full (el incremental pierde UPDATEs).
# La config llega por variables de entorno del Container Apps Job (no .env).
ENTRYPOINT ["python", "main.py"]
CMD ["run-all", "--full"]
