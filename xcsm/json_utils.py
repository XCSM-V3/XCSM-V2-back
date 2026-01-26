# xcsm/json_utils.py - Utilitaires pour manipuler les structures JSON
import json
from bson.objectid import ObjectId
from .utils import get_mongo_db


def get_fichier_json_structure(fichier_source_id):
    """
    Récupère la structure JSON complète d'un fichier depuis MongoDB.
    
    Args:
        fichier_source_id (str/UUID): ID du FichierSource
        
    Returns:
        dict: Structure JSON complète ou None
    """
    try:
        mongo_db = get_mongo_db()
        doc = mongo_db['fichiers_uploades'].find_one({
            "fichier_source_id": str(fichier_source_id)
        })
        
        if doc:
            # Suppression de l'_id MongoDB pour la sérialisation
            doc.pop('_id', None)
            return doc
        
        print(f"⚠️ get_fichier_json_structure: Aucune structure trouvée pour {fichier_source_id}")
        return None
        
    except Exception as e:
        print(f"❌ Erreur get_fichier_json_structure: {e}")
        return None


def get_granule_content(mongo_contenu_id):
    """
    Récupère le contenu JSON d'un granule depuis MongoDB.
    
    Args:
        mongo_contenu_id (str): ID MongoDB du granule
        
    Returns:
        dict: Contenu du granule ou None
    """
    try:
        mongo_db = get_mongo_db()
        doc = mongo_db['granules'].find_one({
            "_id": ObjectId(mongo_contenu_id)
        })
        
        if doc:
            doc['_id'] = str(doc['_id'])  # Conversion pour JSON
            return doc
        return None
        
    except Exception as e:
        print(f"❌ Erreur get_granule_content: {e}")
        return None


def get_cours_complete_structure(cours):
    """
    Reconstruit la structure JSON complète d'un cours avec tous ses granules.
    Utile pour l'export ou l'affichage frontend.
    
    Args:
        cours (Cours): Instance du modèle Cours
        
    Returns:
        dict: Structure hiérarchique complète
    """
    structure = {
        "cours": {
            "id": str(cours.id),
            "code": cours.code,
            "titre": cours.titre,
            "description": cours.description,
            "enseignant": cours.enseignant.utilisateur.username
        },
        "parties": []
    }
    
    for partie in cours.parties.all():
        partie_data = {
            "id": str(partie.id),
            "titre": partie.titre,
            "numero": partie.numero,
            "chapitres": []
        }
        
        for chapitre in partie.chapitres.all():
            chapitre_data = {
                "id": str(chapitre.id),
                "titre": chapitre.titre,
                "numero": chapitre.numero,
                "sections": []
            }
            
            for section in chapitre.sections.all():
                section_data = {
                    "id": str(section.id),
                    "titre": section.titre,
                    "numero": section.numero,
                    "sous_sections": []
                }
                
                for sous_section in section.sous_sections.all():
                    sous_section_data = {
                        "id": str(sous_section.id),
                        "titre": sous_section.titre,
                        "numero": sous_section.numero,
                        "granules": []
                    }
                    
                    # Récupération des granules avec leur contenu MongoDB
                    for granule in sous_section.granules.all():
                        granule_content = get_granule_content(granule.mongo_contenu_id)
                        
                        granule_data = {
                            "id": str(granule.id),
                            "titre": granule.titre,
                            "type": granule.type_contenu,
                            "ordre": granule.ordre,
                            "contenu": granule_content  # Contenu JSON depuis MongoDB
                        }
                        sous_section_data["granules"].append(granule_data)
                    
                    section_data["sous_sections"].append(sous_section_data)
                
                chapitre_data["sections"].append(section_data)
            
            partie_data["chapitres"].append(chapitre_data)
        
        structure["parties"].append(partie_data)
    
    return structure


def export_cours_to_json_file(cours, output_path):
    """
    Exporte un cours complet en fichier JSON.
    
    Args:
        cours (Cours): Instance du cours à exporter
        output_path (str): Chemin du fichier de sortie
    """
    structure = get_cours_complete_structure(cours)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Cours exporté vers {output_path}")


def search_in_granules(query, fichier_source=None):
    """
    Recherche dans les contenus des granules MongoDB.
    
    Args:
        query (str): Terme de recherche
        fichier_source (FichierSource, optional): Filtrer par fichier source
        
    Returns:
        list: Liste des granules correspondants
    """
    try:
        mongo_db = get_mongo_db()
        
        # Construction du filtre
        filter_query = {
            "$or": [
                {"content": {"$regex": query, "$options": "i"}},
                {"html": {"$regex": query, "$options": "i"}}
            ]
        }
        
        if fichier_source:
            filter_query["fichier_source_id"] = str(fichier_source.id)
        
        results = list(mongo_db['granules'].find(filter_query).limit(50))
        
        # Conversion des ObjectId en string
        for doc in results:
            doc['_id'] = str(doc['_id'])
        
        return results
        
    except Exception as e:
        print(f"❌ Erreur search_in_granules: {e}")
        return []


def search_in_granules_filtered(query, fichier_source_ids):
    """
    Recherche dans les granules MongoDB avec filtrage par fichiers sources autorisés.
    Utilisé pour la recherche avec contrôle d'accès basé sur les rôles.
    
    Args:
        query (str): Terme de recherche
        fichier_source_ids (list): Liste des IDs de fichiers sources autorisés
        
    Returns:
        list: Liste des granules correspondants
    """
    try:
        mongo_db = get_mongo_db()
        
        # Construction du filtre avec recherche ET filtrage par fichiers
        filter_query = {
            "$and": [
                {
                    "$or": [
                        {"content": {"$regex": query, "$options": "i"}},
                        {"html": {"$regex": query, "$options": "i"}},
                        {"titre": {"$regex": query, "$options": "i"}}
                    ]
                },
                {
                    "fichier_source_id": {"$in": [str(fid) for fid in fichier_source_ids]}
                }
            ]
        }
        
        results = list(mongo_db['granules'].find(filter_query).limit(100))
        
        # Conversion des ObjectId en string
        for doc in results:
            doc['_id'] = str(doc['_id'])
        
        return results
        
    except Exception as e:
        print(f"❌ Erreur search_in_granules_filtered: {e}")
        return []



def get_statistics():
    """
    Retourne des statistiques sur les données MongoDB.
    
    Returns:
        dict: Statistiques (nb documents, taille, etc.)
    """
    try:
        mongo_db = get_mongo_db()
        
        stats = {
            "fichiers_uploades": mongo_db['fichiers_uploades'].count_documents({}),
            "granules": mongo_db['granules'].count_documents({}),
            "database_name": mongo_db.name
        }
        
        return stats
        
    except Exception as e:
        print(f"❌ Erreur get_statistics: {e}")
        return {}