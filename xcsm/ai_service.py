# Author: Dilane PAFE
# Fichier: xcsm/ai_service.py - Services d'Intelligence Artificielle et Machine Learning

import json
import logging
import os

logger = logging.getLogger(__name__)


def _load_genai():
    """Import différé pour ne pas bloquer le démarrage Django si le paquet manque."""
    try:
        import google.generativeai as genai
        return genai
    except ImportError:
        logger.error(
            "Paquet google-generativeai absent. "
            "Installez-le dans l'image Docker (requirements.txt) puis rebuild."
        )
        return None


# ==============================================================================
# CONFIGURATION GEMINI
# ==============================================================================
def setup_gemini():
    genai = _load_genai()
    if genai is None:
        return None
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("⚠️ GEMINI_API_KEY manquante dans l'environnement !")
        return None
    genai.configure(api_key=api_key)
    # On utilise gemini-2.5-flash pour sa rapidité et son grand contexte
    return genai.GenerativeModel('gemini-2.5-flash')


# ==============================================================================
# MODULE 1: ASSISTANT IA CONVERSATIONNEL (CHAT)
# ==============================================================================

def chat_with_context_stream(cours, message_utilisateur, historique_chat=None):
    """
    Génère une réponse en streaming via Gemini, en se basant sur le contenu du cours.
    """
    # 1. Récupération du contexte (Le contenu du cours)
    from .json_utils import get_xccm_cours_structure
    structure_cours = get_xccm_cours_structure(cours)

    try:
        notions = (
            structure_cours
            .get('sections', [{}])[0]
            .get('chapters', [{}])[0]
            .get('paragraphs', [{}])[0]
            .get('notions', [])[:10]
        )
    except (IndexError, AttributeError):
        notions = []

    contexte_pedagogique = f"""
    Tu es l'assistant pédagogique IA de la plateforme XCSM.
    Tu dois aider l'étudiant à comprendre le cours intitulé "{structure_cours.get('title')}".
    Voici les informations clés de ce cours :
    - Introduction : {structure_cours.get('introduction')}
    - Objectifs : {', '.join(structure_cours.get('learningObjectives', []))}
    - Mots-clés : {', '.join(notions)}

    Réponds de manière claire, pédagogique et encourageante.
    """

    model = setup_gemini()
    if not model:
        yield "Erreur: Aucun assistant IA n'est configuré (Clés API manquantes)."
        return

    try:
        # 2. Appel à Gemini en mode Streaming
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
    et l'enrichit sémantiquement via Gemini.
    """
    texte_echantillon = json.dumps(json_structure, ensure_ascii=False)[:10000]

    prompt = f"""Tu es un expert pédagogique IA. Voici un extrait d'un document de cours sous format JSON brut.
Ta mission est d'analyser ce contenu et de générer des métadonnées pédagogiques de haute qualité pour améliorer l'affichage FrontEnd.

Génère UNIQUEMENT un objet JSON valide avec cette structure stricte (n'ajoute aucun texte avant ou après, pas de bloc de code markdown) :
{{
    "ia_introduction": "Un résumé pédagogique, clair et engageant de ce cours (environ 3 à 4 phrases).",
    "ia_conclusion": "Une brève conclusion ou synthèse de ce qui est censé être retenu.",
    "ia_objectifs": ["Objectif d'apprentissage 1", "Objectif d'apprentissage 2", "Objectif d'apprentissage 3"],
    "ia_mots_cles": ["notion_1", "notion_2", "notion_3", "notion_4"]
}}

Extrait du cours :
{texte_echantillon}
"""

    model = setup_gemini()
    if not model:
        logger.warning("⚠️ Aucune clé API d'IA configurée. L'orchestration sémantique est ignorée.")
        return json_structure

    try:
        logger.info("🧠 Chef d'orchestre: Analyse via Gemini...")
        response = model.generate_content(prompt)
        text_response = response.text
        
        # Nettoyage si Gemini ajoute des balises Markdown (ex: ```json ... ```)
        if text_response.startswith("```json"):
            text_response = text_response[7:-3]
        elif text_response.startswith("```"):
            text_response = text_response[3:-3]
            
        metadonnees_ia = json.loads(text_response.strip())
        
        # INJECTION NON-DESTRUCTIVE
        json_structure["metadata_ia"] = metadonnees_ia
        
        logger.info("✅ Orchestration sémantique terminée avec succès via Gemini !")
        return json_structure

    except Exception as e:
        logger.error(f"❌ Erreur Chef d'Orchestre IA (Gemini) : {e}")
        return json_structure


# ==============================================================================
# MODULE 3: GÉNÉRATION D'EXERCICES
# ==============================================================================

def generate_exercises_from_granule(granule_content, type_question='QCM', count=3):
    """
    Génère des exercices à partir du contenu d'un granule.
    Utilise OpenAI si la clé est disponible, sinon un générateur mock.
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
            response_format={"type": "json_object"}
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
                {"texte": "Une définition erronée", "est_correcte": False, "feedback": "Revoyez le cours."},
                {"texte": "Un concept hors sujet", "est_correcte": False, "feedback": "Ceci n'est pas lié au texte."}
            ]
        })
    return mock_questions
