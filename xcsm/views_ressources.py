"""
Vues pour la gestion des ressources de cours (images, vidéos, documents)
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.core.files.storage import default_storage
from django.conf import settings
import os

from .models import Cours, Ressource
from .serializers import RessourceSerializer


class CoursRessourcesView(APIView):
    """
    Lister les ressources d'un cours
    GET /api/v1/cours/{cours_id}/ressources/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, cours_id):
        try:
            cours = Cours.objects.get(id=cours_id)
            
            # Vérifier les permissions (propriétaire ou étudiant inscrit)
            # Pour l'instant, on autorise tout le monde authentifié
            
            ressources = Ressource.objects.filter(cours=cours).order_by('-date_ajout')
            serializer = RessourceSerializer(ressources, many=True)
            
            return Response(serializer.data)
            
        except Cours.DoesNotExist:
            return Response(
                {'error': 'Cours introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )


class UploadRessourceView(APIView):
    """
    Uploader une ressource (image, vidéo, document) pour un cours
    POST /api/v1/cours/{cours_id}/upload-resource/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, cours_id):
        try:
            cours = Cours.objects.get(id=cours_id)
            
            # Vérifier que l'utilisateur est le propriétaire du cours
            if cours.enseignant.utilisateur != request.user:
                return Response(
                    {'error': 'Permission refusée. Vous devez être le propriétaire du cours.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Récupérer le fichier
            file = request.FILES.get('file')
            if not file:
                return Response(
                    {'error': 'Aucun fichier fourni'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Récupérer le titre (optionnel, sinon utiliser le nom du fichier)
            titre = request.data.get('titre', file.name)
            
            # Déterminer le type de ressource selon l'extension
            extension = os.path.splitext(file.name)[1].lower()
            if extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
                type_ressource = 'IMAGE'
            elif extension in ['.mp4', '.avi', '.mov', '.wmv', '.webm']:
                type_ressource = 'VIDEO'
            elif extension in ['.pdf', '.doc', '.docx', '.txt', '.ppt', '.pptx']:
                type_ressource = 'DOCUMENT'
            else:
                type_ressource = 'AUTRE'
            
            # Créer la ressource
            ressource = Ressource.objects.create(
                cours=cours,
                titre=titre,
                type_ressource=type_ressource,
                fichier=file
            )
            
            serializer = RessourceSerializer(ressource)
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Cours.DoesNotExist:
            return Response(
                {'error': 'Cours introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de l\'upload: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
