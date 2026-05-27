#!/usr/bin/env bash
# build.sh — Script de build Render pour XCSM Backend (Django)
set -o errexit

echo "=== [1/4] Installation des dépendances Python ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== [2/4] Collecte des fichiers statiques (WhiteNoise) ==="
python manage.py collectstatic --no-input

echo "=== [3/4] Application des migrations Django ==="
python manage.py migrate --no-input

echo "=== [4/4] Build terminé avec succès ==="
