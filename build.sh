#!/usr/bin/env bash
# =============================================================================
# build.sh — Script de build Render pour XCSM Backend (Django)
# Exécuté automatiquement par Render avant le démarrage du serveur.
# =============================================================================
set -o errexit  # Arrêter immédiatement en cas d'erreur

echo "=== [1/4] Installation des dépendances Python ==="
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo "=== [2/4] Collecte des fichiers statiques (WhiteNoise) ==="
python manage.py collectstatic --no-input

echo "=== [3/4] Application des migrations Django ==="
python manage.py migrate --no-input

echo "=== [4/4] Build terminé avec succès ==="
