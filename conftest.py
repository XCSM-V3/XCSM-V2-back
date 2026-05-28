"""
conftest.py - Configuration globale des tests XCSM

Force l'utilisation de SQLite en mémoire pour les tests
afin d'éviter la dépendance à MySQL/Docker.
"""
import os
import django
from django.conf import settings


def pytest_configure(config):
    """Surcharge la config Django AVANT le chargement des modèles."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xcsm_project.settings')
    os.environ['DB_ENGINE'] = 'django.db.backends.sqlite3'
    os.environ['DB_NAME'] = ':memory:'

    # Supprimer les variables MySQL qui pourraient interférer
    for key in ['DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD']:
        os.environ.pop(key, None)
