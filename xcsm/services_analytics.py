# Author: Dilane PAFE
# Fichier: xcsm/services_analytics.py - Algorithmes de calcul des statistiques

from django.db.models import Sum, Avg, Count
from django.utils import timezone
from datetime import timedelta
from .models_analytics import TrackingSession, CourseAnalyticsSnapshot
from .models import Progression, Etudiant

def calculate_course_analytics(cours):
    """
    Calcule toutes les métriques requises par le FrontEnd (analytics.types.ts) pour un cours donné.
    """
    etudiants_inscrits = cours.matiere.etudiants_inscrits.all() if cours.matiere else Etudiant.objects.none()
    total_students = etudiants_inscrits.count()

    if total_students == 0:
        return _get_empty_analytics()

    # 1. Calcul du temps total et moyen
    sessions = TrackingSession.objects.filter(cours=cours)
    total_time_seconds = sessions.aggregate(total=Sum('time_spent_seconds'))['total'] or 0
    total_time_hours = total_time_seconds / 3600

    # 2. Calcul du taux de complétion moyen
    # (Nombre de granules consultés / Nombre total de granules) pour chaque étudiant
    total_granules_cours = cours.parties.aggregate(total=Count('chapitres__sections__granules'))['total'] or 1
    
    progressions_par_etudiant = Progression.objects.filter(cours=cours).values('etudiant').annotate(granules_vus=Count('granule'))
    
    somme_completion = 0
    active_students_count = 0
    at_risk_students_count = 0
    
    # Seuil d'inactivité (ex: pas de connexion depuis 7 jours)
    seuil_inactivite = timezone.now() - timedelta(days=7)

    for prog in progressions_par_etudiant:
        taux_etudiant = (prog['granules_vus'] / total_granules_cours) * 100
        somme_completion += taux_etudiant
        
        # Détermination du statut de l'étudiant
        etudiant_obj = Etudiant.objects.get(pk=prog['etudiant'])
        dernier_log = etudiant_obj.utilisateur.last_login
        
        if dernier_log and dernier_log > seuil_inactivite:
            active_students_count += 1
            # Si actif mais taux très bas, il est "à risque"
            if taux_etudiant < 20: 
                at_risk_students_count += 1
        else:
            # Inactif et taux bas = à risque élevé
            if taux_etudiant < 50:
                at_risk_students_count += 1

    average_completion = somme_completion / total_students if total_students > 0 else 0

    # 3. Identification des zones de difficulté (L'algorithme clé)
    difficulty_zones = _identify_difficulty_zones(cours, sessions)

    # 4. Sauvegarde d'un snapshot pour l'historique
    CourseAnalyticsSnapshot.objects.create(
        cours=cours,
        total_students=total_students,
        active_students=active_students_count,
        at_risk_students=at_risk_students_count,
        average_completion_rate=average_completion,
        total_time_spent_hours=total_time_hours,
        difficulty_zones=difficulty_zones
    )

    return {
        "overview": {
            "totalStudents": total_students,
            "averageCompletion": round(average_completion, 1),
            "totalTimeSpent": round(total_time_hours, 1),
            "activeStudents": active_students_count,
            "atRiskStudents": at_risk_students_count
        },
        "difficultyZones": difficulty_zones
    }

def _identify_difficulty_zones(cours, sessions):
    """
    Analyse les sessions pour trouver les granules où les étudiants passent 
    anormalement beaucoup de temps ou ont un faible taux de réussite.
    """
    zones = []
    
    # On groupe par granule et on calcule la moyenne
    stats_granules = sessions.values('granule__titre').annotate(
        avg_time=Avg('time_spent_seconds'),
        avg_score=Avg('success_rate'),
        student_count=Count('etudiant', distinct=True)
    )

    for stat in stats_granules:
        # Règle 1: Temps passé anormalement long (ex: > 5 minutes sur un seul granule)
        if stat['avg_time'] and stat['avg_time'] > 300:
            zones.append({
                "concept": stat['granule__titre'],
                "struggling_students": stat['student_count'],
                "average_time": round(stat['avg_time'] / 60, 1), # En minutes
                "type": "time"
            })
            continue # Passe au suivant pour ne pas doubler l'alerte

        # Règle 2: Score de réussite très bas (ex: < 40% de réussite aux QCM liés)
        if stat['avg_score'] is not None and stat['avg_score'] < 0.4:
            zones.append({
                "concept": stat['granule__titre'],
                "struggling_students": stat['student_count'],
                "average_time": round((stat['avg_time'] or 0) / 60, 1),
                "type": "score"
            })

    # On trie pour renvoyer les zones les plus problématiques en premier
    return sorted(zones, key=lambda x: x['struggling_students'], reverse=True)[:5]

def _get_empty_analytics():
    return {
        "overview": {"totalStudents": 0, "averageCompletion": 0, "totalTimeSpent": 0, "activeStudents": 0, "atRiskStudents": 0},
        "difficultyZones": []
    }