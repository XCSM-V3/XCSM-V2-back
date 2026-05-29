# Author: Dilane PAFE
# Fichier: xcsm/views_cours.py - API CRUD complète pour les Cours

from django.http import StreamingHttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q
import uuid

from .models import Cours, Enseignant, Etudiant, FichierSource, Granule, Exercice, Question, Reponse, Progression, Ressource
from .serializers import (
    CoursListSerializer, 
    CoursDetailSerializer, 
    CoursCreateSerializer,
    ExerciceSerializer,
    RessourceSerializer
)
# IMPORTS MIS À JOUR POUR L'IA ET XCCM
from .json_utils import get_xccm_cours_structure, get_granule_content
from .ai_service import chat_with_context_stream


# ============================================================================
# HELPERS pour compatibilité avec Matière
# ============================================================================

def get_cours_etudiants(cours):
    """Récupère les étudiants inscrits à la matière du cours"""
    if hasattr(cours, 'matiere') and cours.matiere:
        return cours.matiere.etudiants_inscrits.all()
    return Etudiant.objects.none()

def is_etudiant_inscrit(cours, etudiant):
    """Vérifie si un étudiant est inscrit à la matière du cours"""
    if hasattr(cours, 'matiere') and cours.matiere:
        return cours.matiere.etudiants_inscrits.filter(pk=etudiant.pk).exists()
    return False

# ============================================================================
# VIEWSET COURS
# ============================================================================

class CoursViewSet(viewsets.ModelViewSet):
    """
    ViewSet complet pour gérer les cours
    """
    
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CoursCreateSerializer
        elif self.action == 'retrieve':
            return CoursDetailSerializer
        return CoursListSerializer
    
    def get_queryset(self):
        queryset = Cours.objects.select_related('matiere', 'enseignant__utilisateur').all()
        user = self.request.user
        
        # 1. Si Enseignant -> Voir les cours des matières où il est enseignant
        if hasattr(user, 'profil_enseignant'):
            ens = user.profil_enseignant
            queryset = queryset.filter(
                Q(enseignant=ens) |
                Q(matiere__enseignant=ens) |
                Q(matiere__enseignants=ens)
            ).distinct()
            
        # 2. Si Etudiant -> Voir les cours des MATIÈRES où il est inscrit
        elif hasattr(user, 'profil_etudiant'):
            matieres_suivies = user.profil_etudiant.matieres_suivies.all()
            queryset = queryset.filter(matiere__in=matieres_suivies)
        
        else:
             # Admin ou inconnu -> Voir tout ou rien
             if not user.is_staff:
                 return Cours.objects.none()
        
        # Filtrer par Matière spécifique (si demandé par le frontend)
        matiere_id = self.request.query_params.get('matiere_id')
        if matiere_id:
            queryset = queryset.filter(matiere__pk=matiere_id)
        
        # Filtrer par recherche
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(titre__icontains=search) | 
                Q(description__icontains=search)
            )
        
        return queryset.order_by('-date_creation')
    
    def create(self, request, *args, **kwargs):
        """POST /api/v1/cours/ - Création manuelle (titre + description)"""
        try:
            enseignant = Enseignant.objects.get(utilisateur=request.user)
        except Enseignant.DoesNotExist:
            return Response({'message': 'Seul un enseignant peut créer un cours.'}, status=status.HTTP_403_FORBIDDEN)

        titre = request.data.get('titre', '').strip()
        description = request.data.get('description', '').strip()

        if not titre:
            return Response({'titre': ['Ce champ est obligatoire.']}, status=status.HTTP_400_BAD_REQUEST)

        cours = Cours.objects.create(
            enseignant=enseignant,
            titre=titre,
            description=description,
            est_publie=False,
        )

        serializer = CoursDetailSerializer(cours, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def retrieve(self, request, *args, **kwargs):
        """GET /api/v1/cours/{id}/ - Détail d'un cours"""
        cours = self.get_object()
        serializer = self.get_serializer(cours)
        
        data = serializer.data
        data['nb_etudiants'] = get_cours_etudiants(cours).count()
        
        # Vérifier si étudiant inscrit
        try:
            etudiant = Etudiant.objects.get(utilisateur=request.user)
            data['est_inscrit'] = is_etudiant_inscrit(cours, etudiant)
        except Etudiant.DoesNotExist:
            data['est_inscrit'] = False
        
        # Vérifier si propriétaire
        try:
            enseignant = Enseignant.objects.get(utilisateur=request.user)
            data['est_proprietaire'] = (cours.enseignant.pk == enseignant.pk)
        except Enseignant.DoesNotExist:
            data['est_proprietaire'] = False
        
        return Response(data)
    
    def update(self, request, *args, **kwargs):
        """PUT /api/v1/cours/{id}/ - Modifier un cours"""
        cours = self.get_object()
        
        try:
            enseignant = Enseignant.objects.get(utilisateur=request.user)
            if cours.enseignant.pk != enseignant.pk:
                return Response(
                    {'error': 'Vous n\'êtes pas le propriétaire de ce cours'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Enseignant.DoesNotExist:
            return Response(
                {'error': 'Seul l\'enseignant propriétaire peut modifier ce cours'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        partial = kwargs.pop('partial', False)
        serializer = CoursCreateSerializer(cours, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        output_serializer = CoursDetailSerializer(cours, context={'request': request})
        
        return Response({
            'message': 'Cours modifié avec succès',
            'cours': output_serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """DELETE /api/v1/cours/{id}/ - Supprimer un cours"""
        cours = self.get_object()
        
        try:
            enseignant = Enseignant.objects.get(utilisateur=request.user)
            if cours.enseignant.pk != enseignant.pk:
                return Response(
                    {'error': 'Vous n\'êtes pas le propriétaire de ce cours'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Enseignant.DoesNotExist:
            return Response(
                {'error': 'Seul l\'enseignant propriétaire peut supprimer ce cours'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            cours.delete()
            return Response({
                'message': 'Cours supprimé avec succès'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de la suppression : {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def etudiants(self, request, pk=None):
        """GET /api/v1/cours/{id}/etudiants/ - Liste étudiants"""
        cours = self.get_object()
        
        try:
            enseignant = Enseignant.objects.get(utilisateur=request.user)
            if cours.enseignant.pk != enseignant.pk:
                return Response(
                    {'error': 'Seul l\'enseignant du cours peut voir cette liste'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Enseignant.DoesNotExist:
            return Response(
                {'error': 'Seul l\'enseignant du cours peut voir cette liste'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        etudiants = get_cours_etudiants(cours)
        
        def get_user_name(user):
            if hasattr(user, 'nom'):
                return user.nom, user.prenom
            return user.last_name, user.first_name
        
        data = []
        for etudiant in etudiants:
            nom, prenom = get_user_name(etudiant.utilisateur)
            data.append({
                'id': str(etudiant.pk),
                'nom': nom,
                'prenom': prenom,
                'email': etudiant.utilisateur.email,
                'niveau': etudiant.niveau
            })
        
        return Response({
            'count': len(data),
            'etudiants': data
        })
    
    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """GET /api/v1/cours/{id}/documents/ - Documents du cours"""
        cours = self.get_object()
        
        documents = FichierSource.objects.filter(
            enseignant=cours.enseignant
        ).order_by('-date_upload')[:20]
        
        data = []
        for doc in documents:
            data.append({
                'id': str(doc.pk),
                'titre': doc.titre,
                'type_fichier': doc.type_fichier,
                'statut_traitement': doc.statut_traitement,
                'date_upload': doc.date_upload,
            })
        
        return Response({
            'count': len(data),
            'documents': data
        })
    
    @action(detail=True, methods=['get'])
    def contenu(self, request, pk=None):
        """GET /api/v1/cours/{id}/contenu/ - Structure complète du cours format XCCM"""
        cours = self.get_object()
        
        # Vérification des accès : enseignant autorisé (owner OU enseignant de la matière) OU étudiant inscrit
        is_teacher_allowed = False
        try:
            enseignant = Enseignant.objects.get(utilisateur=request.user)
            if cours.enseignant.pk == enseignant.pk:
                is_teacher_allowed = True
            elif cours.matiere and (
                cours.matiere.enseignant_id == enseignant.pk or
                cours.matiere.enseignants.filter(pk=enseignant.pk).exists()
            ):
                is_teacher_allowed = True
        except Enseignant.DoesNotExist:
            pass
            
        is_enrolled = False
        try:
            etudiant = Etudiant.objects.get(utilisateur=request.user)
            if is_etudiant_inscrit(cours, etudiant):
                is_enrolled = True
        except Etudiant.DoesNotExist:
            pass
            
        if not (is_teacher_allowed or is_enrolled) and not request.user.is_staff:
            return Response(
                {'error': 'Vous devez être inscrit à ce cours pour voir son contenu'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        # UTILISATION DE LA NOUVELLE FONCTION XCCM
        structure_complete = get_xccm_cours_structure(cours)
        
        return Response(structure_complete)

    @action(detail=True, methods=['post'], url_path='chat')
    def chat_ia(self, request, pk=None):
        """
        POST /api/v1/cours/{id}/chat/
        Route pour l'Assistant IA (Gemini). Renvoie la réponse en streaming (SSE).
        """
        cours = self.get_object()
        
        # Vérification des permissions
        try:
            est_autorise = False
            
            if hasattr(request.user, 'profil_enseignant'):
                ens = request.user.profil_enseignant
                if cours.enseignant == ens:
                    est_autorise = True
                elif cours.matiere and (
                    cours.matiere.enseignant_id == ens.pk or
                    cours.matiere.enseignants.filter(pk=ens.pk).exists()
                ):
                    est_autorise = True
            elif hasattr(request.user, 'profil_etudiant'):
                etudiant = Etudiant.objects.get(utilisateur=request.user)
                if is_etudiant_inscrit(cours, etudiant):
                    est_autorise = True
                    
            if not est_autorise and not request.user.is_staff:
                return Response({'error': 'Accès non autorisé à l\'assistant de ce cours.'}, status=status.HTTP_403_FORBIDDEN)
        except Exception:
            return Response({'error': 'Erreur de vérification des droits.'}, status=status.HTTP_403_FORBIDDEN)

        # Récupération des données du FrontEnd
        message = request.data.get('message')
        historique = request.data.get('history', [])
        
        if not message:
            return Response({'error': 'Le message est requis.'}, status=status.HTTP_400_BAD_REQUEST)

        # Générateur pour le streaming SSE
        def event_stream():
            try:
                for chunk in chat_with_context_stream(cours, message, historique):
                    # Format standard Server-Sent Events
                    chunk_propre = chunk.replace('\n', '\\n')
                    yield f"data: {chunk_propre}\n\n"
            except Exception as e:
                yield f"data: [ERREUR] {str(e)}\n\n"
            
            # Signal de fin pour le front
            yield "data: [DONE]\n\n"

        # Renvoyer la réponse en streaming
        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no' # Important pour Nginx/Docker
        return response

    @action(detail=True, methods=['get'])
    def ressources(self, request, pk=None):
        """GET /api/v1/cours/{id}/ressources/ - Liste des ressources du cours"""
        cours = self.get_object()
        ressources = Ressource.objects.filter(cours=cours)
        serializer = RessourceSerializer(ressources, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser], url_path='upload-resource')
    def upload_resource(self, request, pk=None):
        """POST /api/v1/cours/{id}/upload-resource/ - Pousser une image/ressource"""
        cours = self.get_object()
        
        try:
             enseignant = Enseignant.objects.get(utilisateur=request.user)
             if cours.enseignant.pk != enseignant.pk:
                 return Response({'error': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        except:
             return Response({'error': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)

        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'Aucun fichier fourni'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ressource = Ressource.objects.create(
                cours=cours,
                titre=request.data.get('titre', file_obj.name),
                fichier=file_obj,
                type_ressource='IMAGE'
            )
            return Response(RessourceSerializer(ressource, context={'request': request}).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def statistiques(self, request, pk=None):
        """GET /api/v1/cours/{id}/statistiques/ - Stats du cours"""
        cours = self.get_object()
        
        try:
            enseignant = Enseignant.objects.get(utilisateur=request.user)
            if cours.enseignant.pk != enseignant.pk:
                return Response(
                    {'error': 'Seul l\'enseignant du cours peut voir les statistiques'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Enseignant.DoesNotExist:
            return Response(
                {'error': 'Seul l\'enseignant du cours peut voir les statistiques'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        stats = {
            'cours_id': str(cours.pk),
            'cours_titre': cours.titre,
            'nb_etudiants': get_cours_etudiants(cours).count(),
            'nb_parties': cours.parties.count(),
            'nb_chapitres': sum(partie.chapitres.count() for partie in cours.parties.all()),
            'date_creation': cours.date_creation,
        }
        
        return Response(stats)

    @action(detail=True, methods=['post'], url_path='consulter-granule')
    def consulter_granule(self, request, pk=None):
        """POST /api/v1/cours/{id}/consulter-granule/ - Marquer un granulé comme consulté"""
        cours = self.get_object()
        granule_id = request.data.get('granule_id')
        
        if not granule_id:
            return Response({'error': 'granule_id est requis'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            etudiant = Etudiant.objects.get(utilisateur=request.user)
            if not is_etudiant_inscrit(cours, etudiant):
                return Response({'error': 'Vous devez être inscrit à ce cours'}, status=status.HTTP_403_FORBIDDEN)
                
            granule = Granule.objects.get(pk=granule_id)
            
            progression, created = Progression.objects.get_or_create(
                etudiant=etudiant,
                cours=cours,
                granule=granule
            )
            
            return Response({
                'message': 'Granulé marqué comme consulté',
                'created': created,
                'date_consultation': progression.date_consultation
            })
            
        except Etudiant.DoesNotExist:
            return Response({'error': 'Seuls les étudiants peuvent suivre leur progression'}, status=status.HTTP_403_FORBIDDEN)
        except Granule.DoesNotExist:
            return Response({'error': 'Granulé introuvable'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)











# # Author: Dilane PAFE
# # Fichier: xcsm/views_cours.py - API CRUD complète pour les Cours

# from rest_framework import viewsets, status
# from rest_framework.decorators import action
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
# from django.db.models import Q
# import uuid

# from .models import Cours, Enseignant, Etudiant, FichierSource, Granule, Exercice, Question, Reponse, Progression, Ressource
# from .serializers import (
#     CoursListSerializer, 
#     CoursDetailSerializer, 
#     CoursCreateSerializer,
#     ExerciceSerializer,
#     RessourceSerializer
# )
# # IMPORT MIS À JOUR ICI
# from .json_utils import get_xccm_cours_structure, get_granule_content


# # ============================================================================
# # HELPERS pour compatibilité avec Matière
# # ============================================================================

# def get_cours_etudiants(cours):
#     """Récupère les étudiants inscrits à la matière du cours"""
#     if hasattr(cours, 'matiere') and cours.matiere:
#         return cours.matiere.etudiants_inscrits.all()
#     return Etudiant.objects.none()

# def is_etudiant_inscrit(cours, etudiant):
#     """Vérifie si un étudiant est inscrit à la matière du cours"""
#     if hasattr(cours, 'matiere') and cours.matiere:
#         return cours.matiere.etudiants_inscrits.filter(pk=etudiant.pk).exists()
#     return False

# # ============================================================================
# # VIEWSET COURS
# # ============================================================================

# class CoursViewSet(viewsets.ModelViewSet):
#     """
#     ViewSet complet pour gérer les cours
#     """
    
#     permission_classes = [IsAuthenticated]
#     parser_classes = [MultiPartParser, FormParser, JSONParser]
    
#     def get_serializer_class(self):
#         if self.action == 'create':
#             return CoursCreateSerializer
#         elif self.action == 'retrieve':
#             return CoursDetailSerializer
#         return CoursListSerializer
    
#     def get_queryset(self):
#         queryset = Cours.objects.select_related('matiere', 'enseignant__utilisateur').all()
#         user = self.request.user
        
#         # 1. Si Enseignant -> Voir SES cours (via ses matières ou directement)
#         if hasattr(user, 'profil_enseignant'):
#             queryset = queryset.filter(enseignant=user.profil_enseignant)
            
#         # 2. Si Etudiant -> Voir les cours des MATIÈRES où il est inscrit
#         elif hasattr(user, 'profil_etudiant'):
#             matieres_suivies = user.profil_etudiant.matieres_suivies.all()
#             queryset = queryset.filter(matiere__in=matieres_suivies)
        
#         else:
#              # Admin ou inconnu -> Voir tout ou rien
#              if not user.is_staff:
#                  return Cours.objects.none()
        
#         # Filtrer par Matière spécifique (si demandé par le frontend)
#         matiere_id = self.request.query_params.get('matiere_id')
#         if matiere_id:
#             queryset = queryset.filter(matiere__pk=matiere_id)
        
#         # Filtrer par recherche
#         search = self.request.query_params.get('search')
#         if search:
#             queryset = queryset.filter(
#                 Q(titre__icontains=search) | 
#                 Q(description__icontains=search)
#             )
        
#         return queryset.order_by('-date_creation')
    
#     def create(self, request, *args, **kwargs):
#         """POST /api/v1/cours/ - Création manuelle"""
#         return Response({'message': 'Veuillez utiliser l\'upload de fichier pour créer un cours.'}, status=status.HTTP_400_BAD_REQUEST)
    
#     def retrieve(self, request, *args, **kwargs):
#         """GET /api/v1/cours/{id}/ - Détail d'un cours"""
#         cours = self.get_object()
#         serializer = self.get_serializer(cours)
        
#         data = serializer.data
#         data['nb_etudiants'] = get_cours_etudiants(cours).count()
        
#         # Vérifier si étudiant inscrit
#         try:
#             etudiant = Etudiant.objects.get(utilisateur=request.user)
#             data['est_inscrit'] = is_etudiant_inscrit(cours, etudiant)
#         except Etudiant.DoesNotExist:
#             data['est_inscrit'] = False
        
#         # Vérifier si propriétaire
#         try:
#             enseignant = Enseignant.objects.get(utilisateur=request.user)
#             data['est_proprietaire'] = (cours.enseignant.pk == enseignant.pk)
#         except Enseignant.DoesNotExist:
#             data['est_proprietaire'] = False
        
#         return Response(data)
    
#     def update(self, request, *args, **kwargs):
#         """PUT /api/v1/cours/{id}/ - Modifier un cours"""
#         cours = self.get_object()
        
#         try:
#             enseignant = Enseignant.objects.get(utilisateur=request.user)
#             if cours.enseignant.pk != enseignant.pk:
#                 return Response(
#                     {'error': 'Vous n\'êtes pas le propriétaire de ce cours'},
#                     status=status.HTTP_403_FORBIDDEN
#                 )
#         except Enseignant.DoesNotExist:
#             return Response(
#                 {'error': 'Seul l\'enseignant propriétaire peut modifier ce cours'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         partial = kwargs.pop('partial', False)
#         serializer = CoursCreateSerializer(cours, data=request.data, partial=partial)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
        
#         output_serializer = CoursDetailSerializer(cours, context={'request': request})
        
#         return Response({
#             'message': 'Cours modifié avec succès',
#             'cours': output_serializer.data
#         })
    
#     def destroy(self, request, *args, **kwargs):
#         """DELETE /api/v1/cours/{id}/ - Supprimer un cours"""
#         cours = self.get_object()
        
#         try:
#             enseignant = Enseignant.objects.get(utilisateur=request.user)
#             if cours.enseignant.pk != enseignant.pk:
#                 return Response(
#                     {'error': 'Vous n\'êtes pas le propriétaire de ce cours'},
#                     status=status.HTTP_403_FORBIDDEN
#                 )
#         except Enseignant.DoesNotExist:
#             return Response(
#                 {'error': 'Seul l\'enseignant propriétaire peut supprimer ce cours'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         try:
#             cours.delete()
#             return Response({
#                 'message': 'Cours supprimé avec succès'
#             }, status=status.HTTP_200_OK)
#         except Exception as e:
#             return Response(
#                 {'error': f'Erreur lors de la suppression : {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     @action(detail=True, methods=['get'])
#     def etudiants(self, request, pk=None):
#         """GET /api/v1/cours/{id}/etudiants/ - Liste étudiants"""
#         cours = self.get_object()
        
#         try:
#             enseignant = Enseignant.objects.get(utilisateur=request.user)
#             if cours.enseignant.pk != enseignant.pk:
#                 return Response(
#                     {'error': 'Seul l\'enseignant du cours peut voir cette liste'},
#                     status=status.HTTP_403_FORBIDDEN
#                 )
#         except Enseignant.DoesNotExist:
#             return Response(
#                 {'error': 'Seul l\'enseignant du cours peut voir cette liste'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         etudiants = get_cours_etudiants(cours)
        
#         def get_user_name(user):
#             if hasattr(user, 'nom'):
#                 return user.nom, user.prenom
#             return user.last_name, user.first_name
        
#         data = []
#         for etudiant in etudiants:
#             nom, prenom = get_user_name(etudiant.utilisateur)
#             data.append({
#                 'id': str(etudiant.pk),
#                 'nom': nom,
#                 'prenom': prenom,
#                 'email': etudiant.utilisateur.email,
#                 'niveau': etudiant.niveau
#             })
        
#         return Response({
#             'count': len(data),
#             'etudiants': data
#         })
    
#     @action(detail=True, methods=['get'])
#     def documents(self, request, pk=None):
#         """GET /api/v1/cours/{id}/documents/ - Documents du cours"""
#         cours = self.get_object()
        
#         documents = FichierSource.objects.filter(
#             enseignant=cours.enseignant
#         ).order_by('-date_upload')[:20]
        
#         data = []
#         for doc in documents:
#             data.append({
#                 'id': str(doc.pk),
#                 'titre': doc.titre,
#                 'type_fichier': doc.type_fichier,
#                 'statut_traitement': doc.statut_traitement,
#                 'date_upload': doc.date_upload,
#             })
        
#         return Response({
#             'count': len(data),
#             'documents': data
#         })
    
#     @action(detail=True, methods=['get'])
#     def contenu(self, request, pk=None):
#         """GET /api/v1/cours/{id}/contenu/ - Structure complète du cours format XCCM"""
#         cours = self.get_object()
        
#         # Vérification des accès : propriétaire OU inscrit
#         is_owner = False
#         try:
#             enseignant = Enseignant.objects.get(utilisateur=request.user)
#             if cours.enseignant.pk == enseignant.pk:
#                 is_owner = True
#         except Enseignant.DoesNotExist:
#             pass
            
#         is_enrolled = False
#         try:
#             etudiant = Etudiant.objects.get(utilisateur=request.user)
#             if is_etudiant_inscrit(cours, etudiant):
#                 is_enrolled = True
#         except Etudiant.DoesNotExist:
#             pass
            
#         if not (is_owner or is_enrolled) and not request.user.is_staff:
#             return Response(
#                 {'error': 'Vous devez être inscrit à ce cours pour voir son contenu'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
            
#         # UTILISATION DE LA NOUVELLE FONCTION XCCM
#         structure_complete = get_xccm_cours_structure(cours)
        
#         return Response(structure_complete)

#     @action(detail=True, methods=['get'])
#     def ressources(self, request, pk=None):
#         """GET /api/v1/cours/{id}/ressources/ - Liste des ressources du cours"""
#         cours = self.get_object()
#         ressources = Ressource.objects.filter(cours=cours)
#         serializer = RessourceSerializer(ressources, many=True, context={'request': request})
#         return Response(serializer.data)

#     @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser], url_path='upload-resource')
#     def upload_resource(self, request, pk=None):
#         """POST /api/v1/cours/{id}/upload-resource/ - Pousser une image/ressource"""
#         cours = self.get_object()
        
#         try:
#              enseignant = Enseignant.objects.get(utilisateur=request.user)
#              if cours.enseignant.pk != enseignant.pk:
#                  return Response({'error': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)
#         except:
#              return Response({'error': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)

#         file_obj = request.FILES.get('file')
#         if not file_obj:
#             return Response({'error': 'Aucun fichier fourni'}, status=status.HTTP_400_BAD_REQUEST)

#         try:
#             ressource = Ressource.objects.create(
#                 cours=cours,
#                 titre=request.data.get('titre', file_obj.name),
#                 fichier=file_obj,
#                 type_ressource='IMAGE'
#             )
#             return Response(RessourceSerializer(ressource, context={'request': request}).data, status=status.HTTP_201_CREATED)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     @action(detail=True, methods=['get'])
#     def statistiques(self, request, pk=None):
#         """GET /api/v1/cours/{id}/statistiques/ - Stats du cours"""
#         cours = self.get_object()
        
#         try:
#             enseignant = Enseignant.objects.get(utilisateur=request.user)
#             if cours.enseignant.pk != enseignant.pk:
#                 return Response(
#                     {'error': 'Seul l\'enseignant du cours peut voir les statistiques'},
#                     status=status.HTTP_403_FORBIDDEN
#                 )
#         except Enseignant.DoesNotExist:
#             return Response(
#                 {'error': 'Seul l\'enseignant du cours peut voir les statistiques'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         stats = {
#             'cours_id': str(cours.pk),
#             'cours_titre': cours.titre,
#             'nb_etudiants': get_cours_etudiants(cours).count(),
#             'nb_parties': cours.parties.count(),
#             'nb_chapitres': sum(partie.chapitres.count() for partie in cours.parties.all()),
#             'date_creation': cours.date_creation,
#         }
        
#         return Response(stats)

#     @action(detail=True, methods=['post'], url_path='consulter-granule')
#     def consulter_granule(self, request, pk=None):
#         """POST /api/v1/cours/{id}/consulter-granule/ - Marquer un granulé comme consulté"""
#         cours = self.get_object()
#         granule_id = request.data.get('granule_id')
        
#         if not granule_id:
#             return Response({'error': 'granule_id est requis'}, status=status.HTTP_400_BAD_REQUEST)
            
#         try:
#             etudiant = Etudiant.objects.get(utilisateur=request.user)
#             if not is_etudiant_inscrit(cours, etudiant):
#                 return Response({'error': 'Vous devez être inscrit à ce cours'}, status=status.HTTP_403_FORBIDDEN)
                
#             granule = Granule.objects.get(pk=granule_id)
            
#             progression, created = Progression.objects.get_or_create(
#                 etudiant=etudiant,
#                 cours=cours,
#                 granule=granule
#             )
            
#             return Response({
#                 'message': 'Granulé marqué comme consulté',
#                 'created': created,
#                 'date_consultation': progression.date_consultation
#             })
            
#         except Etudiant.DoesNotExist:
#             return Response({'error': 'Seuls les étudiants peuvent suivre leur progression'}, status=status.HTTP_403_FORBIDDEN)
#         except Granule.DoesNotExist:
#             return Response({'error': 'Granulé introuvable'}, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


















# """
# API CRUD complète pour les Cours - VERSION FINALE CORRIGÉE
# Compatible avec toutes les configurations de relations ManyToMany
# """

# from rest_framework import viewsets, status
# from rest_framework.decorators import action
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
# from django.db.models import Q
# import uuid

# from .models import Cours, Enseignant, Etudiant, FichierSource, Granule, Exercice, Question, Reponse, Progression, Ressource
# from .serializers import (
#     CoursListSerializer, 
#     CoursDetailSerializer, 
#     CoursCreateSerializer,
#     ExerciceSerializer,
#     RessourceSerializer
# )
# from .json_utils import get_cours_complete_structure, get_granule_content


# # ============================================================================
# # HELPERS pour compatibilité avec différentes configurations de modèles
# # ============================================================================

# # ============================================================================
# # HELPERS pour compatibilité avec Matière
# # ============================================================================

# def get_cours_etudiants(cours):
#     """Récupère les étudiants inscrits à la matière du cours"""
#     if cours.matiere:
#         return cours.matiere.etudiants_inscrits.all()
#     return Etudiant.objects.none()

# def is_etudiant_inscrit(cours, etudiant):
#     """Vérifie si un étudiant est inscrit à la matière du cours"""
#     if cours.matiere:
#         return cours.matiere.etudiants_inscrits.filter(pk=etudiant.pk).exists()
#     return False

# # ============================================================================
# # VIEWSET COURS
# # ============================================================================

# class CoursViewSet(viewsets.ModelViewSet):
#     """
#     ViewSet complet pour gérer les cours
#     """
    
#     permission_classes = [IsAuthenticated]
#     parser_classes = [MultiPartParser, FormParser, JSONParser]
    
#     def get_serializer_class(self):
#         if self.action == 'create':
#             return CoursCreateSerializer
#         elif self.action == 'retrieve':
#             return CoursDetailSerializer
#         return CoursListSerializer
    
#     def get_queryset(self):
#         queryset = Cours.objects.select_related('matiere', 'enseignant__utilisateur').all()
#         user = self.request.user
        
#         # 1. Si Enseignant -> Voir SES cours (via ses matières ou directement)
#         if hasattr(user, 'profil_enseignant'):
#             queryset = queryset.filter(enseignant=user.profil_enseignant)
            
#         # 2. Si Etudiant -> Voir les cours des MATIÈRES où il est inscrit
#         elif hasattr(user, 'profil_etudiant'):
#             # On récupère les matières suivies
#             matieres_suivies = user.profil_etudiant.matieres_suivies.all()
#             queryset = queryset.filter(matiere__in=matieres_suivies)
        
#         else:
#              # Admin ou inconnu -> Voir tout ou rien
#              if not user.is_staff:
#                  return Cours.objects.none()
        
#         # Filtrer par Matière spécifique (si demandé par le frontend)
#         matiere_id = self.request.query_params.get('matiere_id')
#         if matiere_id:
#             queryset = queryset.filter(matiere__pk=matiere_id)
        
#         # Filtrer par recherche
#         search = self.request.query_params.get('search')
#         if search:
#             queryset = queryset.filter(
#                 Q(titre__icontains=search) | 
#                 Q(description__icontains=search)
#             )
        
#         return queryset.order_by('-date_creation')
    
#     def create(self, request, *args, **kwargs):
#         """POST /api/v1/cours/ - Création manuelle (Deprecated / Upload Only?)"""
#         # La création passe normalement par l'upload de fichier qui crée le cours.
#         # Mais si on veut créer un cours vide:
#         return Response({'message': 'Veuillez utiliser l\'upload de fichier pour créer un cours.'}, status=status.HTTP_400_BAD_REQUEST)
    
#     def retrieve(self, request, *args, **kwargs):
#         """GET /api/v1/cours/{id}/ - Détail d'un cours"""
#         cours = self.get_object()
#         serializer = self.get_serializer(cours)
        
#         data = serializer.data
#         data['nb_etudiants'] = get_cours_etudiants(cours).count()
        
#         # Vérifier si étudiant inscrit
#         try:
#             etudiant = Etudiant.objects.get(utilisateur=request.user)
#             data['est_inscrit'] = is_etudiant_inscrit(cours, etudiant)
#         except Etudiant.DoesNotExist:
#             data['est_inscrit'] = False
        
#         # Vérifier si propriétaire
#         try:
#             enseignant = Enseignant.objects.get(utilisateur=request.user)
#             data['est_proprietaire'] = (cours.enseignant.pk == enseignant.pk)
#         except Enseignant.DoesNotExist:
#             data['est_proprietaire'] = False
        
#         return Response(data)
    
#     def update(self, request, *args, **kwargs):
#         """PUT /api/v1/cours/{id}/ - Modifier un cours"""
#         cours = self.get_object()
        
#         try:
#             enseignant = Enseignant.objects.get(utilisateur=request.user)
#             if cours.enseignant.pk != enseignant.pk:
#                 return Response(
#                     {'error': 'Vous n\'êtes pas le propriétaire de ce cours'},
#                     status=status.HTTP_403_FORBIDDEN
#                 )
#         except Enseignant.DoesNotExist:
#             return Response(
#                 {'error': 'Seul l\'enseignant propriétaire peut modifier ce cours'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         partial = kwargs.pop('partial', False)
#         serializer = CoursCreateSerializer(cours, data=request.data, partial=partial)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
        
#         output_serializer = CoursDetailSerializer(cours, context={'request': request})
        
#         return Response({
#             'message': 'Cours modifié avec succès',
#             'cours': output_serializer.data
#         })
    
#     def destroy(self, request, *args, **kwargs):
#         """DELETE /api/v1/cours/{id}/ - Supprimer un cours"""
#         cours = self.get_object()
        
#         try:
#             enseignant = Enseignant.objects.get(utilisateur=request.user)
#             if cours.enseignant.pk != enseignant.pk:
#                 return Response(
#                     {'error': 'Vous n\'êtes pas le propriétaire de ce cours'},
#                     status=status.HTTP_403_FORBIDDEN
#                 )
#         except Enseignant.DoesNotExist:
#             return Response(
#                 {'error': 'Seul l\'enseignant propriétaire peut supprimer ce cours'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         try:
#             cours.delete()
#             return Response({
#                 'message': 'Cours supprimé avec succès'
#             }, status=status.HTTP_200_OK)
#         except Exception as e:
#             return Response(
#                 {'error': f'Erreur lors de la suppression : {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     # Inscription/Désinscription supprimées car gérées par MatièreView
    
#     @action(detail=True, methods=['get'])
#     def etudiants(self, request, pk=None):
#         """GET /api/v1/cours/{id}/etudiants/ - Liste étudiants"""
#         cours = self.get_object()
        
#         try:
#             enseignant = Enseignant.objects.get(utilisateur=request.user)
#             if cours.enseignant.pk != enseignant.pk:
#                 return Response(
#                     {'error': 'Seul l\'enseignant du cours peut voir cette liste'},
#                     status=status.HTTP_403_FORBIDDEN
#                 )
#         except Enseignant.DoesNotExist:
#             return Response(
#                 {'error': 'Seul l\'enseignant du cours peut voir cette liste'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         etudiants = get_cours_etudiants(cours)
        
#         def get_user_name(user):
#             if hasattr(user, 'nom'):
#                 return user.nom, user.prenom
#             return user.last_name, user.first_name
        
#         data = []
#         for etudiant in etudiants:
#             nom, prenom = get_user_name(etudiant.utilisateur)
#             data.append({
#                 'id': str(etudiant.pk),
#                 'nom': nom,
#                 'prenom': prenom,
#                 'email': etudiant.utilisateur.email,
#                 'niveau': etudiant.niveau
#             })
        
#         return Response({
#             'count': len(data),
#             'etudiants': data
#         })
    
#     @action(detail=True, methods=['get'])
#     def documents(self, request, pk=None):
#         """GET /api/v1/cours/{id}/documents/ - Documents du cours"""
#         cours = self.get_object()
        
#         documents = FichierSource.objects.filter(
#             enseignant=cours.enseignant
#         ).order_by('-date_upload')[:20]
        
#         data = []
#         for doc in documents:
#             data.append({
#                 'id': str(doc.pk),
#                 'titre': doc.titre,
#                 'type_fichier': doc.type_fichier,
#                 'statut_traitement': doc.statut_traitement,
#                 'date_upload': doc.date_upload,
#             })
        
#         return Response({
#             'count': len(data),
#             'documents': data
#         })
    
#     @action(detail=True, methods=['get'])
#     def contenu(self, request, pk=None):
#         """GET /api/v1/cours/{id}/contenu/ - Structure complète du cours"""
#         cours = self.get_object()
        
#         # Vérification des accès : propriétaire OU inscrit
#         is_owner = False
#         try:
#             enseignant = Enseignant.objects.get(utilisateur=request.user)
#             if cours.enseignant.pk == enseignant.pk:
#                 is_owner = True
#         except Enseignant.DoesNotExist:
#             pass
            
#         is_enrolled = False
#         try:
#             etudiant = Etudiant.objects.get(utilisateur=request.user)
#             if is_etudiant_inscrit(cours, etudiant):
#                 is_enrolled = True
#         except Etudiant.DoesNotExist:
#             pass
            
#         if not (is_owner or is_enrolled):
#             return Response(
#                 {'error': 'Vous devez être inscrit à ce cours pour voir son contenu'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
            
#         # Génération de la structure complète (logic from json_utils)
#         structure_complete = get_cours_complete_structure(cours)
        
#         return Response(structure_complete)

#         return Response(structure_complete)

#     @action(detail=True, methods=['get'])
#     def ressources(self, request, pk=None):
#         """GET /api/v1/cours/{id}/ressources/ - Liste des ressources du cours"""
#         cours = self.get_object()
        
#         # On récupère les ressources directement liées au cours
#         ressources = Ressource.objects.filter(cours=cours)
        
#         # OPTIONNEL: On récupère aussi les ressources des fichiers sources liés (si pas déjà liées au cours)
#         # Mais pour l'instant, restons simples : on suppose que le processing lie au cours ou que l'upload lie au cours.
#         # Amélioration : récupérer les ressources des fichiers sources de l'enseignant pour ce cours.
        
#         serializer = RessourceSerializer(ressources, many=True, context={'request': request})
#         return Response(serializer.data)

#     @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser], url_path='upload-resource')
#     def upload_resource(self, request, pk=None):
#         """POST /api/v1/cours/{id}/upload-resource/ - Pousser une image/ressource"""
#         cours = self.get_object()
        
#         # Vérification propriétaire
#         try:
#              enseignant = Enseignant.objects.get(utilisateur=request.user)
#              if cours.enseignant.pk != enseignant.pk:
#                  return Response({'error': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)
#         except:
#              return Response({'error': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)

#         file_obj = request.FILES.get('file')
#         if not file_obj:
#             return Response({'error': 'Aucun fichier fourni'}, status=status.HTTP_400_BAD_REQUEST)

#         try:
#             ressource = Ressource.objects.create(
#                 cours=cours,
#                 titre=request.data.get('titre', file_obj.name),
#                 fichier=file_obj,
#                 type_ressource='IMAGE' # Par défaut pour l'instant
#             )
#             # Note: RessourceSerializer expects 'instance' usually, or pass directly
#             return Response(RessourceSerializer(ressource, context={'request': request}).data, status=status.HTTP_201_CREATED)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     @action(detail=True, methods=['get'])
#     def statistiques(self, request, pk=None):
#         """GET /api/v1/cours/{id}/statistiques/ - Stats du cours"""
#         cours = self.get_object()
        
#         try:
#             enseignant = Enseignant.objects.get(utilisateur=request.user)
#             if cours.enseignant.pk != enseignant.pk:
#                 return Response(
#                     {'error': 'Seul l\'enseignant du cours peut voir les statistiques'},
#                     status=status.HTTP_403_FORBIDDEN
#                 )
#         except Enseignant.DoesNotExist:
#             return Response(
#                 {'error': 'Seul l\'enseignant du cours peut voir les statistiques'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         stats = {
#             'cours_id': str(cours.pk),
#             'cours_titre': cours.titre,
#             'nb_etudiants': get_cours_etudiants(cours).count(),
#             'nb_parties': cours.parties.count(),
#             'nb_chapitres': sum(partie.chapitres.count() for partie in cours.parties.all()),
#             'date_creation': cours.date_creation,
#         }
        
#         return Response(stats)

#     @action(detail=True, methods=['post'], url_path='consulter-granule')
#     def consulter_granule(self, request, pk=None):
#         """POST /api/v1/cours/{id}/consulter-granule/ - Marquer un granulé comme consulté"""
#         cours = self.get_object()
#         granule_id = request.data.get('granule_id')
        
#         if not granule_id:
#             return Response({'error': 'granule_id est requis'}, status=status.HTTP_400_BAD_REQUEST)
            
#         try:
#             etudiant = Etudiant.objects.get(utilisateur=request.user)
#             if not is_etudiant_inscrit(cours, etudiant):
#                 return Response({'error': 'Vous devez être inscrit à ce cours'}, status=status.HTTP_403_FORBIDDEN)
                
#             granule = Granule.objects.get(pk=granule_id)
            
#             progression, created = Progression.objects.get_or_create(
#                 etudiant=etudiant,
#                 cours=cours,
#                 granule=granule
#             )
            
#             return Response({
#                 'message': 'Granulé marqué comme consulté',
#                 'created': created,
#                 'date_consultation': progression.date_consultation
#             })
            
#         except Etudiant.DoesNotExist:
#             return Response({'error': 'Seuls les étudiants peuvent suivre leur progression'}, status=status.HTTP_403_FORBIDDEN)
#         except Granule.DoesNotExist:
#             return Response({'error': 'Granulé introuvable'}, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

