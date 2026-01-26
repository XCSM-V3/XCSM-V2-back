# xcsm/ai_service.py
import json
import logging
import os

logger = logging.getLogger(__name__)

def generate_exercises_from_granule(granule_content, type_question='QCM', count=3):
    """
    Génère des exercices à partir du contenu d'un granule.
    Pour l'instant, implémente un Mock ou utilise OpenAI si la clé est présente.
    """
    
    api_key = os.environ.get("OPENAI_API_KEY")
    
    if api_key:
        return _generate_via_openai(granule_content, type_question, count, api_key)
    else:
        return _generate_mock(granule_content, type_question, count)

def _generate_via_openai(content, type_question, count, api_key):
    """
    Appel réel à OpenAI (GPT-4o recommendé pour la structuration JSON)
    """
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
        [
          {{
            "enonce": "La question...",
            "reponses": [
              {{"texte": "Réponse correcte", "est_correcte": true, "feedback": "Pourquoi c'est juste"}},
              {{"texte": "Réponse fausse 1", "est_correcte": false, "feedback": "Pourquoi c'est faux"}},
              {{"texte": "Réponse fausse 2", "est_correcte": false, "feedback": "Pourquoi c'est faux"}}
            ]
          }}
        ]
        """
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        
        result = json.loads(response.choices[0].message.content)
        # S'assurer que c'est une liste
        if isinstance(result, dict) and "questions" in result:
            return result["questions"]
        return result
        
    except Exception as e:
        logger.error(f"Erreur OpenAI : {e}")
        return _generate_mock(content, type_question, count)

def _generate_mock(content, type_question, count):
    """
    Générateur de secours (Mock) pour le développement.
    """
    import random
    
    # Extraction de quelques mots clés pour faire "vrai"
    words = [w for w in content.replace('.', ' ').split() if len(w) > 5]
    keyword = random.choice(words) if words else "ce concept"
    
    mock_questions = []
    for i in range(count):
        mock_questions.append({
            "enonce": f"Question {i+1} sur {keyword} : Quelle est la définition exacte ?",
            "reponses": [
                {"texte": f"La définition correcte de {keyword}", "est_correcte": True, "feedback": "Bravo !"},
                {"texte": "Une définition erronée", "est_correcte": False, "feedback": "Non, c'est l'inverse."},
                {"texte": "Un concept hors sujet", "est_correcte": False, "feedback": "Ceci n'est pas lié au texte."}
            ]
        })
    
    return mock_questions
