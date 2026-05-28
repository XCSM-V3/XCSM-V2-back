# Author: Dilane PAFE
# Fichier: xcsm/services_analytics.py - Algorithmes de calcul des statistiques

from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from .models import Etudiant
from .models_analytics import CourseAnalyticsSnapshot, TrackingSession


def _clamp_0_100(value: float) -> int:
    if value < 0:
        return 0
    if value > 100:
        return 100
    return int(round(value))


def _compute_difficulty_score(avg_time_seconds: float, completion_rate: float, ai_questions_count: int, views: int) -> int:
    """
    Score heuristique 0-100 utilisé par le front.
    - plus le temps moyen est élevé, plus la difficulté augmente
    - plus le taux de complétion est faible, plus la difficulté augmente
    - l'activité IA (proxy via success_rate non null) augmente le score
    """
    # Normalisation (on cappe à 10 minutes pour éviter que ça explose)
    normalized_time = min((avg_time_seconds or 0) / 600.0, 1.0)  # 0..1
    completion_component = 1.0 - min(max(completion_rate, 0.0), 100.0) / 100.0  # 0..1

    denom = max(views or 0, 1)
    ai_component = min((ai_questions_count or 0) / denom, 1.0)  # 0..1

    difficulty = 100.0 * (0.45 * normalized_time + 0.45 * completion_component + 0.10 * ai_component)
    return _clamp_0_100(difficulty)


def calculate_course_analytics(cours, period_days: int = 7):
    """
    Calcule toutes les métriques requises par le FrontEnd (dashboard enseignant).

    Retourne un objet aligné avec `generateDemoAnalytics()` côté front :
    - total_views, unique_learners, avg_completion_rate, avg_session_duration, total_ai_interactions
    - difficult_zones, most_consulted, least_consulted, granule_metrics
    """
    period_days = max(int(period_days or 7), 1)

    etudiants_inscrits = cours.matiere.etudiants_inscrits.all() if cours.matiere else Etudiant.objects.none()
    student_ids = list(etudiants_inscrits.values_list("pk", flat=True))
    total_students = len(student_ids)

    total_granules_cours = cours.parties.aggregate(
        total=Count("chapitres__sections__sous_sections__granules")
    ).get("total") or 0
    total_granules_cours = max(int(total_granules_cours), 1)  # éviter divisions par 0

    date_from = timezone.now() - timedelta(days=period_days)

    sessions = TrackingSession.objects.filter(cours=cours, date_session__gte=date_from)

    if total_students == 0:
        empty = {
            "course_id": str(cours.id),
            "course_title": cours.titre,
            "total_students": 0,
            "total_granules": 0,
            "total_views": 0,
            "unique_learners": 0,
            "avg_completion_rate": 0,
            "avg_session_duration": 0,
            "total_ai_interactions": 0,
            "difficult_zones": [],
            "most_consulted": [],
            "least_consulted": [],
            "granule_metrics": [],
            "alert_count": 0,
            "period_days": period_days,
            "active_students_7d": 0,
            "at_risk_students": 0,
            "last_updated": timezone.now().isoformat(),
        }
        return empty

    # 1) Vue globale
    unique_learners = sessions.values("etudiant_id").distinct().count()
    total_views = sessions.count()

    # 2) Vues + moyennes par granule (et proxy "questions IA" via success_rate non null)
    per_granule = sessions.values(
        "granule_id",
        "granule__titre",
        "granule__sous_section__section__chapitre__titre",
    ).annotate(
        views=Count("id"),
        unique_sessions=Count("etudiant_id", distinct=True),
        avg_time_seconds=Avg("time_spent_seconds"),
        ai_questions_count=Count("id", filter=Q(success_rate__isnull=False)),
    )

    granule_metrics = []
    for g in per_granule:
        views = g["views"] or 0
        unique_sessions = g["unique_sessions"] or 0
        avg_time_seconds = float(g["avg_time_seconds"] or 0.0)
        ai_questions_count = g["ai_questions_count"] or 0

        completion_rate = (unique_sessions / total_students) * 100.0 if total_students else 0.0
        difficulty_score = _compute_difficulty_score(
            avg_time_seconds=avg_time_seconds,
            completion_rate=completion_rate,
            ai_questions_count=ai_questions_count,
            views=views,
        )

        granule_metrics.append(
            {
                "granule_id": str(g["granule_id"]),
                "granule_title": g["granule__titre"],
                "chapter_title": g.get("granule__sous_section__section__chapitre__titre"),
                "views": int(views),
                "unique_sessions": int(unique_sessions),
                "avg_time_seconds": int(round(avg_time_seconds)),
                "ai_questions_count": int(ai_questions_count),
                "difficulty_score": int(difficulty_score),
                "completion_rate": _clamp_0_100(completion_rate),
                "is_difficult_zone": difficulty_score >= 65,
            }
        )

    # Moyenne du temps par granule (mimique le front/démo)
    if granule_metrics:
        avg_session_duration = int(round(sum(g["avg_time_seconds"] for g in granule_metrics) / len(granule_metrics)))
    else:
        avg_session_duration = 0

    total_ai_interactions = sum(g["ai_questions_count"] for g in granule_metrics)

    # 3) Complétion moyenne (basée sur les granules réellement consultés dans la période)
    granules_seen_by_student = sessions.values("etudiant_id").annotate(
        granules_vus=Count("granule_id", distinct=True)
    )
    granules_seen_map = {str(row["etudiant_id"]): int(row["granules_vus"] or 0) for row in granules_seen_by_student}

    somme_completion = 0.0
    active_students_count = 0
    at_risk_students_count = 0
    seuil_inactivite = timezone.now() - timedelta(days=period_days)

    # On charge last_login pour déterminer actifs / à risque
    etudiant_qs = Etudiant.objects.filter(pk__in=student_ids).select_related("utilisateur")
    for e in etudiant_qs:
        seen = granules_seen_map.get(str(e.pk), 0)
        taux_etudiant = (seen / total_granules_cours) * 100.0
        somme_completion += taux_etudiant

        dernier_log = getattr(e.utilisateur, "last_login", None)
        is_active = bool(dernier_log and dernier_log > seuil_inactivite)

        if is_active:
            active_students_count += 1
            if taux_etudiant < 20:
                at_risk_students_count += 1
        else:
            if taux_etudiant < 50:
                at_risk_students_count += 1

    avg_completion_rate = round((somme_completion / total_students) if total_students else 0.0, 1)

    difficult_zones = [g for g in granule_metrics if g["is_difficult_zone"]]

    # 4) Top / bottom granules (pour charts)
    by_views_desc = sorted(granule_metrics, key=lambda x: x["views"], reverse=True)
    most_consulted = by_views_desc[:3]
    least_consulted = by_views_desc[-2:] if len(by_views_desc) >= 2 else by_views_desc

    analytics = {
        "course_id": str(cours.id),
        "course_title": cours.titre,
        "total_students": total_students,
        "total_granules": int(cours.parties.aggregate(total=Count("chapitres__sections__sous_sections__granules")).get("total") or 0),
        "total_views": int(total_views),
        "unique_learners": int(unique_learners),
        "avg_completion_rate": avg_completion_rate,
        "avg_session_duration": avg_session_duration,
        "total_ai_interactions": int(total_ai_interactions),
        "difficult_zones": difficult_zones,
        "most_consulted": most_consulted,
        "least_consulted": least_consulted,
        "granule_metrics": granule_metrics,
        "alert_count": len(difficult_zones),
        "period_days": period_days,
        "active_students_7d": active_students_count,
        "at_risk_students": at_risk_students_count,
        "last_updated": timezone.now().isoformat(),
    }

    # 5) Snapshot (utile pour des graphes d'historique)
    total_time_spent_seconds = sessions.aggregate(total=Sum("time_spent_seconds")).get("total") or 0
    total_time_spent_hours = float(total_time_spent_seconds) / 3600.0

    CourseAnalyticsSnapshot.objects.create(
        cours=cours,
        total_students=total_students,
        active_students=active_students_count,
        at_risk_students=at_risk_students_count,
        average_completion_rate=avg_completion_rate,
        total_time_spent_hours=total_time_spent_hours,
        difficulty_zones=difficult_zones,
    )

    return analytics