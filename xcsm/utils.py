# xcsm/utils.py
from pymongo import MongoClient
from django.conf import settings

def get_mongo_db():
    """
    Retourne une instance de la base de données MongoDB pour stocker les granules.
    """
    # Connexion au serveur MongoDB local
    client = MongoClient('mongodb://localhost:27017/')
    
    # On se connecte à la base de données 'xcsm_granules_db'
    # (MongoDB la créera automatiquement dès qu'on y écrira quelque chose)
    db = client['xcsm_granules_db']
    return db