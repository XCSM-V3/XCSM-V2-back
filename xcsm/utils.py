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
    
    client = MongoClient(mongo_uri)
    
    # On se connecte à la base de données 'xcsm_granules_db'
    db = client['xcsm_granules_db']
    return db