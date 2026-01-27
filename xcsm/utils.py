import os
from pymongo import MongoClient
from django.conf import settings

def get_mongo_db():
    """
    Retourne une instance de la base de données MongoDB pour stocker les granules.
    """
    # Récupération de l'URI depuis les variables d'environnement (Production)
    # ou par défaut localhost (Développement)
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
    
    # DEBUG: Vérifier si la variable est bien chargée
    if mongo_uri == 'mongodb://localhost:27017/':
        print("⚠️ [MONGO] Attention: Utilisation du fallback LOCALHOST. 'MONGO_URI' est absent ou vide.")
        # DEBUG: Lister les clés disponibles (sans valeurs) pour voir s'il y a une typo
        try:
            print(f"ℹ️ [ENV] Clés disponibles: {list(os.environ.keys())}")
        except:
            pass
    else:
        masked = mongo_uri.split('@')[-1] if '@' in mongo_uri else '...'
        print(f"✅ [MONGO] URI chargée avec succès (Cluster: {masked})")
    
    client = MongoClient(mongo_uri)
    
    # On se connecte à la base de données 'xcsm_granules_db'
    db = client['xcsm_granules_db']
    return db