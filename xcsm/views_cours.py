"""
API CRUD complète pour les Cours - VERSION FINALE CORRIGÉE
Compatible avec toutes les configurations de relations ManyToMany
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
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
from .json_utils import get_cours_complete_structure, get_granule_content
from .ai_service import generate_exercises_from_granule

# ============================================================================
# HELPERS pour compatibilité avec différentes configurations de modèles
# ============================================================================

def get_cours_etudiants(cours):
    """Récupère les étudiants d'un cours (compatible avec différentes relations)"""
    try:
        return cours.etudiants_inscrits.all()
    except AttributeError:
        try:
            return Etudiant.objects.filter(cours_suivis=cours)
        except:
            return Etudiant.objects.none()


def add_etudiant_to_cours(cours, etudiant):
    """Inscrit un étudiant à un cours"""
    try:
        cours.etudiants_inscrits.add(etudiant)
    except AttributeError:
        try:
            etudiant.cours_suivis.add(cours)
        except:
            pass


def remove_etudiant_from_cours(cours, etudiant):
    """Désinscrit un étudiant d'un cours"""
    try:
        cours.etudiants_inscrits.remove(etudiant)
    except AttributeError:
        try:
            etudiant.cours_suivis.remove(cours)
        except:
            pass


def is_etudiant_inscrit(cours, etudiant):
    """Vérifie si un étudiant est inscrit au cours"""
    try:
        return cours.etudiants_inscrits.filter(pk=etudiant.pk).exists()
    except AttributeError:
        try:
            return etudiant.cours_suivis.filter(pk=cours.pk).exists()
        except:
            return False


# ============================================================================
# VIEWSET COURS
# ============================================================================

class CoursViewSet(viewsets.ModelViewSet):
    """
    ViewSet complet pour gérer les cours
    """
    
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CoursCreateSerializer
        elif self.action == 'retrieve':
            return CoursDetailSerializer
        return CoursListSerializer
    
    def get_queryset(self):
        queryset = Cours.objects.select_related('enseignant__utilisateur').all()
        
        # Filtrer par enseignant
        enseignant_id = self.request.query_params.get('enseignant_id')
        if enseignant_id:
            queryset = queryset.filter(enseignant__pk=enseignant_id)
        
        # Filtrer par recherche
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(titre__icontains=search) | 
                Q(description__icontains=search) |
                Q(code__icontains=search)
            )
        
        return queryset.order_by('-date_creation')
    
    def create(self, request, *args, **kwargs):
        """POST /api/v1/cours/ - Créer un cours"""
        try:
            enseignant = Enseignant.objects.get(utilisateur=request.user)
        except Enseignant.DoesNotExist:
            return Response(
                {'error': 'Seuls les enseignants peuvent créer des cours'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Générer un code unique si non fourni
        code = serializer.validated_data.get('code')
        if not code:
            code = f"COURS-{uuid.uuid4().hex[:8].upper()}"
            while Cours.objects.filter(code=code).exists():
                code = f"COURS-{uuid.uuid4().hex[:8].upper()}"
        
        # Créer le cours
        cours = serializer.save(enseignant=enseignant, code=code)
        
        # Retourner avec serializer détaillé
        output_serializer = CoursDetailSerializer(cours, context={'request': request})
        
        return Response({
            'message': 'Cours créé avec succès',
            'cours': output_serializer.data
        }, status=status.HTTP_201_CREATED)
    
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
    
    # SUPPRIMER la méthode mes_cours du ViewSet (on la garde dans views_auth.py)
    # pour éviter les conflits d'URLs
    
    @action(detail=True, methods=['post'])
    def inscrire(self, request, pk=None):
        """POST /api/v1/cours/{id}/inscrire/ - S'inscrire"""
        cours = self.get_object()
        
        try:
            etudiant = Etudiant.objects.get(utilisateur=request.user)
        except Etudiant.DoesNotExist:
            return Response(
                {'error': 'Seuls les étudiants peuvent s\'inscrire à un cours'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if is_etudiant_inscrit(cours, etudiant):
            return Response(
                {'error': 'Vous êtes déjà inscrit à ce cours'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        add_etudiant_to_cours(cours, etudiant)
        
        return Response({
            'message': 'Inscription réussie',
            'cours_id': str(cours.pk),
            'cours_titre': cours.titre
        })
    
    @action(detail=True, methods=['post'])
    def desinscrire(self, request, pk=None):
        """POST /api/v1/cours/{id}/desinscrire/ - Se désinscrire"""
        cours = self.get_object()
        
        try:
            etudiant = Etudiant.objects.get(utilisateur=request.user)
        except Etudiant.DoesNotExist:
            return Response(
                {'error': 'Seuls les étudiants peuvent se désinscrire'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not is_etudiant_inscrit(cours, etudiant):
            return Response(
                {'error': 'Vous n\'êtes pas inscrit à ce cours'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        remove_etudiant_from_cours(cours, etudiant)
        
        return Response({
            'message': 'Désinscription réussie'
        })
    
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
        """GET /api/v1/cours/{id}/contenu/ - Structure complète du cours"""
        cours = self.get_object()
        
        # Vérification des accès : propriétaire OU inscrit
        is_owner = False
        try:
            enseignant = Enseignant.objects.get(utilisateur=request.user)
            if cours.enseignant.pk == enseignant.pk:
                is_owner = True
        except Enseignant.DoesNotExist:
            pass
            
        is_enrolled = False
        try:
            etudiant = Etudiant.objects.get(utilisateur=request.user)
            if is_etudiant_inscrit(cours, etudiant):
                is_enrolled = True
        except Etudiant.DoesNotExist:
            pass
            
        if not (is_owner or is_enrolled):
            return Response(
                {'error': 'Vous devez être inscrit à ce cours pour voir son contenu'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        # Génération de la structure complète (logic from json_utils)
        structure_complete = get_cours_complete_structure(cours)
        
        return Response(structure_complete)

        return Response(structure_complete)

    @action(detail=True, methods=['get'])
    def ressources(self, request, pk=None):
        """GET /api/v1/cours/{id}/ressources/ - Liste des ressources du cours"""
        cours = self.get_object()
        
        # On récupère les ressources directement liées au cours
        ressources = Ressource.objects.filter(cours=cours)
        
        # OPTIONNEL: On récupère aussi les ressources des fichiers sources liés (si pas déjà liées au cours)
        # Mais pour l'instant, restons simples : on suppose que le processing lie au cours ou que l'upload lie au cours.
        # Amélioration : récupérer les ressources des fichiers sources de l'enseignant pour ce cours.
        
        serializer = RessourceSerializer(ressources, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_resource(self, request, pk=None):
        """POST /api/v1/cours/{id}/upload-resource/ - Pousser une image/ressource"""
        cours = self.get_object()
        
        # Vérification propriétaire
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
                type_ressource='IMAGE' # Par défaut pour l'instant
            )
            # Note: RessourceSerializer expects 'instance' usually, or pass directly
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

    @action(detail=True, methods=['post'])
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


# ============================================================================
# VIEWSET EXERCICES
# ============================================================================

class ExerciceViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les exercices et leur génération par IA
    """
    queryset = Exercice.objects.all()
    serializer_class = ExerciceSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        POST /api/v1/exercices/generate/
        Génère des exercices à partir d'un granule.
        """
        granule_id = request.data.get('granule_id')
        type_question = request.data.get('type_question', 'QCM')
        count = int(request.data.get('count', 3))
        
        if not granule_id:
            return Response({'error': 'granule_id est requis'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            granule = Granule.objects.get(pk=granule_id)
            # Re-dérivation du cours via la hiérarchie
            cours = granule.sous_section.section.chapitre.partie.cours
            
            # 1. Récupérer le contenu réel du granule (MongoDB)
            from .json_utils import get_granule_content
            content_data = get_granule_content(granule.mongo_contenu_id)
            text_content = content_data.get('html_content', '') if isinstance(content_data, dict) else str(content_data)
            
            # Nettoyage HTML si nécessaire pour le prompt
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text_content, 'html.parser')
            clean_text = soup.get_text()
            
            # 2. Appeler le service d'IA
            print(f"🤖 Génération d'exercices IA pour le granule {granule.titre}...")
            from .ai_service import generate_exercises_from_granule
            questions_data = generate_exercises_from_granule(clean_text, type_question, count)
            
            # 3. Créer l'Exercice et les Questions/Réponses en base
            from django.db import transaction
            with transaction.atomic():
                exercice = Exercice.objects.create(
                    titre=request.data.get('titre', f"Exercice : {granule.titre}"),
                    description=request.data.get('description', f"Généré automatiquement à partir de : {granule.titre}"),
                    granule=granule,
                    cours=cours,
                    difficulte=int(request.data.get('difficulte', 1))
                )
                
                for i, q_item in enumerate(questions_data):
                    question = Question.objects.create(
                        exercice=exercice,
                        enonce=q_item.get('enonce'),
                        type_question=type_question,
                        point=1.0,
                        ordre=i
                    )
                    
                    for r_item in q_item.get('reponses', []):
                        Reponse.objects.create(
                            question=question,
                            texte=r_item.get('texte'),
                            est_correcte=r_item.get('est_correcte', False),
                            feedback=r_item.get('feedback', '')
                        )
            
            serializer = self.get_serializer(exercice)
            return Response({
                'message': 'Exercices générés avec succès',
                'exercice': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except Granule.DoesNotExist:
            return Response({'error': 'Granule non trouvé'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)