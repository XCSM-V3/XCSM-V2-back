"""
Vues pour l'affichage du contenu à différents niveaux hiérarchiques
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Cours, Partie, Chapitre, Section, SousSection, Granule
from .serializers import GranuleSerializer
from .json_utils import get_granule_content


def enrichir_granules_avec_hierarchie(granules):
    """
    Enrichit une liste de granules avec leur contenu MongoDB et leur hiérarchie.
    Détecte automatiquement les changements de partie/chapitre/section/sous-section.
    """
    granules_data = []
    current_partie = None
    current_chapitre = None
    current_section = None
    current_sous_section = None
    
    for granule in granules:
        # Détecter les changements de hiérarchie
        partie_titre = granule.sous_section.section.chapitre.partie.titre
        chapitre_titre = granule.sous_section.section.chapitre.titre
        section_titre = granule.sous_section.section.titre
        sous_section_titre = granule.sous_section.titre
        
        granule_dict = {
            'id': str(granule.id),
            'titre': granule.titre,
            'type_contenu': granule.type_contenu,
            'ordre': granule.ordre,
            'contenu': get_granule_content(granule.mongo_contenu_id),
            # Ajouter les titres hiérarchiques
            'hierarchie': {
                'partie': partie_titre,
                'chapitre': chapitre_titre,
                'section': section_titre,
                'sous_section': sous_section_titre,
                # Indiquer si c'est un nouveau titre (pour l'affichage)
                'nouvelle_partie': partie_titre != current_partie,
                'nouveau_chapitre': chapitre_titre != current_chapitre,
                'nouvelle_section': section_titre != current_section,
                'nouvelle_sous_section': sous_section_titre != current_sous_section,
            }
        }
        
        # Mettre à jour les titres courants
        current_partie = partie_titre
        current_chapitre = chapitre_titre
        current_section = section_titre
        current_sous_section = sous_section_titre
        
        granules_data.append(granule_dict)
    
    return granules_data


class CoursContentView(APIView):
    """
    Afficher tous les granules d'un cours complet
    GET /api/v1/contenu/cours/<uuid:cours_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, cours_id):
        try:
            cours = Cours.objects.get(id=cours_id)
            
            # Récupérer tous les granules du cours
            granules = Granule.objects.filter(
                sous_section__section__chapitre__partie__cours=cours
            ).select_related(
                'sous_section__section__chapitre__partie__cours'
            ).order_by(
                'sous_section__section__chapitre__partie__numero',
                'sous_section__section__chapitre__numero',
                'sous_section__section__numero',
                'sous_section__numero',
                'ordre'
            )
            
            # Enrichir avec le contenu MongoDB et la hiérarchie
            granules_data = enrichir_granules_avec_hierarchie(granules)
            
            return Response({
                'type': 'cours',
                'titre': cours.titre,
                'cours_id': str(cours.id),
                'cours_titre': cours.titre,
                'granules': granules_data,
                'chemin': {}
            })
            
        except Cours.DoesNotExist:
            return Response(
                {'error': 'Cours introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )


class PartieContentView(APIView):
    """
    Afficher tous les granules d'une partie
    GET /api/v1/contenu/partie/<uuid:partie_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, partie_id):
        try:
            partie = Partie.objects.select_related('cours').get(id=partie_id)
            
            granules = Granule.objects.filter(
                sous_section__section__chapitre__partie=partie
            ).select_related(
                'sous_section__section__chapitre'
            ).order_by(
                'sous_section__section__chapitre__numero',
                'sous_section__section__numero',
                'sous_section__numero',
                'ordre'
            )
            
            granules_data = enrichir_granules_avec_hierarchie(granules)
            
            return Response({
                'type': 'partie',
                'titre': partie.titre,
                'cours_id': str(partie.cours.id),
                'cours_titre': partie.cours.titre,
                'granules': granules_data,
                'chemin': {
                    'partie': partie.titre
                }
            })
            
        except Partie.DoesNotExist:
            return Response(
                {'error': 'Partie introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )


class ChapitreContentView(APIView):
    """
    Afficher tous les granules d'un chapitre
    GET /api/v1/contenu/chapitre/<uuid:chapitre_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, chapitre_id):
        try:
            chapitre = Chapitre.objects.select_related(
                'partie__cours'
            ).get(id=chapitre_id)
            
            granules = Granule.objects.filter(
                sous_section__section__chapitre=chapitre
            ).select_related(
                'sous_section__section'
            ).order_by(
                'sous_section__section__numero',
                'sous_section__numero',
                'ordre'
            )
            
            granules_data = enrichir_granules_avec_hierarchie(granules)
            
            return Response({
                'type': 'chapitre',
                'titre': chapitre.titre,
                'cours_id': str(chapitre.partie.cours.id),
                'cours_titre': chapitre.partie.cours.titre,
                'granules': granules_data,
                'chemin': {
                    'partie': chapitre.partie.titre,
                    'chapitre': chapitre.titre
                }
            })
            
        except Chapitre.DoesNotExist:
            return Response(
                {'error': 'Chapitre introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )


class SectionContentView(APIView):
    """
    Afficher tous les granules d'une section
    GET /api/v1/contenu/section/<uuid:section_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, section_id):
        try:
            section = Section.objects.select_related(
                'chapitre__partie__cours'
            ).get(id=section_id)
            
            granules = Granule.objects.filter(
                sous_section__section=section
            ).select_related(
                'sous_section'
            ).order_by(
                'sous_section__numero',
                'ordre'
            )
            
            granules_data = enrichir_granules_avec_hierarchie(granules)
            
            return Response({
                'type': 'section',
                'titre': section.titre,
                'cours_id': str(section.chapitre.partie.cours.id),
                'cours_titre': section.chapitre.partie.cours.titre,
                'granules': granules_data,
                'chemin': {
                    'partie': section.chapitre.partie.titre,
                    'chapitre': section.chapitre.titre,
                    'section': section.titre
                }
            })
            
        except Section.DoesNotExist:
            return Response(
                {'error': 'Section introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )


class SousSectionContentView(APIView):
    """
    Afficher tous les granules d'une sous-section
    GET /api/v1/contenu/sous_section/<uuid:sous_section_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, sous_section_id):
        try:
            sous_section = SousSection.objects.select_related(
                'section__chapitre__partie__cours'
            ).get(id=sous_section_id)
            
            granules = Granule.objects.filter(
                sous_section=sous_section
            ).order_by('ordre')
            
            granules_data = enrichir_granules_avec_hierarchie(granules)
            
            return Response({
                'type': 'sous_section',
                'titre': sous_section.titre,
                'cours_id': str(sous_section.section.chapitre.partie.cours.id),
                'cours_titre': sous_section.section.chapitre.partie.cours.titre,
                'granules': granules_data,
                'chemin': {
                    'partie': sous_section.section.chapitre.partie.titre,
                    'chapitre': sous_section.section.chapitre.titre,
                    'section': sous_section.section.titre,
                    'sous_section': sous_section.titre
                }
            })
            
        except SousSection.DoesNotExist:
            return Response(
                {'error': 'Sous-section introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )
