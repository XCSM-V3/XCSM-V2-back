# Author: Dilane PAFE
# Fichier: xcsm/views_analytics.py - API pour le Dashboard Enseignant

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Cours
from .models_analytics import TrackingSession
from .services_analytics import calculate_course_analytics

class AnalyticsViewSet(viewsets.ViewSet):
    """
    Gère les routes /api/v1/analytics/ appelées par useAnalytics.ts
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='dashboard')
    def get_dashboard(self, request):
        """
        GET /api/v1/analytics/dashboard?course_id=123
        Renvoie les métriques globales pour le tableau de bord de l'enseignant.
        """
        course_id = request.query_params.get('course_id')
        if not course_id:
            return Response({"error": "course_id est requis"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cours = Cours.objects.get(id=course_id)
            period_raw = request.query_params.get("period", "7")
            try:
                period_days = int(period_raw)
            except ValueError:
                period_days = 7
            
            # Vérification (propriétaire, co-enseignant ou admin)
            is_owner = False
            is_co_teacher = False
            if hasattr(request.user, 'profil_enseignant'):
                ens = request.user.profil_enseignant
                is_owner = (cours.enseignant == ens)
                if cours.matiere:
                    is_co_teacher = (
                        cours.matiere.enseignant == ens
                        or cours.matiere.enseignants.filter(pk=ens.pk).exists()
                    )

            if not request.user.is_staff and not is_owner and not is_co_teacher:
                return Response({"error": "Non autorisé"}, status=status.HTTP_403_FORBIDDEN)

            data = calculate_course_analytics(cours, period_days=period_days)
            return Response(data)

        except Cours.DoesNotExist:
            return Response({"error": "Cours non trouvé"}, status=status.HTTP_404_NOT_FOUND)


    @action(detail=False, methods=['post'], url_path='track')
    def track_session(self, request):
        """
        POST /api/v1/analytics/track
        Appelé par le FrontEnd (côté étudiant) pour enregistrer le temps passé sur un granule.
        """
        data = request.data
        try:
            from .models import Etudiant, Granule
            etudiant = Etudiant.objects.get(utilisateur=request.user)
            cours = Cours.objects.get(id=data.get('course_id'))
            granule = Granule.objects.get(id=data.get('granule_id'))
            
            TrackingSession.objects.create(
                etudiant=etudiant,
                cours=cours,
                granule=granule,
                time_spent_seconds=data.get('time_spent', 0),
                success_rate=data.get('success_rate', None)
            )
            return Response({"success": True}, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=False, methods=['post'], url_path='synthesis')
    def generate_synthesis(self, request):
        """
        POST /api/v1/analytics/synthesis
        Utilise Gemini pour générer un résumé textuel à partir des métriques.
        """
        course_id = request.data.get('course_id')
        if not course_id:
            return Response({"error": "course_id est requis"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cours = Cours.objects.get(id=course_id)
            metrics = calculate_course_analytics(cours, period_days=7)
            
            # Appel au Chef d'Orchestre IA (Gemini)
            from .ai_service import setup_gemini
            model = setup_gemini()
            
            if not model:
                return Response({"synthesis": "Synthèse indisponible (API non configurée)."})

            difficulty_titles = ", ".join(
                [z.get("granule_title") for z in metrics.get("difficult_zones", []) if z.get("granule_title")]
            ) or "Aucune zone critique détectée"

            prompt = f"""
Tu es un conseiller pédagogique. Analyse ces statistiques d'un cours en ligne nommé "{cours.titre}" :
- Étudiants inscrits : {metrics.get('total_students', 0)}
- Taux de complétion moyen : {metrics.get('avg_completion_rate', 0)}%
- Étudiants à risque de décrochage : {metrics.get('at_risk_students', 0)}
- Zones de difficultés identifiées : {difficulty_titles}

Rédige un court rapport (3 paragraphes) pour l'enseignant.
1. Fais un bilan positif global.
2. Souligne les points d'attention (les zones de difficulté).
3. Donne une recommandation actionnable pour aider les étudiants à risque.
"""
            
            response = model.generate_content(prompt)
            return Response({"synthesis": response.text})

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)