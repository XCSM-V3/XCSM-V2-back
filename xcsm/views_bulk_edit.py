"""
Vue pour l'édition en masse du contenu (tous les granules d'un chapitre/section/partie)
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from bson import ObjectId

from .models import Chapitre, Section, SousSection, Partie, Granule
from .utils import get_mongo_db


class BulkEditContentView(APIView):
    """
    Éditer tous les granules d'un chapitre/section/partie en une seule fois
    PUT /api/v1/contenu/bulk-edit/
    Body: {
        "type": "chapitre|section|sous_section|partie",
        "id": "uuid",
        "granules": [
            {"id": "uuid1", "contenu": "texte1"},
            {"id": "uuid2", "contenu": "texte2"},
            ...
        ]
    }
    """
    permission_classes = [IsAuthenticated]
    
    def put(self, request):
        try:
            content_type = request.data.get('type')
            content_id = request.data.get('id')
            granules_data = request.data.get('granules', [])
            
            if not content_type or not content_id or not granules_data:
                return Response(
                    {'error': 'Les champs type, id et granules sont requis'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Vérifier les permissions selon le type
            if not self._check_ownership(content_type, content_id, request.user):
                return Response(
                    {'error': 'Permission refusée. Vous devez être le propriétaire du cours.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Mettre à jour tous les granules
            mongo_db = get_mongo_db()
            updated_count = 0
            errors = []
            
            for granule_data in granules_data:
                granule_id = granule_data.get('id')
                new_content = granule_data.get('contenu')
                
                if not granule_id or new_content is None:
                    continue
                
                try:
                    granule = Granule.objects.get(id=granule_id)
                    
                    if granule.mongo_contenu_id:
                        result = mongo_db['granules'].update_one(
                            {"_id": ObjectId(granule.mongo_contenu_id)},
                            {"$set": {"content": new_content}}
                        )
                        
                        if result.modified_count > 0:
                            updated_count += 1
                    
                except Granule.DoesNotExist:
                    errors.append(f"Granule {granule_id} introuvable")
                except Exception as e:
                    errors.append(f"Erreur granule {granule_id}: {str(e)}")
            
            return Response({
                'message': f'{updated_count} granules mis à jour avec succès',
                'updated_count': updated_count,
                'total': len(granules_data),
                'errors': errors if errors else None
            })
            
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de la mise à jour: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _check_ownership(self, content_type, content_id, user):
        """Vérifier que l'utilisateur est propriétaire du cours"""
        try:
            if content_type == 'chapitre':
                obj = Chapitre.objects.select_related(
                    'partie__cours__enseignant__utilisateur'
                ).get(id=content_id)
                cours = obj.partie.cours
            elif content_type == 'section':
                obj = Section.objects.select_related(
                    'chapitre__partie__cours__enseignant__utilisateur'
                ).get(id=content_id)
                cours = obj.chapitre.partie.cours
            elif content_type == 'sous_section':
                obj = SousSection.objects.select_related(
                    'section__chapitre__partie__cours__enseignant__utilisateur'
                ).get(id=content_id)
                cours = obj.section.chapitre.partie.cours
            elif content_type == 'partie':
                obj = Partie.objects.select_related(
                    'cours__enseignant__utilisateur'
                ).get(id=content_id)
                cours = obj.cours
            else:
                return False
            
            return cours.enseignant.utilisateur == user
            
        except Exception:
            return False
