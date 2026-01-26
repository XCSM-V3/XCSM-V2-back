"""
Admin configuration pour les modèles de tracking et traçabilité.
"""

from django.contrib import admin
from .models_tracking import ProcessingLog, UserActivityLog, ProcessingMetrics


@admin.register(ProcessingLog)
class ProcessingLogAdmin(admin.ModelAdmin):
    """
    Interface admin pour consulter les logs de traitement.
    """
    list_display = [
        'operation',
        'fichier_source',
        'status',
        'duration_seconds',
        'retry_count',
        'started_at'
    ]
    
    list_filter = [
        'status',
        'operation',
        'started_at',
    ]
    
    search_fields = [
        'fichier_source__titre',
        'celery_task_id',
        'error_message',
    ]
    
    readonly_fields = [
        'id',
        'fichier_source',
        'operation',
        'status',
        'started_at',
        'completed_at',
        'duration_seconds',
        'celery_task_id',
        'retry_count',
        'result_summary',
        'error_message',
        'error_traceback',
    ]
    
    date_hierarchy = 'started_at'
    
    ordering = ['-started_at']
    
    def has_add_permission(self, request):
        """Les logs ne sont pas créables manuellement"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Empêcher la suppression accidentelle des logs"""
        return request.user.is_superuser


@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    """
    Interface admin pour consulter les activités utilisateur.
    """
    list_display = [
        'user',
        'action',
        'resource_type',
        'resource_id',
        'ip_address',
        'timestamp',
    ]
    
    list_filter = [
        'action',
        'resource_type',
        'timestamp',
    ]
    
    search_fields = [
        'user__email',
        'user__nom',
        'user__prenom',
        'ip_address',
        'resource_id',
    ]
    
    readonly_fields = [
        'id',
        'user',
        'action',
        'resource_type',
        'resource_id',
        'ip_address',
        'user_agent',
        'metadata',
        'timestamp',
    ]
    
    date_hierarchy = 'timestamp'
    
    ordering = ['-timestamp']
    
    def has_add_permission(self, request):
        """Les logs ne sont pas créables manuellement"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Seul le superuser peut supprimer les logs"""
        return request.user.is_superuser


@admin.register(ProcessingMetrics)
class ProcessingMetricsAdmin(admin.ModelAdmin):
    """
    Interface admin pour consulter les métriques agrégées.
    """
    list_display = [
        'date',
        'total_documents_processed',
        'total_documents_success',
        'total_documents_failed',
        'total_granules_created',
        'avg_total_time',
        'active_users_count',
    ]
    
    list_filter = [
        'date',
    ]
    
    readonly_fields = [
        'date',
        'total_documents_processed',
        'total_documents_success',
        'total_documents_failed',
        'total_granules_created',
        'avg_extraction_time',
        'avg_granulation_time',
        'avg_total_time',
        'active_users_count',
        'created_at',
        'updated_at',
    ]
    
    date_hierarchy = 'date'
    
    ordering = ['-date']
    
    def has_add_permission(self, request):
        """Les métriques ne sont pas créables manuellement"""
        return False
