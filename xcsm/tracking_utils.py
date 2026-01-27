"""
Utilitaires pour le logging et le tracking des opérations.
"""

from django.utils import timezone
from .models_tracking import ProcessingLog, UserActivityLog
import logging
import traceback

logger = logging.getLogger(__name__)


class ProcessingLogger:
    """
    Context manager pour logger automatiquement les opérations de traitement.
    
    Usage:
        with ProcessingLogger(fichier, 'EXTRACTION_TEXT', task_id) as log:
            # Faire le traitement
            result = extract_text(fichier)
            log.set_result({'sections': 10, 'granules': 145})
    """
    
    def __init__(self, fichier_source, operation, celery_task_id=None):
        self.fichier_source = fichier_source
        self.operation = operation
        self.celery_task_id = celery_task_id
        self.log_entry = None
        self.start_time = None
        
    def __enter__(self):
        """Début de l'opération"""
        self.start_time = timezone.now()
        self.log_entry = ProcessingLog.objects.create(
            fichier_source=self.fichier_source,
            operation=self.operation,
            status='STARTED',
            celery_task_id=self.celery_task_id
        )
        logger.info(f"📊 [Log {self.log_entry.id}] Démarrage: {self.operation} pour {self.fichier_source.titre}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Fin de l'opération"""
        self.log_entry.completed_at = timezone.now()
        self.log_entry.calculate_duration()
        
        if exc_type is None:
            # Succès
            self.log_entry.status = 'SUCCESS'
            logger.info(
                f"✅ [Log {self.log_entry.id}] Succès: {self.operation} "
                f"({self.log_entry.duration_seconds:.2f}s)"
            )
        else:
            # Erreur
            self.log_entry.status = 'FAILED'
            self.log_entry.error_message = str(exc_val)
            self.log_entry.error_traceback = ''.join(
                traceback.format_exception(exc_type, exc_val, exc_tb)
            )
            logger.error(
                f"❌ [Log {self.log_entry.id}] Échec: {self.operation} "
                f"- {exc_val}"
            )
        
        self.log_entry.save()
        
        # Ne pas supprimer l'exception
        return False
    
    def set_result(self, result_data):
        """Définir les résultats de l'opération"""
        if self.log_entry:
            self.log_entry.result_summary = result_data
            self.log_entry.save(update_fields=['result_summary'])
    
    def set_progress(self, status='IN_PROGRESS'):
        """Mettre à jour le statut pendant l'opération"""
        if self.log_entry:
            self.log_entry.status = status
            self.log_entry.save(update_fields=['status'])
    
    def increment_retry(self):
        """Incrémenter le compteur de retry"""
        if self.log_entry:
            self.log_entry.retry_count += 1
            self.log_entry.status = 'RETRYING'
            self.log_entry.save(update_fields=['retry_count', 'status'])


def log_user_activity(user, action, resource_type=None, resource_id=None, 
                      metadata=None, request=None):
    """
    Enregistre une activité utilisateur.
    
    Args:
        user: Instance de Utilisateur
        action: Type d'action (voir UserActivityLog.ACTION_CHOICES)
        resource_type: Type de ressource concernée (optionnel)
        resource_id: ID de la ressource (optionnel)
        metadata: Données supplémentaires (optionnel)
        request: Objet request Django pour extraire IP/User-Agent (optionnel)
    """
    ip_address = None
    user_agent = None
    
    if request:
        # Extraction de l'IP (en tenant compte des proxies)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]  # Limite à 500 chars
    
    try:
        UserActivityLog.objects.create(
            user=user,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata
        )
        logger.debug(f"📝 Activity logged: {user.email if user else 'Anonymous'} - {action}")
    except Exception as e:
        # Ne jamais faire échouer une requête à cause du logging
        logger.warning(f"⚠️ Failed to log user activity: {e}")


def get_processing_stats(fichier_source):
    """
    Récupère les statistiques de traitement pour un fichier.
    
    Returns:
        dict: Statistiques incluant nombre de logs, durée totale, erreurs, etc.
    """
    logs = ProcessingLog.objects.filter(fichier_source=fichier_source)
    
    total_logs = logs.count()
    success_count = logs.filter(status='SUCCESS').count()
    failed_count = logs.filter(status='FAILED').count()
    
    # Durée totale (somme de toutes les opérations)
    total_duration = sum(
        log.duration_seconds for log in logs 
        if log.duration_seconds is not None
    )
    
    # Dernière erreur
    last_error = logs.filter(status='FAILED').first()
    
    return {
        'total_operations': total_logs,
        'success_count': success_count,
        'failed_count': failed_count,
        'total_duration_seconds': total_duration,
        'last_error': last_error.error_message if last_error else None,
        'retry_count': sum(log.retry_count for log in logs)
    }
