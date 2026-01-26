"""
Modèles de Tracking et Traçabilité pour XCSM

Ce module contient les modèles pour:
- Journal des traitements de documents
- Logs des activités utilisateur
- Métriques de performance
"""

from django.db import models
from django.contrib.auth import get_user_model
from .models import FichierSource, Utilisateur
import uuid


class ProcessingLog(models.Model):
    """
    Journal détaillé des traitements de documents.
    Permet de tracer chaque étape du pipeline de traitement.
    """
    
    STATUS_CHOICES = [
        ('STARTED', 'Démarré'),
        ('IN_PROGRESS', 'En cours'),
        ('SUCCESS', 'Succès'),
        ('FAILED', 'Échec'),
        ('RETRYING', 'Nouvelle tentative'),
    ]
    
    OPERATION_CHOICES = [
        ('UPLOAD', 'Upload du fichier'),
        ('EXTRACTION_TEXT', 'Extraction de texte'),
        ('EXTRACTION_IMAGES', 'Extraction d\'images'),
        ('GRANULATION', 'Génération de granules'),
        ('OCR', 'Reconnaissance optique (OCR)'),
        ('INDEXING', 'Indexation vectorielle'),
        ('COMPLETE', 'Traitement complet'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fichier_source = models.ForeignKey(
        FichierSource,
        on_delete=models.CASCADE,
        related_name='processing_logs'
    )
    
    # Informations sur l'opération
    operation = models.CharField(
        max_length=50,
        choices=OPERATION_CHOICES,
        help_text="Type d'opération effectuée"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='STARTED'
    )
    
    # Métriques de performance
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Durée en secondes"
    )
    
    # Détails techniques
    celery_task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="ID de la tâche Celery"
    )
    retry_count = models.IntegerField(
        default=0,
        help_text="Nombre de tentatives"
    )
    
    # Résultats et erreurs
    result_summary = models.JSONField(
        null=True,
        blank=True,
        help_text="Résumé des résultats (granules créés, etc.)"
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Message d'erreur en cas d'échec"
    )
    error_traceback = models.TextField(
        null=True,
        blank=True,
        help_text="Traceback complet de l'erreur"
    )
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['fichier_source', '-started_at']),
            models.Index(fields=['status', '-started_at']),
            models.Index(fields=['operation', '-started_at']),
        ]
        verbose_name = "Log de traitement"
        verbose_name_plural = "Logs de traitement"
    
    def __str__(self):
        return f"{self.operation} - {self.status} ({self.started_at:%Y-%m-%d %H:%M})"
    
    def calculate_duration(self):
        """Calcule la durée si completed_at est défini"""
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = delta.total_seconds()
            self.save(update_fields=['duration_seconds'])


class UserActivityLog(models.Model):
    """
    Logs des activités utilisateur pour audit et analytics.
    """
    
    ACTION_CHOICES = [
        ('LOGIN', 'Connexion'),
        ('LOGOUT', 'Déconnexion'),
        ('REGISTER', 'Inscription'),
        ('UPLOAD_FILE', 'Upload de fichier'),
        ('CREATE_COURSE', 'Création de cours'),
        ('UPDATE_COURSE', 'Modification de cours'),
        ('DELETE_COURSE', 'Suppression de cours'),
        ('ENROLL_COURSE', 'Inscription à un cours'),
        ('GENERATE_QCM', 'Génération de QCM'),
        ('SEARCH', 'Recherche'),
        ('VIEW_DOCUMENT', 'Consultation de document'),
        ('DOWNLOAD', 'Téléchargement'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        related_name='activity_logs'
    )
    
    # Détails de l'action
    action = models.CharField(
        max_length=100,
        choices=ACTION_CHOICES
    )
    resource_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Type de ressource (Cours, Fichier, etc.)"
    )
    resource_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="ID de la ressource concernée"
    )
    
    # Métadonnées techniques
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Adresse IP de l'utilisateur"
    )
    user_agent = models.TextField(
        null=True,
        blank=True,
        help_text="User-Agent du navigateur"
    )
    
    # Données supplémentaires
    metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="Données additionnelles (query de recherche, etc.)"
    )
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
            models.Index(fields=['resource_type', 'resource_id']),
        ]
        verbose_name = "Log d'activité utilisateur"
        verbose_name_plural = "Logs d'activité utilisateur"
    
    def __str__(self):
        user_str = self.user.email if self.user else "Anonyme"
        return f"{user_str} - {self.action} ({self.timestamp:%Y-%m-%d %H:%M})"


class ProcessingMetrics(models.Model):
    """
    Statistiques agrégées de traitement pour tableaux de bord.
    Mise à jour périodique (ex: chaque jour).
    """
    
    date = models.DateField(unique=True, help_text="Date concernée")
    
    # Compteurs
    total_documents_processed = models.IntegerField(default=0)
    total_documents_success = models.IntegerField(default=0)
    total_documents_failed = models.IntegerField(default=0)
    total_granules_created = models.IntegerField(default=0)
    
    # Métriques de temps (en secondes)
    avg_extraction_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Temps moyen d'extraction de texte"
    )
    avg_granulation_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Temps moyen de génération de granules"
    )
    avg_total_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Temps moyen total de traitement"
    )
    
    # Métriques utilisateurs
    active_users_count = models.IntegerField(
        default=0,
        help_text="Nombre d'utilisateurs actifs ce jour"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = "Métrique de traitement"
        verbose_name_plural = "Métriques de traitement"
    
    def __str__(self):
        return f"Métriques du {self.date}"
