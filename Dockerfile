# Dockerfile pour l'API Django REST
FROM python:3.12-slim

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Répertoire de travail
WORKDIR /app

# Installation des dépendances système (avec retry sur les miroirs instables)
RUN for i in 1 2 3; do apt-get update -o Acquire::Retries=5 && break || sleep 5; done && \
    apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    tesseract-ocr \
    tesseract-ocr-fra \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copie des requirements
COPY requirements.txt .

# Installation des dépendances Python
RUN pip install --no-cache-dir "setuptools<82" && \
    pip install --no-cache-dir -r requirements.txt

# Copie du code de l'application
COPY . .

# Création du répertoire media
RUN mkdir -p /app/media

# Collecte des fichiers statiques
RUN python manage.py collectstatic --noinput || true

# Port exposé
EXPOSE 8000

# Commande par défaut (API Django)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "300", "xcsm_project.wsgi:application"]
