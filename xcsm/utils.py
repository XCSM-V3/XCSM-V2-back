import os
from pymongo import MongoClient
from django.conf import settings

# Globals pour le Singleton
_mongo_client = None
_mongo_db = None

def get_mongo_db():
    """
    Retourne une instance UNIQUE de la base de données MongoDB (Singleton).
    Évite de recréer une connexion pour chaque requête.
    """
    global _mongo_client, _mongo_db
    
    if _mongo_db is not None:
        return _mongo_db

    # Récupération de l'URI
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
    
    # Nettoyage
    if mongo_uri:
        mongo_uri = mongo_uri.strip().strip("'").strip('"')

    try:
        if _mongo_client is None:
            # print(f"🔌 [MONGO] Initialisation de la connexion unique...")
            _mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        
        _mongo_db = _mongo_client['xcsm_granules_db']
        # print("✅ [MONGO] Connexion établie et mise en cache.")
        return _mongo_db
        
    except Exception as e:
        print(f"❌ [MONGO] Erreur critique connexion: {e}")
        raise e