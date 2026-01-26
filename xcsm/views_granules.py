"""
Endpoints pour la gestion des granules
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from .models import Granule, Cours, FichierSource
from .serializers import GranuleSerializer, GranuleDetailSerializer
from .json_utils import get_granule_content


class GranuleListView(APIView):
    """
    Liste tous les granules d'un cours ou d'un fichier
    GET /api/v1/granules/?cours_id=xxx
    GET /api/v1/granules/?fichier_id=xxx
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        cours_id = request.query_params.get('cours_id')
        fichier_id = request.query_params.get('fichier_id')
        
        if cours_id:
            try:
                cours = Cours.objects.get(id=cours_id)
                # Vérifier les permissions
                if cours.enseignant.utilisateur != request.user:
                    return Response(
                        {"error": "Vous n'êtes pas propriétaire de ce cours"},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                granules = Granule.objects.filter(
                    sous_section__section__chapitre__partie__cours=cours
                ).select_related(
                    'sous_section__section__chapitre__partie__cours'
                ).order_by('ordre')
                
            except Cours.DoesNotExist:
                return Response(
                    {"error": "Cours introuvable"},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        elif fichier_id:
            try:
                fichier = FichierSource.objects.get(id=fichier_id)
                # Vérifier les permissions
                if fichier.enseignant.utilisateur != request.user:
                    return Response(
                        {"error": "Vous n'êtes pas propriétaire de ce fichier"},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                granules = Granule.objects.filter(
                    fichier_source=fichier
                ).select_related(
                    'sous_section__section__chapitre__partie__cours'
                ).order_by('ordre')
                
            except FichierSource.DoesNotExist:
                return Response(
                    {"error": "Fichier introuvable"},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            return Response(
                {"error": "Paramètre cours_id ou fichier_id requis"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = GranuleSerializer(granules, many=True)
        return Response({
            "count": granules.count(),
            "granules": serializer.data
        })


class GranuleDetailView(APIView):
    """
    Voir/Éditer un granule spécifique
    GET /api/v1/granules/<uuid:granule_id>/
    PUT /api/v1/granules/<uuid:granule_id>/
    DELETE /api/v1/granules/<uuid:granule_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, granule_id):
        try:
            granule = Granule.objects.select_related(
                'sous_section__section__chapitre__partie__cours'
            ).get(id=granule_id)
            
            # Vérifier les permissions
            cours = granule.sous_section.section.chapitre.partie.cours
            if cours.enseignant.utilisateur != request.user:
                return Response(
                    {"error": "Vous n'êtes pas propriétaire de ce granule"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = GranuleDetailSerializer(granule)
            return Response(serializer.data)
            
        except Granule.DoesNotExist:
            return Response(
                {"error": "Granule introuvable"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def put(self, request, granule_id):
        """Éditer le contenu d'un granule"""
        try:
            granule = Granule.objects.select_related(
                'sous_section__section__chapitre__partie__cours'
            ).get(id=granule_id)
            
            # Vérifier les permissions
            cours = granule.sous_section.section.chapitre.partie.cours
            if cours.enseignant.utilisateur != request.user:
                return Response(
                    {"error": "Vous n'êtes pas propriétaire de ce granule"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Mettre à jour le titre si fourni
            if 'titre' in request.data:
                granule.titre = request.data['titre']
                granule.save()
            
            # Mettre à jour le contenu MongoDB si fourni
            if 'contenu' in request.data:
                from .utils import get_mongo_db
                mongo_db = get_mongo_db()
                mongo_db['granules'].update_one(
                    {'_id': granule.mongo_contenu_id},
                    {'$set': {'content': request.data['contenu']}}
                )
            
            serializer = GranuleDetailSerializer(granule)
            return Response(serializer.data)
            
        except Granule.DoesNotExist:
            return Response(
                {"error": "Granule introuvable"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def delete(self, request, granule_id):
        """Supprimer un granule"""
        try:
            granule = Granule.objects.select_related(
                'sous_section__section__chapitre__partie__cours'
            ).get(id=granule_id)
            
            # Vérifier les permissions
            cours = granule.sous_section.section.chapitre.partie.cours
            if cours.enseignant.utilisateur != request.user:
                return Response(
                    {"error": "Vous n'êtes pas propriétaire de ce granule"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Supprimer aussi de MongoDB
            from .utils import get_mongo_db
            mongo_db = get_mongo_db()
            mongo_db['granules'].delete_one({'_id': granule.mongo_contenu_id})
            
            granule.delete()
            
            return Response(
                {"message": "Granule supprimé avec succès"},
                status=status.HTTP_204_NO_CONTENT
            )
            
        except Granule.DoesNotExist:
            return Response(
                {"error": "Granule introuvable"},
                status=status.HTTP_404_NOT_FOUND
            )
