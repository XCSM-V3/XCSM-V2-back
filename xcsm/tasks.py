"""
Celery Tasks pour le traitement asynchrone des documents.

Architecture:
- Frontend → API Django → Broker Redis → Worker Celery → MongoDB + PostgreSQL

Tâches principales:
1. process_document_async: Orchestrateur principal
2. extract_text_from_document_task: Extraction de texte (PDF/DOCX/TXT)
3. generate_granules_task: Génération de la hiérarchie et des granules
4. extract_images_from_pdf_task: Extraction d'images (non-bloquant)
"""

from celery import shared_task
from celery.result import allow_join_result
from .models import FichierSource
from .processing import (
    extract_structure_from_pdf,
    extract_structure_from_docx,
    extract_structure_from_txt,
    split_and_create_granules,
    extract_images_from_pdf
)
from .tracking_utils import ProcessingLogger, log_user_activity
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ==============================================================================
# TÂCHE 1: ORCHESTRATEUR PRINCIPAL
# ==============================================================================

@shared_task(bind=True, max_retries=3)
def process_document_task(self, fichier_id):
    """
    Tâche principale pour traiter un document uploadé de manière asynchrone.
    
    Workflow:
    1. Récupération du fichier source
    2. Extraction d'images (PDF uniquement, non-bloquant)
    3. Extraction de texte et structure
    4. Génération de granules et hiérarchie
    5. Mise à jour du statut
    
    Args:
        fichier_id: UUID du FichierSource à traiter
        
    Returns:
        dict: {"success": bool, "message": str, "cours_id": int}
    """
    try:
        # ÉTAPE 1: Récupération du fichier
        logger.info(f"🚀 [Task {self.request.id}] Démarrage traitement fichier {fichier_id}")
        
        fichier = FichierSource.objects.get(id=fichier_id)
        
        # Utilisation du ProcessingLogger pour tracking complet
        with ProcessingLogger(fichier, 'COMPLETE', self.request.id) as proc_log:
            fichier.statut_traitement = 'EN_COURS'
            fichier.save()
            
            # Détermination du type de fichier
            file_path = fichier.fichier_original.path
            ext = file_path.split('.')[-1].lower()

            logger.info(f"📄 [Task {self.request.id}] Fichier: {fichier.titre} (Type: {ext})")
            
            # ÉTAPE 2: Extraction d'images (PDF uniquement, non-bloquant)
            if ext == 'pdf':
                logger.info(f"🖼️ [Task {self.request.id}] Lancement extraction d'images...")
                try:
                    extract_images_from_pdf_task.delay(fichier_id)
                except Exception as img_error:
                    logger.warning(f"⚠️ [Task {self.request.id}] Échec extraction images (non-bloquant): {img_error}")

            # ÉTAPE 3: Extraction de texte
            logger.info(f"📝 [Task {self.request.id}] Extraction de texte...")
            extraction_result = extract_text_from_document_task.apply_async(
                args=[fichier_id],
                retry=True,
                retry_policy={
                    'max_retries': 3,
                    'interval_start': 60,
                    'interval_step': 60,
                    'interval_max': 600,
                }
            )
            
            with allow_join_result():
                json_structure = extraction_result.get(timeout=300)  # 5 minutes max
            
            if not json_structure:
                raise ValueError("Extraction de texte a retourné une structure vide")
            
            # ÉTAPE 4: Génération de granules
            logger.info(f"🔨 [Task {self.request.id}] Génération de granules...")
            granules_result = generate_granules_task.apply_async(
                args=[fichier_id, json_structure],
                retry=True,
                retry_policy={
                    'max_retries': 3,
                    'interval_start': 60,
                    'interval_step': 60,
                    'interval_max': 600,
                }
            )
            
            with allow_join_result():
                cours_info = granules_result.get(timeout=600)  # 10 minutes max
            
            # ÉTAPE 5: Finalisation
            fichier.statut_traitement = 'TRAITE'
            fichier.save()
            
            # Enregistrer les résultats dans le log
            proc_log.set_result({
                'cours_id': cours_info['cours_id'],
                'cours_titre': cours_info['cours_titre'],
                'granules_count': cours_info['granules_count']
            })
            
            logger.info(f"✅ [Task {self.request.id}] Traitement terminé avec succès: {fichier.titre}")
            
            return {
                "success": True,
                "message": f"Traitement réussi: {cours_info['cours_titre']}",
                "cours_id": cours_info['cours_id'],
                "granules_count": cours_info['granules_count']
            }
        
    except FichierSource.DoesNotExist:
        logger.error(f"❌ [Task {self.request.id}] Fichier introuvable: {fichier_id}")
        return {"success": False, "message": "Fichier introuvable"}
        
    except Exception as exc:
        logger.error(f"❌ [Task {self.request.id}] Erreur: {exc}", exc_info=True)
        
        # Mise à jour du statut en erreur
        try:
            fichier = FichierSource.objects.get(id=fichier_id)
            fichier.statut_traitement = 'ERREUR'
            fichier.save()
        except Exception:
            pass
        
        # Retry avec backoff exponentiel
        if self.request.retries < self.max_retries:
            retry_in = 60 * (2 ** self.request.retries)  # Backoff exponentiel: 60s, 120s, 240s
            logger.warning(f"🔄 [Task {self.request.id}] Retry {self.request.retries + 1}/{self.max_retries} dans {retry_in}s")
            raise self.retry(exc=exc, countdown=retry_in)
        
        return {"success": False, "message": f"Erreur: {str(exc)}"}


# ==============================================================================
# TÂCHE 2: EXTRACTION DE TEXTE
# ==============================================================================

@shared_task(bind=True, max_retries=3)
def extract_text_from_document_task(self, fichier_id):
    """
    Extrait le texte et la structure d'un document (PDF/DOCX/TXT).
    
    Args:
        fichier_id: UUID du FichierSource
        
    Returns:
        dict: Structure JSON du document
    """
    try:
        logger.info(f"📝 [Extract Task {self.request.id}] Début extraction pour {fichier_id}")
        
        fichier = FichierSource.objects.get(id=fichier_id)
        
        # Tracking de l'extraction
        with ProcessingLogger(fichier, 'EXTRACTION_TEXT', self.request.id) as extract_log:
            file_path = fichier.fichier_original.path
            ext = file_path.split('.')[-1].lower()
            
            # Extraction selon le type
            if ext == 'docx':
                logger.info(f"📄 [Extract Task {self.request.id}] Extraction DOCX...")
                json_structure = extract_structure_from_docx(file_path)
            elif ext == 'pdf':
                logger.info(f"📄 [Extract Task {self.request.id}] Extraction PDF...")
                json_structure = extract_structure_from_pdf(file_path)
            elif ext == 'txt':
                logger.info(f"📄 [Extract Task {self.request.id}] Extraction TXT...")
                json_structure = extract_structure_from_txt(file_path)
            else:
                raise ValueError(f"Format {ext} non supporté")
            
            # Validation
            if not json_structure or not json_structure.get("sections"):
                logger.warning(f"⚠️ [Extract Task {self.request.id}] Structure vide, création fallback")
                json_structure = {
                    "metadata": {"extraction_date": datetime.now().isoformat()},
                    "sections": [{
                        "type": "h1",
                        "level": 1,
                        "content": "Document",
                        "children": []
                    }]
                }
            
            # Enregistrer le résultat
            sections_count = len(json_structure.get('sections', []))
            extract_log.set_result({'sections_count': sections_count})
            
            logger.info(f"✅ [Extract Task {self.request.id}] Extraction réussie: {sections_count} sections")
            return json_structure
        
    except Exception as exc:
        logger.error(f"❌ [Extract Task {self.request.id}] Erreur extraction: {exc}", exc_info=True)
        
        # Retry
        if self.request.retries < self.max_retries:
            retry_in = 60 * (2 ** self.request.retries)
            logger.warning(f"🔄 [Extract Task {self.request.id}] Retry dans {retry_in}s")
            raise self.retry(exc=exc, countdown=retry_in)
        
        raise


# ==============================================================================
# TÂCHE 3: GÉNÉRATION DE GRANULES
# ==============================================================================

@shared_task(bind=True, max_retries=3)
def generate_granules_task(self, fichier_id, json_structure):
    """
    Génère la hiérarchie MySQL et les granules MongoDB à partir d'une structure JSON.
    
    Args:
        fichier_id: UUID du FichierSource
        json_structure: Structure JSON extraite du document
        
    Returns:
        dict: {"cours_id": int, "cours_titre": str, "granules_count": int}
    """
    try:
        logger.info(f"🔨 [Granule Task {self.request.id}] Début génération pour {fichier_id}")
        
        fichier = FichierSource.objects.get(id=fichier_id)
        
        # Tracking de la génération
        with ProcessingLogger(fichier, 'GRANULATION', self.request.id) as granule_log:
            # Stockage MongoDB du document complet
            from .utils import get_mongo_db
            mongo_db = get_mongo_db()
            
            mongo_db['fichiers_uploades'].update_one(
                {"fichier_source_id": str(fichier.id)},
                {
                    "$set": {
                        "titre": fichier.titre,
                        "structure_json": json_structure,
                        "date_traitement": datetime.now().isoformat(),
                        "version": "2.0-JSON-ASYNC"
                    }
                },
                upsert=True
            )
            
            doc = mongo_db['fichiers_uploades'].find_one({"fichier_source_id": str(fichier.id)})
            fichier.mongo_transforme_id = str(doc['_id'])
            fichier.save()
            
            # Génération de la hiérarchie et des granules
            logger.info(f"🔨 [Granule Task {self.request.id}] Création hiérarchie MySQL + granules MongoDB...")
            cours = split_and_create_granules(fichier, json_structure)
            
            # Comptage des granules
            from .models import Granule
            granules_count = Granule.objects.filter(fichier_source=fichier).count()
            
            # Enregistrer les résultats
            granule_log.set_result({
                'cours_id': str(cours.id),
                'cours_code': cours.matiere.code if cours.matiere else "N/A",
                'granules_count': granules_count
            })
            
            logger.info(f"✅ [Granule Task {self.request.id}] Génération réussie: {granules_count} granules créés")
            
            return {
                "cours_id": str(cours.id),
                "cours_titre": cours.titre,
            "cours_code": cours.matiere.code if cours.matiere else "N/A",
            "granules_count": granules_count
        }
        
    except Exception as exc:
        logger.error(f"❌ [Granule Task {self.request.id}] Erreur génération: {exc}", exc_info=True)
        
        # Retry
        if self.request.retries < self.max_retries:
            retry_in = 60 * (2 ** self.request.retries)
            logger.warning(f"🔄 [Granule Task {self.request.id}] Retry dans {retry_in}s")
            raise self.retry(exc=exc, countdown=retry_in)
        
        raise


# ==============================================================================
# TÂCHE 4: EXTRACTION D'IMAGES (NON-BLOQUANT)
# ==============================================================================

@shared_task(bind=True, max_retries=2)
def extract_images_from_pdf_task(self, fichier_id):
    """
    Extrait les images d'un PDF de manière asynchrone (non-bloquant).
    
    Args:
        fichier_id: UUID du FichierSource
        
    Returns:
        int: Nombre d'images extraites
    """
    try:
        logger.info(f"🖼️ [Image Task {self.request.id}] Extraction images pour {fichier_id}")
        
        fichier = FichierSource.objects.get(id=fichier_id)
        
        # Tracking de l'extraction d'images
        with ProcessingLogger(fichier, 'EXTRACTION_IMAGES', self.request.id) as img_log:
            count = extract_images_from_pdf(fichier)
            img_log.set_result({'images_extracted': count})
            
            logger.info(f"✅ [Image Task {self.request.id}] {count} images extraites")
            return count
        
    except Exception as exc:
        logger.warning(f"⚠️ [Image Task {self.request.id}] Erreur extraction images: {exc}")
        
        # Retry limité (tâche non-critique)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=120)
        
        return 0
