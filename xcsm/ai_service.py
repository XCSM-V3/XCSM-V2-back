# Author: Dilane PAFE
# Fichier: xcsm/ai_service.py - Services d'Intelligence Artificielle et Machine Learning

import json
import logging
import os

# IMPORT DE GOOGLE GENERATIVE AI (Gemini)
import google.generativeai as genai


logger = logging.getLogger(__name__)


# ==============================================================================
# CONFIGURATION GEMINI
# ==============================================================================
def setup_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("⚠️ GEMINI_API_KEY manquante dans l'environnement !")
        return None
    genai.configure(api_key=api_key)
    # On utilise gemini-1.5-flash pour sa rapidité et son grand contexte
    return genai.GenerativeModel('gemini-1.5-flash')

# ==============================================================================
# MODULE 1: ASSISTANT IA CONVERSATIONNEL (CHAT)
# ==============================================================================

def chat_with_context_stream(cours, message_utilisateur, historique_chat=None):
    """
    Génère une réponse en streaming via Gemini, en se basant sur le contenu du cours.
    """
    model = setup_gemini()
    if not model:
        yield "Erreur: L'assistant IA n'est pas configuré (Clé API manquante)."
        return

    # 1. Récupération du contexte (Le contenu du cours)
    # Pour ne pas surcharger, on récupère l'introduction et les métadonnées de l'IA (notre Chef d'Orchestre !)
    from .json_utils import get_xccm_cours_structure
    structure_cours = get_xccm_cours_structure(cours)
    
    contexte_pedagogique = f"""
    Tu es l'assistant pédagogique IA de la plateforme XCSM. 
    Tu dois aider l'étudiant à comprendre le cours intitulé "{structure_cours.get('title')}".
    Voici les informations clés de ce cours :
    - Introduction : {structure_cours.get('introduction')}
    - Objectifs : {', '.join(structure_cours.get('learningObjectives', []))}
    - Mots-clés : {', '.join(structure_cours.get('sections', [])[0].get('chapters', [])[0].get('paragraphs', [])[0].get('notions', [])[:10])} # On prend quelques mots-clés du début
    
    Réponds de manière claire, pédagogique et encourageante.
    """

    # 2. Construction de l'historique pour Gemini
    messages = [{"role": "system", "parts": [contexte_pedagogique]}] # Le contexte initial
    
    if historique_chat:
        for msg in historique_chat[-5:]: # On garde les 5 derniers messages pour le contexte
            role = "user" if msg['role'] == "user" else "model"
            messages.append({"role": role, "parts": [msg['content']]})
            
    # Ajout du message actuel
    messages.append({"role": "user", "parts": [message_utilisateur]})

    try:
        # 3. Appel à Gemini en mode Streaming
        # Note: L'API Gemini Python gère l'historique via model.start_chat()
        chat = model.start_chat(history=[])
        
        # Injection discrète du contexte système dans le premier message
        full_message = f"CONTEXTE CACHÉ: {contexte_pedagogique}\n\nQUESTION DE L'ÉTUDIANT: {message_utilisateur}"
        
        response = chat.send_message(full_message, stream=True)
        
        for chunk in response:
            if chunk.text:
                yield chunk.text

    except Exception as e:
        logger.error(f"❌ Erreur Gemini Chat : {e}")
        yield "Désolé, une erreur est survenue lors de la communication avec l'assistant."




# ==============================================================================
# MODULE 2: LE CHEF D'ORCHESTRE SÉMANTIQUE
# ==============================================================================

def apply_semantic_orchestrator(json_structure):
    """
    Intercepte le JSON généré par le moteur de parsing heuristique,
    et l'enrichit sémantiquement via l'IA SANS modifier la structure textuelle originale.
    Ces données amélioreront le rendu visuel et structurel côté FrontEnd.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("⚠️ Clé API non trouvée. L'orchestration sémantique IA est ignorée.")
        return json_structure

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        logger.info("🧠 Chef d'orchestre: Analyse et enrichissement du document...")
        
        # Extraction d'un échantillon pour éviter de dépasser la limite de tokens
        texte_echantillon = json.dumps(json_structure, ensure_ascii=False)[:6000]
        
        prompt = f"""
        Tu es un expert pédagogique IA. Voici un extrait d'un document de cours sous format JSON brut.
        Ta mission est d'analyser ce contenu et de générer des métadonnées pédagogiques de haute qualité 
        pour améliorer l'affichage FrontEnd.
        
        Génère UNIQUEMENT un objet JSON valide avec cette structure stricte :
        {{
            "ia_introduction": "Un résumé pédagogique, clair et engageant de ce cours (environ 3 à 4 phrases).",
            "ia_conclusion": "Une brève conclusion ou synthèse de ce qui est censé être retenu.",
            "ia_objectifs": ["Objectif d'apprentissage 1", "Objectif d'apprentissage 2", "Objectif d'apprentissage 3"],
            "ia_mots_cles": ["notion_1", "notion_2", "notion_3", "notion_4"]
        }}
        
        Extrait du cours :
        {texte_echantillon}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        metadonnees_ia = json.loads(response.choices[0].message.content)
        
        # INJECTION NON-DESTRUCTIVE : On ajoute les données IA dans un bloc dédié
        json_structure["metadata_ia"] = metadonnees_ia
        
        logger.info("✅ Orchestration sémantique terminée avec succès !")
        return json_structure

    except Exception as e:
        logger.error(f"❌ Erreur Chef d'Orchestre IA : {e}")
        return json_structure


# ==============================================================================
# LOGIQUE EXISTANTE (Génération d'exercices)
# ==============================================================================

def generate_exercises_from_granule(granule_content, type_question='QCM', count=3):
    """
    Génère des exercices à partir du contenu d'un granule.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    
    if api_key:
        return _generate_via_openai(granule_content, type_question, count, api_key)
    else:
        return _generate_mock(granule_content, type_question, count)

def _generate_via_openai(content, type_question, count, api_key):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        prompt = f"""
        En tant qu'expert pédagogique, génère {count} questions de type {type_question} 
        basées uniquement sur le contenu pédagogique suivant :
        
        ---
        {content}
        ---
        
        Format de sortie attendu (JSON pur) :
        {{
          "questions": [
              {{
                "enonce": "La question...",
                "reponses": [
                    {{"texte": "Option A", "est_correcte": true, "feedback": "Explication..."}},
                    {{"texte": "Option B", "est_correcte": false, "feedback": "Explication..."}}
                ]
              }}
          ]
        }}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        
        result = json.loads(response.choices[0].message.content)
        if isinstance(result, dict) and "questions" in result:
            return result["questions"]
        return result
        
    except Exception as e:
        logger.error(f"Erreur OpenAI : {e}")
        return _generate_mock(content, type_question, count)

def _generate_mock(content, type_question, count):
    """
    Générateur de secours (Mock) pour le développement local.
    """
    import random
    
    words = [w for w in content.replace('.', ' ').split() if len(w) > 5]
    keyword = random.choice(words) if words else "ce concept"
    
    mock_questions = []
    for i in range(count):
        mock_questions.append({
            "enonce": f"Question {i+1} sur {keyword} : Quelle est la définition exacte ?",
            "reponses": [
                {"texte": f"La définition correcte de {keyword}", "est_correcte": True, "feedback": "Bravo !"},
                {"texte": "Une définition erronée", "est_correcte": False, "feedback": "Revoyez le cours."}
            ]
        })
    return mock_questions



















# # Author: Dilane PAFE
# # Fichier: xcsm/ai_service.py - Services d'Intelligence Artificielle et Machine Learning

# import json
# import logging
# import os

# logger = logging.getLogger(__name__)

# def generate_exercises_from_granule(granule_content, type_question='QCM', count=3):
#     """
#     Génère des exercices à partir du contenu d'un granule.
#     """
#     api_key = os.environ.get("OPENAI_API_KEY")
#     if api_key:
#         return _generate_via_openai_exercises(granule_content, type_question, count, api_key)
#     else:
#         return _generate_mock_exercises(granule_content, type_question, count)

# def build_semantic_structure_from_text(raw_text_preview):
#     """
#     MODULE 2 - Segmentation Intelligente ML
#     Analyse le texte brut du document et détecte sémantiquement la hiérarchie.
#     L'IA ne modifie pas le texte, elle indique juste comment le découper.
#     """
#     api_key = os.environ.get("OPENAI_API_KEY")
    
#     if not api_key:
#         logger.warning("⚠️ Clé API non trouvée, utilisation de la segmentation de secours (Règles basiques).")
#         return _generate_mock_semantic_structure()

#     try:
#         from openai import OpenAI
#         client = OpenAI(api_key=api_key)
        
#         prompt = f"""
#         Tu es un expert pédagogique IA. Analyse le texte brut suivant extrait d'un support de cours.
#         Ta mission est de détecter la structure logique du cours et de la hiérarchiser en Partie -> Chapitre -> Section.
        
#         Règles strictes :
#         1. Ne modifie pas le texte original.
#         2. Déduis des titres pertinents si le texte manque de clarté.
#         3. Identifie des 'notions_cles' (mots-clés) pour chaque section.
#         4. Génère une brève introduction pour chaque niveau.
        
#         Format JSON attendu :
#         {{
#             "titre_cours": "Titre global",
#             "introduction": "Intro globale",
#             "parties": [
#                 {{
#                     "titre": "Titre Partie",
#                     "introduction": "Intro partie",
#                     "chapitres": [
#                         {{
#                             "titre": "Titre Chapitre",
#                             "introduction": "Intro chapitre",
#                             "sections": [
#                                 {{
#                                     "titre": "Titre Section",
#                                     "notions_cles": ["notion1", "notion2"],
#                                     "mots_debut": "Les 5 premiers mots du début de cette section dans le texte brut",
#                                     "mots_fin": "Les 5 derniers mots de la fin de cette section dans le texte brut"
#                                 }}
#                             ]
#                         }}
#                     ]
#                 }}
#             ]
#         }}
        
#         Texte à analyser :
#         {raw_text_preview[:15000]} # Limite de tokens pour l'analyse structurelle
#         """
        
#         response = client.chat.completions.create(
#             model="gpt-4o",
#             messages=[{"role": "user", "content": prompt}],
#             response_format={ "type": "json_object" }
#         )
        
#         return json.loads(response.choices[0].message.content)
        
#     except Exception as e:
#         logger.error(f"❌ Erreur IA Segmentation Sémantique : {e}")
#         return _generate_mock_semantic_structure()

# def _generate_mock_semantic_structure():
#     """
#     Structure de fallback si l'API IA est indisponible.
#     """
#     return {
#         "titre_cours": "Cours Généré (Mode Dégradé)",
#         "introduction": "Introduction non disponible.",
#         "parties": [
#             {
#                 "titre": "Partie 1: Généralités",
#                 "introduction": "",
#                 "chapitres": [
#                     {
#                         "titre": "Chapitre 1: Introduction",
#                         "introduction": "",
#                         "sections": [
#                             {
#                                 "titre": "Section 1: Concepts de base",
#                                 "notions_cles": ["base", "concept"],
#                                 "mots_debut": "",
#                                 "mots_fin": ""
#                             }
#                         ]
#                     }
#                 ]
#             }
#         ]
#     }

# def _generate_via_openai_exercises(content, type_question, count, api_key):
#     # Implémentation conservée de votre fichier initial
#     pass

# def _generate_mock_exercises(content, type_question, count):
#     # Implémentation conservée de votre fichier initial
#     pass



























# # xcsm/ai_service.py
# import json
# import logging
# import os

# logger = logging.getLogger(__name__)

# def generate_exercises_from_granule(granule_content, type_question='QCM', count=3):
#     """
#     Génère des exercices à partir du contenu d'un granule.
#     Pour l'instant, implémente un Mock ou utilise OpenAI si la clé est présente.
#     """
    
#     api_key = os.environ.get("OPENAI_API_KEY")
    
#     if api_key:
#         return _generate_via_openai(granule_content, type_question, count, api_key)
#     else:
#         return _generate_mock(granule_content, type_question, count)

# def _generate_via_openai(content, type_question, count, api_key):
#     """
#     Appel réel à OpenAI (GPT-4o recommendé pour la structuration JSON)
#     """
#     try:
#         from openai import OpenAI
#         client = OpenAI(api_key=api_key)
        
#         prompt = f"""
#         En tant qu'expert pédagogique, génère {count} questions de type {type_question} 
#         basées uniquement sur le contenu pédagogique suivant :
        
#         ---
#         {content}
#         ---
        
#         Format de sortie attendu (JSON pur) :
#         [
#           {{
#             "enonce": "La question...",
#             "reponses": [
#               {{"texte": "Réponse correcte", "est_correcte": true, "feedback": "Pourquoi c'est juste"}},
#               {{"texte": "Réponse fausse 1", "est_correcte": false, "feedback": "Pourquoi c'est faux"}},
#               {{"texte": "Réponse fausse 2", "est_correcte": false, "feedback": "Pourquoi c'est faux"}}
#             ]
#           }}
#         ]
#         """
        
#         response = client.chat.completions.create(
#             model="gpt-4o",
#             messages=[{"role": "user", "content": prompt}],
#             response_format={ "type": "json_object" }
#         )
        
#         result = json.loads(response.choices[0].message.content)
#         # S'assurer que c'est une liste
#         if isinstance(result, dict) and "questions" in result:
#             return result["questions"]
#         return result
        
#     except Exception as e:
#         logger.error(f"Erreur OpenAI : {e}")
#         return _generate_mock(content, type_question, count)

# def _generate_mock(content, type_question, count):
#     """
#     Générateur de secours (Mock) pour le développement.
#     """
#     import random
    
#     # Extraction de quelques mots clés pour faire "vrai"
#     words = [w for w in content.replace('.', ' ').split() if len(w) > 5]
#     keyword = random.choice(words) if words else "ce concept"
    
#     mock_questions = []
#     for i in range(count):
#         mock_questions.append({
#             "enonce": f"Question {i+1} sur {keyword} : Quelle est la définition exacte ?",
#             "reponses": [
#                 {"texte": f"La définition correcte de {keyword}", "est_correcte": True, "feedback": "Bravo !"},
#                 {"texte": "Une définition erronée", "est_correcte": False, "feedback": "Non, c'est l'inverse."},
#                 {"texte": "Un concept hors sujet", "est_correcte": False, "feedback": "Ceci n'est pas lié au texte."}
#             ]
#         })
    
#     return mock_questions
