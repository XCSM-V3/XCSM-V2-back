"""
Vue pour l'édition du contenu des granules
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from bson import ObjectId

from .models import Granule
from .utils import get_mongo_db


class GranuleUpdateView(APIView):
    """
    Mettre à jour le contenu d'un granule
    PUT /api/v1/granules/{granule_id}/update/
    """
    permission_classes = [IsAuthenticated]
    
    def put(self, request, granule_id):
        try:
            granule = Granule.objects.select_related(
                'sous_section__section__chapitre__partie__cours__enseignant__utilisateur'
            ).get(id=granule_id)
            
            # Vérifier que l'utilisateur est le propriétaire du cours
            cours = granule.sous_section.section.chapitre.partie.cours
            if cours.enseignant.utilisateur != request.user:
                return Response(
                    {'error': 'Permission refusée. Vous devez être le propriétaire du cours.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Récupérer le nouveau contenu
            new_content = request.data.get('contenu')
            if new_content is None:
                return Response(
                    {'error': 'Le champ "contenu" est requis'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mettre à jour dans MongoDB
            if granule.mongo_contenu_id:
                mongo_db = get_mongo_db()
                result = mongo_db['granules'].update_one(
                    {"_id": ObjectId(granule.mongo_contenu_id)},
                    {"$set": {"content": new_content}}
                )
                
                if result.matched_count == 0:
                    return Response(
                        {'error': 'Contenu MongoDB introuvable'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                return Response(
                    {'error': 'Ce granule n\'a pas de contenu MongoDB associé'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({
                'message': 'Granule mis à jour avec succès',
                'granule_id': str(granule.id)
            })
            
        except Granule.DoesNotExist:
            return Response(
                {'error': 'Granule introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de la mise à jour: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
