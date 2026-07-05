# XCSM Backend V3 — API d'Intelligence Pédagogique

> Moteur cognitif de XCSM : transforme des documents PDF/DOCX en granules  
> d'apprentissage hiérarchiques, enrichis par IA (Google Gemini) et par  
> des mécanismes collaboratifs temps réel.

**Encadreur :** Pr BATCHAKUI Bernabé — ENSPY, Université de Yaoundé I  
**Déployé sur :** Render — https://votre-backend.onrender.com

---

## 📋 Table des Matières

1. [Description](#description)
2. [Nouveautés V3](#nouveautés-v3)
3. [Stack Technologique](#stack-technologique)
4. [Architecture Hybride MySQL + MongoDB](#architecture-hybride)
5. [Installation Locale](#installation-locale)
6. [Déploiement Docker](#déploiement-docker)
7. [Variables d'Environnement](#variables-denvironnement)
8. [Structure des Dossiers](#structure-des-dossiers)
9. [Endpoints API](#endpoints-api)
10. [Modules V3 — Détail Technique](#modules-v3--détail-technique)
11. [Sécurité](#sécurité)
12. [Tests](#tests)
13. [Celery — Tâches Asynchrones](#celery--tâches-asynchrones)
14. [Performances et Monitoring](#performances-et-monitoring)

---

## 📖 Description

**XCSM Backend V3** est une API REST Django qui transforme des documents pédagogiques non structurés (PDF, DOCX) en **granules d'apprentissage** organisés selon une hiérarchie à 5 niveaux :
Cours → Parties → Chapitres → Sections → Notions (granules atomiques)

Avec la V3, le backend devient un **Moteur Cognitif** : il analyse sémantiquement le contenu, intègre des interactions sociales (commentaires, votes) et propose une assistance IA en temps réel via Gemini.

**État actuel :**
- Phase 1 (Parsing + Structure) : ✅ 100%
- Phase 2 (IA + Analytics) : 🔄 30%
- Phase 3 (Collaboration) : 🔄 0%
- Phase 4 (ML avancé) : 🔄 0%

---

## 🌟 Nouveautés V3

### Module 1 — Assistant IA Conversationnel

- Intégration **Google Gemini 1.5 Flash** (primaire) + **OpenAI** (fallback)
- **Streaming SSE** via `StreamingHttpResponse` Django : réponses mot par mot
- Conscience du contexte : le granule actuellement lu est injecté dans le prompt
- **Rate limiting** : 10 messages/minute/utilisateur

### Module 2 — Segmentation Sémantique ML

- **Algorithme "Zéro Perte"** : le document brut est sauvegardé intégralement en HTML dans MongoDB avant tout traitement
- **Orchestrateur IA** (Celery workers) : enrichissement des métadonnées sans altérer la donnée source
- Injection automatique : Introductions, Notions clés, Objectifs pédagogiques

### Module 3 — Analytics & Dashboard Pédagogique

- **Tracking silencieux** : durée de consultation par granule (anonymisé RGPD)
- **Détection des zones de difficulté** : algorithme sur taux de complétion + revisites
- **Synthèse IA** : rapports pédagogiques textuels pour les enseignants via Gemini
- Conformité RGPD : aucun identifiant personnel stocké dans les analytics

### Module 4 — Collaboration & Commentaires

- Fils de discussions (threads) liés à des granules spécifiques
- Upvotes / Downvotes (idempotent via upsert)
- Notifications événementielles (polling 15s côté frontend)

---

## 🛠️ Stack Technologique

| Composant | Technologie | Version |
|---|---|---|
| Framework | Django + Django REST Framework | 5.x |
| DB Relationnelle | **MySQL** 8.0 | Users, Auth, Analytics |
| DB Documents | MongoDB | 7.0 — Cours, Granules, Commentaires |
| Cache / Broker | Redis | 7.x |
| Async Worker | Celery | 5.x |
| IA Primaire | Google Generative AI (Gemini 1.5) | latest |
| IA Fallback | OpenAI API | latest |
| Parsing PDF | PyMuPDF (fitz) | latest |
| Parsing DOCX | Mammoth | latest |
| Conteneurisation | Docker + Docker Compose | latest |
| Auth | SimpleJWT | latest |
| Docs API | drf-spectacular (Swagger) | latest |

---

## 🗄️ Architecture Hybride
┌──────────────────────┐       ┌──────────────────────┐
│       MySQL 8.0      │       │     MongoDB 7.0       │
│                      │       │                       │
│  • Users & Auth      │       │  • Cours (structure)  │
│  • Rôles & Perms     │       │  • Granules (HTML)    │
│  • Analytics Events  │◄─────►│  • Commentaires       │
│  • Notifications     │       │  • Historique IA      │
│  • Sessions JWT      │       │  • Métadonnées ML     │
└──────────────────────┘       └──────────────────────┘
▲                              ▲
│                              │
└──────────────┬───────────────┘
│
┌────────▼─────────┐
│   Django ORM     │
│  +  PyMongo      │
└──────────────────┘
│
┌────────▼─────────┐
│  Celery + Redis  │
│  (ML Pipeline)   │
└──────────────────┘

**Pourquoi MySQL et non PostgreSQL ?**

MySQL 8.0 est utilisé (et non PostgreSQL recommandé dans le CDC) car le projet était initialement développé avec MySQL et la migration représente un risque avant la V3. Les limitations sont compensées par :
- Des index composites sur toutes les colonnes analytiques
- Des requêtes optimisées avec `VALUES` + agrégats MySQL natifs
- MongoDB pour toutes les données non-relationnelles

---

## 🚀 Installation Locale

### Prérequis

- Python ≥ 3.11
- MySQL 8.0
- MongoDB 7.0
- Redis 7.x
- (Optionnel) Docker & Docker Compose

### Étapes

```bash
# 1. Cloner le dépôt
git clone https://github.com/votre-org/xcsm-backend.git
cd xcsm-backend

# 2. Créer et activer l'environnement virtuel
python -m venv venv
source venv/bin/activate        # Linux/Mac
# ou
venv\Scripts\activate           # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos valeurs (voir section Variables d'Environnement)

# 5. Créer la base MySQL
mysql -u root -p
# Dans MySQL :
CREATE DATABASE xcsm_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'xcsm_user'@'localhost' IDENTIFIED BY 'votre_password';
GRANT ALL PRIVILEGES ON xcsm_db.* TO 'xcsm_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;

# 6. Appliquer les migrations
python manage.py migrate

# 7. Créer un superuser
python manage.py createsuperuser

# 8. Lancer le serveur
python manage.py runserver

# 9. (Autre terminal) Lancer Celery worker
celery -A core worker -l info

# 10. (Autre terminal - optionnel) Monitoring Celery
celery -A core flower
```

---

## 🐳 Déploiement Docker

```bash
# Build et démarrage de tous les services
docker-compose up --build

# En arrière-plan
docker-compose up -d --build

# Appliquer les migrations
docker-compose exec django python manage.py migrate

# Créer superuser
docker-compose exec django python manage.py createsuperuser
```

**Services Docker :**

| Service | Port | Description |
|---|---|---|
| django | 8000 | API REST principale |
| mysql | 3306 | Base relationnelle |
| mongodb | 27017 | Base documents |
| redis | 6379 | Cache + Broker Celery |
| celery | — | Worker ML asynchrone |
| flower | 5555 | Dashboard monitoring Celery |

---

## ⚙️ Variables d'Environnement

Créer `.env` à la racine (ne jamais committer de clés en clair) :

### 💾 Sauvegarde et Restauration (.env)

Pour éviter que votre clé API Gemini ne soit scannée et révoquée par GitHub/Google, le fichier `.env` a été encodé en Base64 et poussé sous le nom de `env_back_backup.txt`.

Pour le restaurer après avoir cloné le dépôt :
```bash
base64 -d env_back_backup.txt > .env
```

### Template de base

```bash
# ============================================
# DJANGO CORE
# ============================================
SECRET_KEY=votre_secret_key_aleatoire_minimum_50_caracteres
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# ============================================
# BASE DE DONNÉES MySQL
# ============================================
DB_ENGINE=django.db.backends.mysql
DB_NAME=xcsm_db
DB_USER=xcsm_user
DB_PASSWORD=votre_password_mysql
DB_HOST=localhost
DB_PORT=3306

# ============================================
# MONGODB
# ============================================
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB_NAME=xcsm_db

# ============================================
# REDIS + CELERY
# ============================================
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# ============================================
# IA — CLÉS SECRÈTES (NE JAMAIS EXPOSER)
# ============================================
GEMINI_API_KEY=votre_vraie_cle_google_gemini
OPENAI_API_KEY=votre_cle_openai_fallback

# ============================================
# CORS (Frontend autorisé)
# ============================================
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://xcsm-frontend-app.vercel.app

# ============================================
# JWT
# ============================================
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=15
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7
```

---

## 📁 Structure des Dossiers
xcsm-backend/
│
├── core/                          # Configuration Django principale
│   ├── settings/
│   │   ├── base.py                # Settings communs
│   │   ├── development.py         # Settings dev (DEBUG=True)
│   │   └── production.py          # Settings prod (HTTPS, etc.)
│   ├── urls.py                    # Routes racine
│   ├── celery.py                  # Configuration Celery
│   └── wsgi.py
│
├── apps/
│   ├── authentication/            # Gestion utilisateurs & JWT
│   │   ├── models.py              # CustomUser
│   │   ├── views.py               # Login, Register, Refresh
│   │   ├── serializers.py
│   │   └── permissions.py         # IsTeacher, IsStudent
│   │
│   ├── documents/                 # Upload & parsing documents
│   │   ├── models.py              # Document, ProcessingTask
│   │   ├── views.py               # Upload, statut processing
│   │   ├── processing.py          # Moteur PyMuPDF + Mammoth
│   │   ├── tasks.py               # Celery tasks (segmentation)
│   │   └── serializers.py
│   │
│   ├── courses/                   # Structure hiérarchique des cours
│   │   ├── models.py              # Course (MySQL) + hiérarchie MongoDB
│   │   ├── views.py               # CRUD cours, granules
│   │   ├── serializers.py
│   │   └── mongo_service.py       # Accès MongoDB (PyMongo)
│   │
│   ├── ai_assistant/              # IA pédagogique (Module 1 V3)
│   │   ├── views.py               # AIChatStreamView (SSE)
│   │   ├── throttles.py           # Rate limiting (10/min)
│   │   ├── prompts.py             # Templates de prompts Gemini
│   │   └── urls.py
│   │
│   ├── analytics/                 # Analytics & Dashboard (Module 3 V3)
│   │   ├── models.py              # AnalyticsEvent (anonymisé RGPD)
│   │   ├── views.py               # Track, Dashboard, AI Summary
│   │   ├── services.py            # Algorithmes détection difficulté
│   │   └── serializers.py
│   │
│   ├── comments/                  # Collaboration (Module 4 V3)
│   │   ├── models.py              # Comment, Vote (MySQL)
│   │   ├── views.py               # CRUD + vote endpoint
│   │   ├── serializers.py
│   │   └── permissions.py
│   │
│   ├── notifications/             # Notifications (polling)
│   │   ├── models.py              # Notification (MySQL)
│   │   ├── views.py               # List, MarkRead
│   │   └── services.py            # create_notification() helper
│   │
│   └── ml_engine/                 # Segmentation ML (Module 2 V3)
│       ├── tasks.py               # Celery tasks ML
│       ├── orchestrator.py        # Orchestrateur IA (Gemini)
│       └── segmentation.py        # Algorithmes de découpage
│
├── requirements.txt               # Dépendances Python (versions fixées)
├── requirements-dev.txt           # Dépendances développement
├── docker-compose.yml
├── Dockerfile
├── .env.example                   # Template variables (commité)
├── .env                           # ⛔ NON COMMITÉ — vos vraies valeurs
└── manage.py

---

## 🔗 Endpoints API

### Authentification

| Méthode | Endpoint | Description | Auth |
|---|---|---|---|
| POST | `/api/auth/register/` | Inscription | ❌ |
| POST | `/api/auth/login/` | Connexion → JWT | ❌ |
| POST | `/api/auth/refresh/` | Refresh du token | ❌ |
| GET | `/api/auth/me/` | Profil utilisateur | ✅ |

### Cours & Granules

| Méthode | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/api/courses/` | Liste des cours | ✅ |
| POST | `/api/courses/` | Créer un cours | ✅ Enseignant |
| GET | `/api/courses/{id}/` | Détail cours | ✅ |
| GET | `/api/courses/{id}/hierarchy/` | Arborescence complète | ✅ |
| GET | `/api/granules/{id}/` | Lire un granule | ✅ |

### Documents (Upload + Parsing)

| Méthode | Endpoint | Description | Auth |
|---|---|---|---|
| POST | `/api/documents/upload/` | Upload PDF/DOCX | ✅ Enseignant |
| GET | `/api/documents/{id}/status/` | Statut processing Celery | ✅ |
| POST | `/api/documents/{id}/segment/` | Déclencher segmentation ML | ✅ Enseignant |

### IA Pédagogique (Module 1)

| Méthode | Endpoint | Description | Auth | Limite |
|---|---|---|---|---|
| POST | `/api/ai/chat/stream/` | Chat IA (SSE streaming) | ✅ | 10/min |
| POST | `/api/ai/summary/` | Synthèse IA enseignant | ✅ Enseignant | 2/heure |

### Analytics (Module 3)

| Méthode | Endpoint | Description | Auth |
|---|---|---|---|
| POST | `/api/analytics/track/` | Tracker une consultation (anonymisé) | ✅ |
| GET | `/api/analytics/dashboard/` | Dashboard enseignant | ✅ Enseignant |
| GET | `/api/analytics/dashboard/{courseId}/` | Dashboard par cours | ✅ Enseignant |

### Commentaires (Module 4)

| Méthode | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/api/comments/?granule_id={id}` | Commentaires d'un granule | ✅ |
| POST | `/api/comments/` | Créer un commentaire | ✅ |
| POST | `/api/comments/{id}/vote/` | Upvote / Downvote | ✅ |
| DELETE | `/api/comments/{id}/` | Supprimer (auteur uniquement) | ✅ |

### Notifications

| Méthode | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/api/notifications/` | Lister (non lues) | ✅ |
| PATCH | `/api/notifications/{id}/read/` | Marquer comme lue | ✅ |
| PATCH | `/api/notifications/read-all/` | Tout marquer comme lu | ✅ |

### Système

| Méthode | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/api/health/` | Healthcheck (MySQL + MongoDB + Redis) | ❌ |
| GET | `/api/docs/` | Documentation Swagger | ❌ |

---

## 🔐 Sécurité

### Rate Limiting IA (obligatoire)

```python
# apps/ai_assistant/throttles.py
class AIUserRateThrottle(UserRateThrottle):
    rate = '10/min'   # Chat IA

class AISummaryThrottle(UserRateThrottle):
    rate = '2/hour'   # Synthèse enseignant
```

### Permissions par rôle

```python
# IsTeacher : uniquement les enseignants
# IsStudent  : uniquement les étudiants
# IsAuthenticated : tout utilisateur connecté
```

### Anonymisation RGPD Analytics

```python
# Aucun user_id direct dans analytics_events
# Hash SHA-256 irréversible : anonymize_user_id(user_id)
```

### Variables sensibles

Les clés `GEMINI_API_KEY` et `OPENAI_API_KEY` sont uniquement dans `.env` (backend). **Elles ne sont jamais transmises au frontend.**

---

## 🧪 Tests

```bash
# Tous les tests
python manage.py test

# Module spécifique
python manage.py test apps.ai_assistant
python manage.py test apps.analytics

# Avec coverage
pip install coverage
coverage run manage.py test
coverage report --min-percentage=70
coverage html  # Rapport HTML dans htmlcov/
```

**Couverture cible :** > 70% sur les modules V3.

---

## ⚡ Celery — Tâches Asynchrones

```bash
# Lancer le worker (terminal séparé)
celery -A core worker -l info

# Monitoring (interface web sur http://localhost:5555)
celery -A core flower

# Tâche planifiée (si utilisée)
celery -A core beat -l info
```

**Tâches définies :**

| Tâche | Module | Description | Timeout |
|---|---|---|---|
| `segment_document` | ml_engine | Segmentation ML d'un document | 120s |
| `enrich_granules` | ml_engine | Enrichissement métadonnées IA | 60s |
| `generate_summary` | analytics | Synthèse IA pour enseignant | 30s |

---

## 📊 Performances et Monitoring

**Métriques atteintes (tests sur V2) :**
- Documents PDF traités jusqu'à 50 Mo ✅
- Documents DOCX traités jusqu'à 20 Mo ✅
- Temps de traitement : 2 à 5 secondes par document ✅
- 100 à 200 granules extraits par document moyen ✅
- Précision détection titres : ~85% ✅

**Monitoring recommandé :**
- **Flower** : http://localhost:5555 (Celery workers)
- **Django Admin** : http://localhost:8000/admin (données)
- **Swagger** : http://localhost:8000/api/docs/ (endpoints)

---

## 👥 Auteurs

Projet développé par les étudiants de l'**ENSPY**  
(École Nationale Supérieure Polytechnique de Yaoundé I, Cameroun)

**Encadreur :** Pr BATCHAKUI Bernabé

© XCSM 2025 — Tous droits réservés