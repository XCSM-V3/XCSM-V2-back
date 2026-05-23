# Author: Dilane PAFE
# Fichier: xcsm/models_analytics.py - Modèles pour le Tracking et l'Analytics

import uuid
from django.db import models
from .models import Etudiant, Cours, Granule, Enseignant

class TrackingSession(models.Model):
    """
    Enregistre le temps passé par un étudiant sur un granule spécifique.
    C'est la brique de base pour calculer le temps moyen et identifier les zones de difficulté.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name='sessions_tracking')
    cours = models.ForeignKey(Cours, on_delete=models.CASCADE, related_name='sessions_tracking_cours')
    granule = models.ForeignKey(Granule, on_delete=models.CASCADE, related_name='sessions_tracking_granules')
    
    # Le temps passé en secondes
    time_spent_seconds = models.IntegerField(default=0)
    
    # Indicateur de compréhension (ex: auto-évaluation de l'étudiant ou résultat du QCM IA lié)
    success_rate = models.FloatField(null=True, blank=True, help_text="Taux de réussite aux QCM sur ce granule (0.0 à 1.0)")
    
    date_session = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_session']

    def __str__(self):
        return f"{self.etudiant.utilisateur.username} sur {self.granule.titre} ({self.time_spent_seconds}s)"


class CourseAnalyticsSnapshot(models.Model):
    """
    Stocke une "photographie" des statistiques d'un cours à un instant T.
    Utile pour générer des graphiques d'évolution dans le temps sans recalculer toute la base.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cours = models.ForeignKey(Cours, on_delete=models.CASCADE, related_name='analytics_snapshots')
    
    total_students = models.IntegerField(default=0)
    active_students = models.IntegerField(default=0)
    at_risk_students = models.IntegerField(default=0)
    
    average_completion_rate = models.FloatField(default=0.0)
    total_time_spent_hours = models.FloatField(default=0.0)
    
    # Les zones de difficulté identifiées (JSON)
    # Format attendu par le front: [{ "concept": "React Hooks", "struggling_students": 12, "average_time": 45, "type": "time" | "score" }]
    difficulty_zones = models.JSONField(default=list)
    
    date_snapshot = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_snapshot']