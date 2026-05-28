# Author: Dilane PAFE
# Fichier: xcsm/json_utils.py - Utilitaires pour manipuler les structures JSON (Intégration IA)

import json
import re
from bson.objectid import ObjectId
from .utils import get_mongo_db

def get_fichier_json_structure(fichier_source_id):
    """Récupère la structure JSON complète d'un fichier depuis MongoDB."""
    try:
        mongo_db = get_mongo_db()
        doc = mongo_db['fichiers_uploades'].find_one({
            "fichier_source_id": str(fichier_source_id)
        })
        if doc:
            doc.pop('_id', None)
            return doc
        return None
    except Exception as e:
        print(f"❌ Erreur get_fichier_json_structure: {e}")
        return None

def get_granule_content(mongo_contenu_id):
    """Récupère le contenu JSON d'un granule depuis MongoDB."""
    try:
        mongo_db = get_mongo_db()
        doc = mongo_db['granules'].find_one({
            "_id": ObjectId(mongo_contenu_id)
        })
        if doc:
            doc['_id'] = str(doc['_id'])
            return doc
        return None
    except Exception as e:
        print(f"❌ Erreur get_granule_content: {e}")
        return None

def get_xccm_cours_structure(cours):
    """
    Génère la structure JSON stricte attendue par le FrontEnd et la plateforme XCCM.
    Va chercher les données intelligentes générées par le Chef d'Orchestre.
    """
    mongo_db = get_mongo_db()
    
    # 1. Récupération des Métadonnées IA depuis le fichier source lié
    ia_intro = "Introduction en cours d'analyse IA."
    ia_concl = "Conclusion en cours d'analyse IA."
    ia_objectifs = []
    ia_mots_cles = []
    
    fichier_source = cours.enseignant.fichiers_uploades.filter(titre=cours.titre).first()
    if fichier_source and fichier_source.mongo_transforme_id:
        doc_mongo = mongo_db['fichiers_uploades'].find_one({"_id": ObjectId(fichier_source.mongo_transforme_id)})
        if doc_mongo and "structure_json" in doc_mongo:
            metadata_ia = doc_mongo["structure_json"].get("metadata_ia", {})
            ia_intro = metadata_ia.get("ia_introduction", ia_intro)
            ia_concl = metadata_ia.get("ia_conclusion", ia_concl)
            ia_objectifs = metadata_ia.get("ia_objectifs", [])
            ia_mots_cles = metadata_ia.get("ia_mots_cles", [])

    # 2. Informations de l'Auteur
    nom_auteur = f"{cours.enseignant.utilisateur.first_name} {cours.enseignant.utilisateur.last_name}".strip()
    if not nom_auteur:
        nom_auteur = cours.enseignant.utilisateur.username
    photo_auteur = cours.enseignant.utilisateur.photo_url.url if hasattr(cours.enseignant.utilisateur, 'photo_url') and cours.enseignant.utilisateur.photo_url else "/placeholder-user.jpg"

    # 3. Structure Globale
    structure = {
        "id": str(cours.id),
        "title": cours.titre,
        "category": cours.matiere.titre if hasattr(cours, 'matiere') and cours.matiere else "Non catégorisé",
        "image": cours.image.url if hasattr(cours, 'image') and cours.image else "/placeholder-course.png",
        "views": 0,
        "likes": 0,
        "downloads": 0,
        "author": {
            "name": nom_auteur,
            "image": photo_auteur
        },
        "introduction": ia_intro,         # INJECTION IA !
        "conclusion": ia_concl,           # INJECTION IA !
        "learningObjectives": ia_objectifs, # INJECTION IA !
        "sections": []
    }

    # 4. Arborescence
    for partie in cours.parties.all().order_by('numero'):
        section_data = {
            "title": partie.titre,
            "introduction": f"Introduction de la section {partie.titre}.",
            "chapters": [],
            "exercise": None
        }

        for chapitre in partie.chapitres.all().order_by('numero'):
            chapter_data = {
                "title": chapitre.titre,
                "introduction": f"Introduction du chapitre {chapitre.titre}.",
                "paragraphs": [],
                "exercise": None
            }

            for section in chapitre.sections.all().order_by('numero'):
                content_html = ""
                # Rétrocompatibilité et concaténation
                if hasattr(section, 'sous_sections') and section.sous_sections.exists():
                    for sous_section in section.sous_sections.all().order_by('numero'):
                        for granule in sous_section.granules.all().order_by('ordre'):
                            gc = get_granule_content(granule.mongo_contenu_id)
                            if gc and "html" in gc:
                                content_html += gc["html"] + "\n"
                elif hasattr(section, 'granules'):
                    for granule in section.granules.all().order_by('ordre'):
                        gc = get_granule_content(granule.mongo_contenu_id)
                        if gc and "html" in gc:
                            content_html += gc["html"] + "\n"

                paragraph_data = {
                    "title": section.titre,
                    "introduction": "Contenu détaillé.",
                    "content": content_html.strip(),
                    "notions": ia_mots_cles, # INJECTION IA des mots-clés dans les paragraphes
                    "exercise": None
                }
                chapter_data["paragraphs"].append(paragraph_data)
            section_data["chapters"].append(chapter_data)
        structure["sections"].append(section_data)

    return structure

def export_cours_to_json_file(cours, output_path):
    structure = get_xccm_cours_structure(cours)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)

def search_in_granules_filtered(query, fichier_source_ids):
    """Recherche MongoDB."""
    try:
        mongo_db = get_mongo_db()
        cleaned_query = re.sub(r'[^\w\s]', ' ', query)
        keywords = [re.escape(w) for w in cleaned_query.split() if w.strip()]
        if not keywords: keywords = [re.escape(query)]

        keyword_conditions = []
        for word in keywords:
            keyword_conditions.append({
                "$or": [
                    {"content": {"$regex": word, "$options": "i"}},
                    {"html": {"$regex": word, "$options": "i"}},
                    {"titre": {"$regex": word, "$options": "i"}}
                ]
            })

        filter_query = {
            "$and": [
                {"$and": keyword_conditions},
                {"fichier_source_id": {"$in": [str(fid) for fid in fichier_source_ids]}}
            ]
        }
        
        results = list(mongo_db['granules'].find(filter_query).limit(100))
        for doc in results:
            doc['_id'] = str(doc['_id'])
        return results
        
    except Exception as e:
        print(f"❌ Erreur search_in_granules_filtered: {e}")
        return []

def get_statistics():
    try:
        mongo_db = get_mongo_db()
        return {
            "fichiers_uploades": mongo_db['fichiers_uploades'].count_documents({}),
            "granules": mongo_db['granules'].count_documents({}),
            "database_name": mongo_db.name
        }
    except Exception as e:
        return {}















# # Author: Dilane PAFE
# # Fichier: xcsm/json_utils.py - Utilitaires pour manipuler les structures JSON

# import json
# import re
# from bson.objectid import ObjectId
# from .utils import get_mongo_db


# def get_fichier_json_structure(fichier_source_id):
#     """
#     Récupère la structure JSON complète d'un fichier depuis MongoDB.
#     """
#     try:
#         mongo_db = get_mongo_db()
#         doc = mongo_db['fichiers_uploades'].find_one({
#             "fichier_source_id": str(fichier_source_id)
#         })
        
#         if doc:
#             doc.pop('_id', None)
#             return doc
        
#         print(f"⚠️ get_fichier_json_structure: Aucune structure trouvée pour {fichier_source_id}")
#         return None
        
#     except Exception as e:
#         print(f"❌ Erreur get_fichier_json_structure: {e}")
#         return None


# def get_granule_content(mongo_contenu_id):
#     """
#     Récupère le contenu JSON d'un granule depuis MongoDB.
#     """
#     try:
#         mongo_db = get_mongo_db()
#         doc = mongo_db['granules'].find_one({
#             "_id": ObjectId(mongo_contenu_id)
#         })
        
#         if doc:
#             doc['_id'] = str(doc['_id'])
#             return doc
#         return None
        
#     except Exception as e:
#         print(f"❌ Erreur get_granule_content: {e}")
#         return None


# def get_xccm_cours_structure(cours):
#     """
#     Génère la structure JSON stricte attendue par la plateforme externe XCCM.
#     Mappe la hiérarchie: Partie -> section, Chapitre -> chapter, Section+Granules -> paragraph.
#     Intègre les champs d'enrichissement IA.
#     """
#     nom_auteur = f"{cours.enseignant.utilisateur.first_name} {cours.enseignant.utilisateur.last_name}".strip()
#     if not nom_auteur:
#         nom_auteur = cours.enseignant.utilisateur.username

#     photo_auteur = "/placeholder-user.jpg"
#     if hasattr(cours.enseignant.utilisateur, 'photo_url') and cours.enseignant.utilisateur.photo_url:
#         photo_auteur = cours.enseignant.utilisateur.photo_url.url

#     structure = {
#         "id": str(cours.id),
#         "title": cours.titre,
#         "category": cours.matiere.titre if hasattr(cours, 'matiere') and cours.matiere else "Non catégorisé",
#         "image": cours.image.url if hasattr(cours, 'image') and cours.image else "/placeholder-course.png",
#         "views": 0,
#         "likes": 0,
#         "downloads": 0,
#         "author": {
#             "name": nom_auteur,
#             "image": photo_auteur
#         },
#         "introduction": cours.description or "Introduction en attente de génération IA.",
#         "conclusion": "Conclusion en attente de génération IA.",
#         "learningObjectives": [],
#         "sections": []
#     }

#     # Parcours des Parties (devient "sections" dans XCCM)
#     for partie in cours.parties.all().order_by('numero'):
#         section_data = {
#             "title": partie.titre,
#             "introduction": "Texte d'introduction à la section (En attente IA).",
#             "chapters": [],
#             "exercise": None
#         }

#         # Parcours des Chapitres (devient "chapters" dans XCCM)
#         for chapitre in partie.chapitres.all().order_by('numero'):
#             chapter_data = {
#                 "title": chapitre.titre,
#                 "introduction": "Texte d'introduction au Chapitre (En attente IA).",
#                 "paragraphs": [],
#                 "exercise": None
#             }

#             # Parcours des Sections (devient "paragraphs" dans XCCM)
#             for section in chapitre.sections.all().order_by('numero'):
#                 content_html = ""
                
#                 # Rétrocompatibilité et concaténation des granules
#                 if hasattr(section, 'sous_sections') and section.sous_sections.exists():
#                     for sous_section in section.sous_sections.all().order_by('numero'):
#                         for granule in sous_section.granules.all().order_by('ordre'):
#                             gc = get_granule_content(granule.mongo_contenu_id)
#                             if gc and "html" in gc:
#                                 content_html += gc["html"] + "\n"
#                 elif hasattr(section, 'granules'):
#                     for granule in section.granules.all().order_by('ordre'):
#                         gc = get_granule_content(granule.mongo_contenu_id)
#                         if gc and "html" in gc:
#                             content_html += gc["html"] + "\n"

#                 paragraph_data = {
#                     "title": section.titre,
#                     "introduction": "Texte d'introduction au paragraphe (En attente IA).",
#                     "content": content_html.strip() or "Contenu en cours de traitement.",
#                     "notions": [],
#                     "exercise": None
#                 }
                
#                 chapter_data["paragraphs"].append(paragraph_data)

#             section_data["chapters"].append(chapter_data)

#         structure["sections"].append(section_data)

#     return structure


# def export_cours_to_json_file(cours, output_path):
#     """
#     Exporte un cours complet au format XCCM dans un fichier JSON.
#     """
#     structure = get_xccm_cours_structure(cours)
    
#     with open(output_path, 'w', encoding='utf-8') as f:
#         json.dump(structure, f, ensure_ascii=False, indent=2)
    
#     print(f"✅ Cours formaté pour XCCM exporté vers {output_path}")


# def search_in_granules(query, fichier_source=None):
#     """
#     Recherche dans les contenus des granules MongoDB.
#     """
#     try:
#         mongo_db = get_mongo_db()
        
#         cleaned_query = re.sub(r'[^\w\s]', ' ', query)
#         keywords = [re.escape(w) for w in cleaned_query.split() if w.strip()]
        
#         if not keywords:
#             keywords = [re.escape(query)]

#         keyword_conditions = []
#         for word in keywords:
#             keyword_conditions.append({
#                 "$or": [
#                     {"content": {"$regex": word, "$options": "i"}},
#                     {"html": {"$regex": word, "$options": "i"}}
#                 ]
#             })

#         filter_query = {
#             "$and": keyword_conditions
#         }
        
#         if fichier_source:
#              filter_query["$and"].append({"fichier_source_id": str(fichier_source.id)})
        
#         results = list(mongo_db['granules'].find(filter_query).limit(50))
        
#         for doc in results:
#             doc['_id'] = str(doc['_id'])
        
#         return results
        
#     except Exception as e:
#         print(f"❌ Erreur search_in_granules: {e}")
#         return []


# def search_in_granules_filtered(query, fichier_source_ids):
#     """
#     Recherche dans les granules MongoDB avec filtrage par fichiers sources.
#     Mode "Mots-clés" : Tous les mots doivent être présents (AND).
#     """
#     try:
#         mongo_db = get_mongo_db()
        
#         cleaned_query = re.sub(r'[^\w\s]', ' ', query)
#         keywords = [re.escape(w) for w in cleaned_query.split() if w.strip()]
        
#         if not keywords:
#             keywords = [re.escape(query)]

#         keyword_conditions = []
#         for word in keywords:
#             keyword_conditions.append({
#                 "$or": [
#                     {"content": {"$regex": word, "$options": "i"}},
#                     {"html": {"$regex": word, "$options": "i"}},
#                     {"titre": {"$regex": word, "$options": "i"}}
#                 ]
#             })

#         filter_query = {
#             "$and": [
#                 {"$and": keyword_conditions},
#                 {
#                     "fichier_source_id": {"$in": [str(fid) for fid in fichier_source_ids]}
#                 }
#             ]
#         }
        
#         results = list(mongo_db['granules'].find(filter_query).limit(100))
        
#         for doc in results:
#             doc['_id'] = str(doc['_id'])
        
#         return results
        
#     except Exception as e:
#         print(f"❌ Erreur search_in_granules_filtered: {e}")
#         return []


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
            "code": cours.matiere.code if cours.matiere else "N/A",
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

                    for granule in sous_section.granules.all():
                        granule_content = get_granule_content(granule.mongo_contenu_id)

                        granule_data = {
                            "id": str(granule.id),
                            "titre": granule.titre,
                            "type": granule.type_contenu,
                            "ordre": granule.ordre,
                            "contenu": granule_content
                        }
                        sous_section_data["granules"].append(granule_data)

                    section_data["sous_sections"].append(sous_section_data)

                chapitre_data["sections"].append(section_data)

            partie_data["chapitres"].append(chapitre_data)

        structure["parties"].append(partie_data)

    return structure


# def get_statistics():
#     """
#     Retourne des statistiques sur les données MongoDB.
#     """
#     try:
#         mongo_db = get_mongo_db()
#         stats = {
#             "fichiers_uploades": mongo_db['fichiers_uploades'].count_documents({}),
#             "granules": mongo_db['granules'].count_documents({}),
#             "database_name": mongo_db.name
#         }
#         return stats
#     except Exception as e:
#         print(f"❌ Erreur get_statistics: {e}")
#         return {}


















# # xcsm/json_utils.py - Utilitaires pour manipuler les structures JSON
# import json
# from bson.objectid import ObjectId
# from .utils import get_mongo_db


# def get_fichier_json_structure(fichier_source_id):
#     """
#     Récupère la structure JSON complète d'un fichier depuis MongoDB.
    
#     Args:
#         fichier_source_id (str/UUID): ID du FichierSource
        
#     Returns:
#         dict: Structure JSON complète ou None
#     """
#     try:
#         mongo_db = get_mongo_db()
#         doc = mongo_db['fichiers_uploades'].find_one({
#             "fichier_source_id": str(fichier_source_id)
#         })
        
#         if doc:
#             # Suppression de l'_id MongoDB pour la sérialisation
#             doc.pop('_id', None)
#             return doc
        
#         print(f"⚠️ get_fichier_json_structure: Aucune structure trouvée pour {fichier_source_id}")
#         return None
        
#     except Exception as e:
#         print(f"❌ Erreur get_fichier_json_structure: {e}")
#         return None


# def get_granule_content(mongo_contenu_id):
#     """
#     Récupère le contenu JSON d'un granule depuis MongoDB.
    
#     Args:
#         mongo_contenu_id (str): ID MongoDB du granule
        
#     Returns:
#         dict: Contenu du granule ou None
#     """
#     try:
#         mongo_db = get_mongo_db()
#         doc = mongo_db['granules'].find_one({
#             "_id": ObjectId(mongo_contenu_id)
#         })
        
#         if doc:
#             doc['_id'] = str(doc['_id'])  # Conversion pour JSON
#             return doc
#         return None
        
#     except Exception as e:
#         print(f"❌ Erreur get_granule_content: {e}")
#         return None


# def get_cours_complete_structure(cours):
#     """
#     Reconstruit la structure JSON complète d'un cours avec tous ses granules.
#     Utile pour l'export ou l'affichage frontend.
    
#     Args:
#         cours (Cours): Instance du modèle Cours
        
#     Returns:
#         dict: Structure hiérarchique complète
#     """
#     structure = {
#         "cours": {
#             "id": str(cours.id),
#             "code": cours.matiere.code if cours.matiere else "N/A",
#             "titre": cours.titre,
#             "description": cours.description,
#             "enseignant": cours.enseignant.utilisateur.username
#         },
#         "parties": []
#     }
    
#     for partie in cours.parties.all():
#         partie_data = {
#             "id": str(partie.id),
#             "titre": partie.titre,
#             "numero": partie.numero,
#             "chapitres": []
#         }
        
#         for chapitre in partie.chapitres.all():
#             chapitre_data = {
#                 "id": str(chapitre.id),
#                 "titre": chapitre.titre,
#                 "numero": chapitre.numero,
#                 "sections": []
#             }
            
#             for section in chapitre.sections.all():
#                 section_data = {
#                     "id": str(section.id),
#                     "titre": section.titre,
#                     "numero": section.numero,
#                     "sous_sections": []
#                 }
                
#                 for sous_section in section.sous_sections.all():
#                     sous_section_data = {
#                         "id": str(sous_section.id),
#                         "titre": sous_section.titre,
#                         "numero": sous_section.numero,
#                         "granules": []
#                     }
                    
#                     # Récupération des granules avec leur contenu MongoDB
#                     for granule in sous_section.granules.all():
#                         granule_content = get_granule_content(granule.mongo_contenu_id)
                        
#                         granule_data = {
#                             "id": str(granule.id),
#                             "titre": granule.titre,
#                             "type": granule.type_contenu,
#                             "ordre": granule.ordre,
#                             "contenu": granule_content  # Contenu JSON depuis MongoDB
#                         }
#                         sous_section_data["granules"].append(granule_data)
                    
#                     section_data["sous_sections"].append(sous_section_data)
                
#                 chapitre_data["sections"].append(section_data)
            
#             partie_data["chapitres"].append(chapitre_data)
        
#         structure["parties"].append(partie_data)
    
#     return structure


# def export_cours_to_json_file(cours, output_path):
#     """
#     Exporte un cours complet en fichier JSON.
    
#     Args:
#         cours (Cours): Instance du cours à exporter
#         output_path (str): Chemin du fichier de sortie
#     """
#     structure = get_cours_complete_structure(cours)
    
#     with open(output_path, 'w', encoding='utf-8') as f:
#         json.dump(structure, f, ensure_ascii=False, indent=2)
    
#     print(f"✅ Cours exporté vers {output_path}")


# def search_in_granules(query, fichier_source=None):
#     """
#     Recherche dans les contenus des granules MongoDB.
    
#     Args:
#         query (str): Terme de recherche
#         fichier_source (FichierSource, optional): Filtrer par fichier source
        
#     Returns:
#         list: Liste des granules correspondants
#     """
#     try:
#         mongo_db = get_mongo_db()
#         import re

#         # 1. Nettoyage et découpage en mots-clés
#         cleaned_query = re.sub(r'[^\w\s]', ' ', query)
#         keywords = [re.escape(w) for w in cleaned_query.split() if w.strip()]
        
#         if not keywords:
#             keywords = [re.escape(query)]

#         # 2. Construction des conditions pour CHAQUE mot-clé
#         keyword_conditions = []
#         for word in keywords:
#             keyword_conditions.append({
#                 "$or": [
#                     {"content": {"$regex": word, "$options": "i"}},
#                     {"html": {"$regex": word, "$options": "i"}}
#                 ]
#             })

#         # 3. Requête finale : (Mot1 AND Mot2 AND ...)
#         filter_query = {
#             "$and": keyword_conditions
#         }
        
#         if fichier_source:
#              filter_query["$and"].append({"fichier_source_id": str(fichier_source.id)})
        
#         results = list(mongo_db['granules'].find(filter_query).limit(50))
        
#         # Conversion des ObjectId en string
#         for doc in results:
#             doc['_id'] = str(doc['_id'])
        
#         return results
        
#     except Exception as e:
#         print(f"❌ Erreur search_in_granules: {e}")
#         return []


#     except Exception as e:
#         print(f"❌ Erreur search_in_granules_filtered: {e}")
#         return []

# def search_in_granules_filtered(query, fichier_source_ids):
#     """
#     Recherche dans les granules MongoDB avec filtrage par fichiers sources.
#     Mode "Mots-clés" : Tous les mots doivent être présents (AND), peu importe l'ordre ou les séparateurs.
#     """
#     try:
#         mongo_db = get_mongo_db()
#         import re
        
#         # 1. Nettoyage et découpage en mots-clés
#         # On remplace tout ce qui n'est pas alphanumérique par des espaces
#         # Cela permet de traiter "Nom - Prénom" comme ["Nom", "Prénom"]
#         cleaned_query = re.sub(r'[^\w\s]', ' ', query)
#         keywords = [re.escape(w) for w in cleaned_query.split() if w.strip()]
        
#         if not keywords:
#             # Si le nettoyage supprime tout (ex: que des symboles), on garde la requête brute échappée
#             keywords = [re.escape(query)]

#         # 2. Construction des conditions pour CHAQUE mot-clé
#         # Chaque mot doit être présent dans (content OU html OU titre)
#         keyword_conditions = []
#         for word in keywords:
#             keyword_conditions.append({
#                 "$or": [
#                     {"content": {"$regex": word, "$options": "i"}},
#                     {"html": {"$regex": word, "$options": "i"}},
#                     {"titre": {"$regex": word, "$options": "i"}}
#                 ]
#             })

#         # 3. Requête finale : (Mot1 AND Mot2 AND ...) AND (Fichier autorisé)
#         filter_query = {
#             "$and": [
#                 {"$and": keyword_conditions},
#                 {
#                     "fichier_source_id": {"$in": [str(fid) for fid in fichier_source_ids]}
#                 }
#             ]
#         }
        
#         results = list(mongo_db['granules'].find(filter_query).limit(100))
        
#         # Conversion des ObjectId en string
#         for doc in results:
#             doc['_id'] = str(doc['_id'])
        
#         return results
        
#     except Exception as e:
#         print(f"❌ Erreur search_in_granules_filtered: {e}")
#         return []



# def get_statistics():
#     """
#     Retourne des statistiques sur les données MongoDB.
    
#     Returns:
#         dict: Statistiques (nb documents, taille, etc.)
#     """
#     try:
#         mongo_db = get_mongo_db()
        
#         stats = {
#             "fichiers_uploades": mongo_db['fichiers_uploades'].count_documents({}),
#             "granules": mongo_db['granules'].count_documents({}),
#             "database_name": mongo_db.name
#         }
        
#         return stats
        
#     except Exception as e:
#         print(f"❌ Erreur get_statistics: {e}")
#         return {}