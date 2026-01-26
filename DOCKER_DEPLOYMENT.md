# Guide de Déploiement Docker - XCSM Backend

## 🚀 Démarrage Rapide

### Prérequis
- Docker 20.10+
- Docker Compose 2.0+
- 4 GB RAM minimum
- 20 GB espace disque

### 1. Configuration Initiale

```bash
cd /home/rouchda-yampen/Bureau/XCSM_Backend-relié/XCSM_Backend-main

# Copier le fichier d'environnement
cp .env.example .env

# Éditer les variables (IMPORTANT: changer les mots de passe!)
nano .env
```

### 2. Ajouter les dépendances monitoring

```bash
# Ajouter à requirements.txt
cat monitoring_requirements.txt >> requirements.txt
```

### 3. Build et Démarrage

```bash
# Build des images
docker-compose build

# Démarrage de tous les services
docker-compose up -d

# Voir les logs
docker-compose logs -f
```

### 4. Initialisation de la Base

```bash
# Attendre que MySQL soit prêt (30 secondes)
sleep 30

# Migrations Django
docker-compose exec api python manage.py migrate

# Créer un superuser
docker-compose exec api python manage.py createsuperuser
```

---

## 📊 Services Disponibles

| Service | URL | Description |
|:--------|:----|:------------|
| **API Django** | http://localhost:8000 | API REST principale |
| **Admin Django** | http://localhost:8000/admin | Interface admin |
| **Grafana** | http://localhost:3000 | Dashboards monitoring |
| **Prometheus** | http://localhost:9090 | Métriques |
| **MySQL** | localhost:3306 | Base données relationnelle |
| **MongoDB** | localhost:27017 | Base documents |
| **Redis** | localhost:6379 | Broker Celery |

**Credentials Grafana par défaut:** `admin / admin` (à changer!)

---

## 🔍 Monitoring et Métriques

### Prometheus Targets

Accessible sur http://localhost:9090/targets

- ✅ `django-api` - Métriques API (requêtes, temps de réponse)
- ✅ `redis` - Métriques Redis (mémoire, connexions)
- ✅ `mysql` - Métriques MySQL (queries, connexions)
- ✅ `celery-worker` - Métriques Celery (tâches, échecs)

### Grafana Dashboards

1. **Accéder à Grafana:** http://localhost:3000
2. **Login:** admin / admin
3. **Ajouter Prometheus datasource:**
   - Configuration > Data Sources > Add Prometheus
   - URL: http://prometheus:9090
   - Save & Test

4. **Importer dashboards:**
   - Dashboard ID `12900` - Redis
   - Dashboard ID `7362` - MySQL
   - Dashboard ID `10991` - Django

### Métriques Clés Trackées

#### 📈 API Performance
- `http_request_duration_seconds` - Temps de réponse
- `http_requests_total` - Nombre de requêtes
- `http_requests_errors_total` - Erreurs 4xx/5xx

#### ⚙️ Celery
- `celery_tasks_total` - Tâches par statut
- `celery_task_duration_seconds` - Durée des tâches
- `celery_workers_total` - Nombre de workers actifs

#### 💾 Bases de Données
- `redis_memory_used_bytes` - Mémoire Redis
- `mysql_global_status_connections` - Connexions MySQL
- `mysql_global_status_slow_queries` - Requêtes lentes

#### 📤 Upload
- `file_upload_duration_seconds` - Temps d'upload
- `file_processing_total` - Fichiers traités
- `parsing_errors_total` - Erreurs de parsing

---

## 🛠️ Commandes Utiles

### Gestion des Services

```bash
# Arrêter tous les services
docker-compose down

# Redémarrer un service spécifique
docker-compose restart api

# Voir les logs d'un service
docker-compose logs -f worker

# Statut des conteneurs
docker-compose ps

# Utilisation des ressources
docker stats
```

### Celery Worker

```bash
# Consulter les tâches
docker-compose exec worker celery -A xcsm_project inspect active

# Stats des workers
docker-compose exec worker celery -A xcsm_project inspect stats

# Purger la queue
docker-compose exec worker celery -A xcsm_project purge
```

### Base de Données

```bash
# Accéder à MySQL
docker-compose exec mysql mysql -u xcsm_user -p xcsm_db

# Backup MySQL
docker-compose exec mysql mysqldump -u xcsm_user -p xcsm_db > backup.sql

# Accéder à MongoDB
docker-compose exec mongodb mongosh -u admin -p

# Accéder à Redis
docker-compose exec redis redis-cli
```

---

## 🔧 Configuration Avancée

### Scaling Celery Workers

```bash
# Lancer 3 workers
docker-compose up -d --scale worker=3
```

### Variables d'Environnement Importantes

```env
# Performance
CELERY_WORKER_CONCURRENCY=4
GUNICORN_WORKERS=4

# Monitoring
PROMETHEUS_SCRAPE_INTERVAL=15s

# Sécurité
DEBUG=False
SECRET_KEY=<génér é-avec-django>
```

---

## 📦 Déploiement Production

### Checklist Sécurité

- [ ] Changer tous les mots de passe par défaut
- [ ] Générer nouveau SECRET_KEY Django
- [ ] Définir ALLOWED_HOSTS correctement
- [ ] Activer HTTPS (reverse proxy nginx)
- [ ] Configurer firewall (ports 8000, 3000, 9090 fermés)
- [ ] Backup automatique des données
- [ ] Logs rotation configurée
- [ ] Rate limiting API

### Volumes Persistants

Les données sont stockées dans:
```
mysql_data/      - Base MySQL
mongodb_data/    - Base MongoDB
redis_data/      - Persistence Redis
prometheus_data/ - Métriques historiques
grafana_data/    - Configuration Grafana
```

**Backup:**
```bash
# Backup complet
docker run --rm --volumes-from xcsm_mysql -v $(pwd):/backup ubuntu \
  tar czf /backup/mysql_backup.tar.gz /var/lib/mysql
```

---

## 🐛 Troubleshooting

### API ne démarre pas

```bash
# Vérifier les logs
docker-compose logs api

# Vérifier que MySQL est prêt
docker-compose exec mysql mysqladmin ping

# Refaire les migrations
docker-compose exec api python manage.py migrate --fake-initial
```

### Worker Celery ne traite pas les tâches

```bash
# Vérifier que Redis est accessible
docker-compose exec redis redis-cli ping

# Redémarrer le worker
docker-compose restart worker

# Vérifier les tâches en attente
docker-compose exec worker celery -A xcsm_project inspect reserved
```

### Prometheus ne scrape pas

```bash
# Vérifier la config
docker-compose exec prometheus promtool check config /etc/prometheus/prometheus.yml

# Reload config
docker-compose exec prometheus kill -HUP 1
```

---

## 📊 Architecture Deployed

```
┌─────────────────────────────────────────┐
│           XCSM Production Stack         │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────┐  ┌──────────┐           │
│  │   API    │  │  Worker  │           │
│  │ :8000    │  │  Celery  │           │
│  └────┬─────┘  └────┬─────┘           │
│       │             │                  │
│  ┌────┴──────┬──────┴────┬────────┐  │
│  │   MySQL   │  MongoDB  │ Redis  │  │
│  │   :3306   │  :27017   │ :6379  │  │
│  └───────────┴───────────┴────────┘  │
│                                         │
│  ┌──────────────────────────────────┐ │
│  │  Monitoring Stack                │ │
│  │  ┌───────────┐  ┌────────────┐  │ │
│  │  │Prometheus │  │  Grafana   │  │ │
│  │  │  :9090    │  │   :3000    │  │ │
│  │  └───────────┘  └────────────┘  │ │
│  └──────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**Tous les services sont isolés et communicent via le réseau Docker `xcsm_network`.**
