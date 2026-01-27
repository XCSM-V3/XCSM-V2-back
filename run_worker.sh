#!/bin/bash
echo "🚀 Démarrage du Worker Celery pour XCSM..."
echo "Assurez-vous que votre Broker (RabbitMQ ou Redis) est lancé."
echo "----------------------------------------------------------------"

# Activation de l'environnement virtuel si besoin
source venv/bin/activate 2>/dev/null || echo "⚠️  Pas de virtualenv 'venv' trouvé, on continue..."

# Lancement du worker
# -A xcsm_project : indique l'application Celery
# worker : le mode
# --loglevel=info : pour voir ce qui se passe
celery -A xcsm_project worker --loglevel=info
