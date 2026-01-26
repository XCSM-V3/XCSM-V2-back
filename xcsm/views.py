# from django.shortcuts import render
# # Create your views here.

# # xcsm/views.py
# from rest_framework import generics, status
# from rest_framework.response import Response
# from .serializers import FichierSourceSerializer
# from .processing import process_and_store_document
# from .permissions import IsEnseignant



# from rest_framework.parsers import MultiPartParser, FormParser # AJOUT CRITIQUE



# class DocumentUploadView(generics.CreateAPIView):
#     """
#     API pour l'upload de documents (PDF/DOCX) et le lancement du processus de transformation.
#     URL: /api/v1/documents/upload/
#     """
#     serializer_class = FichierSourceSerializer
#     permission_classes = [IsEnseignant] # Seuls les Enseignants peuvent accéder


#     # AJOUTER CETTE LIGNE : Indique à DRF et Swagger d'accepter les fichiers
#     parser_classes = (MultiPartParser, FormParser)


#     def perform_create(self, serializer):
#         user = self.request.user
        
#         # L'instance Enseignant est requise pour la clé étrangère
#         try:
#             enseignant = user.profil_enseignant
#         except Exception:
#             return Response(
#                 {"detail": "Profil enseignant introuvable."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
            
#         # 1. Sauvegarde du FichierSource (l'instance MySQL)
#         fichier_source_instance = serializer.save(enseignant=enseignant, statut_traitement='EN_ATTENTE')
        
#         # 2. Lancement du processus de traitement SYNCHRONE
#         # NOTE: Ceci est bloquant. En production, cela serait une tâche asynchrone (Celery)
#         success, message = process_and_store_document(fichier_source_instance)

#         if success:
#             # Réponse OK: le fichier est dans MongoDB
#             return Response(
#                 {
#                     "message": "Document uploadé et traitement initial terminé.",
#                     "document_id": fichier_source_instance.id,
#                     "mongo_id": fichier_source_instance.mongo_transforme_id
#                 },
#                 status=status.HTTP_201_CREATED
#             )
#         else:
#             # Réponse ERREUR: le parsing a échoué (PDF corrompu, etc.)
#             # On renvoie 200/201 car l'objet a été créé, mais avec un statut ERREUR
#             return Response(
#                 {
#                     "message": f"Document uploadé, mais traitement initial en échec: {message}",
#                     "document_id": fichier_source_instance.id,
#                     "statut": "ERREUR"
#                 },
#                 status=status.HTTP_202_ACCEPTED # Accepté mais traité avec erreur
#             )

















# # xcsm/views.py
# from rest_framework import generics, status
# from rest_framework.response import Response
# from rest_framework.parsers import MultiPartParser, FormParser
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.exceptions import PermissionDenied

# # Vos imports
# from .models import FichierSource
# from .serializers import FichierSourceSerializer
# from .permissions import IsEnseignant
# from .processing import process_and_store_document

# class DocumentUploadView(generics.CreateAPIView):
#     """
#     API pour l'upload de documents (PDF/DOCX) et le lancement du processus de transformation.
#     URL: /api/v1/documents/upload/
#     """
#     queryset = FichierSource.objects.all()
#     serializer_class = FichierSourceSerializer
#     permission_classes = []  # Authentification désactivée pour DEV # Sécurité stricte
#     parser_classes = (MultiPartParser, FormParser) # Pour gérer les fichiers

#     def perform_create(self, serializer):
#         # Cette méthode sert uniquement à attacher l'enseignant lors de la sauvegarde
#         user = self.request.user
#         try:
#             # On s'assure que l'utilisateur a bien un profil enseignant
#             enseignant = user.profil_enseignant
#         except Exception:
#             raise PermissionDenied("L'utilisateur connecté n'est pas un enseignant.")
            
#         # On sauvegarde juste l'instance dans MySQL
#         serializer.save(enseignant=enseignant, statut_traitement='EN_ATTENTE')

#     def create(self, request, *args, **kwargs):
#         # 1. Validation et Sauvegarde standard
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         self.perform_create(serializer)
        
#         # Récupération de l'instance créée
#         instance = serializer.instance
#         headers = self.get_success_headers(serializer.data)

#         # 2. AUTOMATISATION : Lancement immédiat du traitement
#         print(f"🚀 [API] Démarrage du traitement pour : {instance.titre}")
#         try:
#             succes, message = process_and_store_document(instance)
            
#             # 3. Construction de la réponse enrichie
#             response_data = serializer.data
#             response_data['traitement_automatique'] = {
#                 "succes": succes,
#                 "message": message
#             }
            
#             # Code 201 si tout est OK, 202 si upload OK mais traitement échoué
#             status_code = status.HTTP_201_CREATED if succes else status.HTTP_202_ACCEPTED
            
#             return Response(response_data, status=status_code, headers=headers)

#         except Exception as e:
#             # Filet de sécurité ultime
#             return Response(
#                 {
#                     "error": "Erreur serveur lors du traitement.", 
#                     "detail": str(e)
#                 }, 
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )



























# xcsm/views.py - Version complète avec consultation JSON
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView

from .models import FichierSource, Cours, Granule
from .serializers import FichierSourceSerializer
from .permissions import IsEnseignant
from .processing import process_and_store_document
from datetime import datetime
from .utils import get_mongo_db
from .json_utils import (
    get_fichier_json_structure, 
    get_granule_content,
    get_cours_complete_structure,
    search_in_granules,
    get_statistics
)


# ==============================================================================
# 1. UPLOAD DE DOCUMENTS (Existant - Amélioré)
# ==============================================================================

class DocumentUploadView(generics.CreateAPIView):
    """
    API pour l'upload de documents (PDF/DOCX) et le lancement du processus de transformation.
    URL: POST /api/v1/documents/upload/
    
    Corps de la requête:
        - titre (string): Titre du document
        - fichier_original (file): Fichier PDF ou DOCX
    
    Réponse:
        - document_id: UUID du fichier créé
        - mongo_id: ID MongoDB du document transformé
        - traitement_automatique: Résultat du traitement
    """
    queryset = FichierSource.objects.all()
    serializer_class = FichierSourceSerializer
    permission_classes = [IsAuthenticated]  # Authentification REQUISE pour avoir request.user
    parser_classes = (MultiPartParser, FormParser)

    def perform_create(self, serializer):
        user = self.request.user
        try:
            enseignant = user.profil_enseignant
        except Exception:
            raise PermissionDenied("L'utilisateur connecté n'est pas un enseignant.")
        
        serializer.save(enseignant=enseignant, statut_traitement='EN_ATTENTE')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        instance = serializer.instance
        headers = self.get_success_headers(serializer.data)

        print(f"🚀 [API] Upload reçu. Démarrage du traitement ASYNCHRONE (Celery) pour : {instance.titre}")
        
        # Lancement du traitement via Celery
        from .tasks import process_document_task
        process_document_task.delay(instance.id)
        
        # Réponse immédiate
        response_data = serializer.data
        response_data['message'] = "Fichier uploadé. Traitement en cours en arrière-plan."
        response_data['statut'] = "EN_ATTENTE"
        
        return Response(response_data, status=status.HTTP_202_ACCEPTED, headers=headers)
class DocumentUpdateStructureView(APIView):
    """
    Permet au professeur de corriger la structure (titres, granules) depuis l'éditeur.
    Reçoit une nouvelle `json_structure` et re-génère les granules.
    PUT /api/v1/documents/<uuid:pk>/structure/
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            fichier = FichierSource.objects.get(id=pk)
            # Vérification propriétaire
            if fichier.enseignant != request.user.profil_enseignant:
                return Response({"error": "Non autorisé"}, status=status.HTTP_403_FORBIDDEN)
            
            # 1. Préparation de la structure
            new_structure = request.data.get("json_structure")
            html_content = request.data.get("html_content")

            if html_content:
                # Si HTML fourni (depuis Tiptap), on le parse
                from .processing import parse_html_to_json_structure
                new_structure = parse_html_to_json_structure(html_content)
            
            if not new_structure:
                 return Response({"error": "Structure ou HTML manquant"}, status=status.HTTP_400_BAD_REQUEST)
            
            # 2. Mise à jour MongoDB avec Upsert (Pour gérer les nouveaux fichiers dummies)
            mongo_db = get_mongo_db()
            
            update_data = {
                "structure_json": new_structure, 
                "date_modification": datetime.now().isoformat()
            }
            
            # Si c'est une création (upsert), on ajoute les champs requis
            mongo_db['fichiers_uploades'].update_one(
                {"fichier_source_id": str(fichier.id)},
                {
                    "$set": update_data,
                    "$setOnInsert": {
                        "titre": fichier.titre,
                        "type_original": "HTML_EDIT",
                        "date_traitement": datetime.now().isoformat(),
                        "version": "2.0-JSON-EDITOR"
                    }
                },
                upsert=True
            )
            
            # Si le fichier était en attente (cas du dummy file), on le marque comme TRAITÉ
            if fichier.statut_traitement == 'EN_ATTENTE':
                fichier.statut_traitement = 'TRAITE'
                fichier.save()
            
            # Récupérer l'ID mongo s'il n'est pas encore lié (cas du dummy)
            if not fichier.mongo_transforme_id:
                doc = mongo_db['fichiers_uploades'].find_one({"fichier_source_id": str(fichier.id)})
                if doc:
                    fichier.mongo_transforme_id = str(doc['_id'])
                    fichier.save()

            # 3. Régénération des Granules MySQL/Mongo
            from .processing import split_and_create_granules
            
            # Récupération de l'ID du cours cible s'il est fourni
            target_course_id = request.data.get("course_id")
            
            split_and_create_granules(fichier, new_structure, target_course_id=target_course_id)

            return Response({"status": "Structure mise à jour et granules régénérés"})

        except FichierSource.DoesNotExist:
            return Response({"error": "Fichier introuvable"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# Dans xcsm/views.py, ajouter après DocumentUploadView

class DocumentListView(generics.ListAPIView):
    """
    Liste de tous les documents uploadés par l'enseignant connecté
    GET /api/v1/documents/
    """
    serializer_class = FichierSourceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # On retourne uniquement les fichiers de l'enseignant connecté
        try:
            return FichierSource.objects.filter(enseignant=self.request.user.profil_enseignant).order_by('-date_upload')
        except:
            return FichierSource.objects.none()

class DocumentDeleteView(generics.DestroyAPIView):
    """
    Supprimer un document (et ses granules associés en cascade)
    DELETE /api/v1/documents/<uuid:pk>/
    """
    queryset = FichierSource.objects.all()
    serializer_class = FichierSourceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Sécurité : on ne peut supprimer que ses propres fichiers
        try:
            return FichierSource.objects.filter(enseignant=self.request.user.profil_enseignant)
        except:
            return FichierSource.objects.none()
    
    
# ==============================================================================
# 2. CONSULTATION DE LA STRUCTURE JSON (NOUVEAU)
# ==============================================================================

class FichierJsonStructureView(APIView):
    """
    Récupère la structure JSON complète d'un fichier uploadé depuis MongoDB.
    URL: GET /api/v1/documents/<uuid:fichier_id>/json/
    
    Réponse:
        - structure_json: Structure hiérarchique complète
        - metadata: Informations sur le traitement
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, fichier_id):
        try:
            fichier = FichierSource.objects.get(id=fichier_id)
        except FichierSource.DoesNotExist:
            return Response(
                {"error": "Fichier introuvable"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Vérification des permissions
        try:
            if fichier.enseignant != request.user.profil_enseignant:
                return Response(
                    {"error": "Vous n'êtes pas propriétaire de ce fichier"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Exception:
             # Allowed for admins or if checks fail safely (dev mode)
             pass
        
        # Récupération du JSON depuis MongoDB
        json_structure = get_fichier_json_structure(fichier.id)
        
        # Si le fichier est en attente, on renvoie une structure vide mais avec le statut
        if not json_structure and fichier.statut_traitement == 'EN_ATTENTE':
             return Response({
                "fichier_info": {
                    "id": str(fichier.id),
                    "titre": fichier.titre,
                    "statut_traitement": fichier.statut_traitement, # Using proper name
                    "date_upload": fichier.date_upload
                },
                "json_structure": {}
            })

        if not json_structure:
            # Fallback if processing failed or not found
            return Response(
                {"error": "Structure JSON introuvable dans MongoDB"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        
        # IMPORTANT: Enrichir la structure JSON avec les vrais granule_id PostgreSQL
        # Cela permet au frontend de générer des QCM en utilisant les bons IDs
        if json_structure:
            try:
                from .models import Granule
                # Récupérer tous les granules liés à ce fichier DIRECTEMENT
                granules = Granule.objects.filter(
                    fichier_source=fichier
                ).select_related('sous_section__section__chapitre__partie')
                
                # Créer un mapping titre -> granule_id
                granule_map = {}
                for granule in granules:
                    # Utiliser le titre comme clé (peut être amélioré avec un hash du contenu)
                    granule_map[granule.titre] = str(granule.id)
                
                print(f"📊 Enrichissement: {len(granule_map)} granules trouvés pour le fichier {fichier.id}")
                
                # Fonction récursive pour enrichir la structure
                def enrich_structure(node):
                    if isinstance(node, dict):
                        # Si c'est un noeud avec un titre, essayer de trouver le granule_id
                        if 'titre' in node or 'title' in node or 'content' in node:
                            titre = node.get('titre') or node.get('title') or node.get('content', '')
                            # Tronquer le titre pour matcher avec les granules (max 45 chars + "...")
                            titre_court = titre[:45] + "..." if len(titre) > 45 else titre
                            
                            if titre in granule_map:
                                node['granule_id'] = granule_map[titre]
                            elif titre_court in granule_map:
                                node['granule_id'] = granule_map[titre_court]
                        
                        # Enrichir récursivement tous les enfants
                        for key, value in node.items():
                            if isinstance(value, (dict, list)):
                                enrich_structure(value)
                    elif isinstance(node, list):
                        for item in node:
                            enrich_structure(item)
                
                # Enrichir la structure complète
                enrich_structure(json_structure)
                
                # Compter combien de granule_id ont été ajoutés
                def count_enriched(node, count=[0]):
                    if isinstance(node, dict):
                        if 'granule_id' in node:
                            count[0] += 1
                        for value in node.values():
                            count_enriched(value, count)
                    elif isinstance(node, list):
                        for item in node:
                            count_enriched(item, count)
                    return count[0]
                
                enriched_count = count_enriched(json_structure)
                print(f"✅ {enriched_count} nœuds enrichis avec granule_id")
                
            except Exception as e:
                print(f"⚠️ Erreur lors de l'enrichissement des granule_id: {e}")
                import traceback
                traceback.print_exc()
                # Continue même si l'enrichissement échoue
        
        return Response({
            "fichier_info": {
                "id": str(fichier.id),
                "titre": fichier.titre,
                "statut_traitement": fichier.statut_traitement, # Standardized name
                "date_upload": fichier.date_upload
            },
            "json_structure": json_structure
        })


# ==============================================================================
# 3. CONSULTATION D'UN GRANULE INDIVIDUEL
# ==============================================================================

class GranuleDetailView(APIView):
    """
    Récupère le contenu JSON d'un granule spécifique depuis MongoDB.
    URL: GET /api/v1/granules/<uuid:granule_id>/
    
    Réponse:
        - granule_info: Métadonnées MySQL
        - contenu_json: Contenu complet depuis MongoDB
    """
    permission_classes = []  # Authentification désactivée pour DEV
    
    def get(self, request, granule_id):
        try:
            granule = Granule.objects.select_related(
                'sous_section__section__chapitre__partie__cours',
                'fichier_source'
            ).get(id=granule_id)
        except Granule.DoesNotExist:
            return Response(
                {"error": "Granule introuvable"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Récupération du contenu MongoDB
        contenu_json = get_granule_content(granule.mongo_contenu_id)
        
        return Response({
            "granule_info": {
                "id": str(granule.id),
                "titre": granule.titre,
                "type": granule.type_contenu,
                "ordre": granule.ordre,
                "sous_section": granule.sous_section.titre,
                "section": granule.sous_section.section.titre,
                "chapitre": granule.sous_section.section.chapitre.titre
            },
            "contenu_json": contenu_json
        })


# ==============================================================================
# 5. RECHERCHE DANS LES GRANULES
# ==============================================================================


# ==============================================================================
# 5. RECHERCHE DANS LES GRANULES
# ==============================================================================

class GranuleSearchView(APIView):
    """
    Recherche dans les contenus des granules MongoDB avec authentification et filtrage par rôle.
    URL: GET /api/v1/granules/search/?q=<terme>
    
    Query params:
        - q: Terme de recherche (requis)
        - cours_id (optional): Filtrer par cours spécifique
    
    Réponse:
        Liste des granules correspondants avec métadonnées enrichies
    """
    permission_classes = [IsAuthenticated]  # Authentification REQUISE
    
    def get(self, request):
        query = request.query_params.get('q', '')
        cours_id = request.query_params.get('cours_id', None)
        
        if not query:
            return Response(
                {"error": "Paramètre 'q' requis"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        
        # Déterminer les cours accessibles selon le rôle
        try:
            if hasattr(user, 'profil_enseignant'):
                # Enseignant : ses propres cours
                accessible_courses = Cours.objects.filter(enseignant=user.profil_enseignant)
                user_role = 'enseignant'
            elif hasattr(user, 'profil_etudiant'):
                # Étudiant : cours inscrits
                accessible_courses = user.profil_etudiant.cours_suivis.all()
                user_role = 'etudiant'
            else:
                return Response(
                    {"error": "Profil utilisateur invalide"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Exception as e:
            return Response(
                {"error": f"Erreur lors de la récupération du profil: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Filtrer par cours spécifique si demandé
        if cours_id:
            accessible_courses = accessible_courses.filter(id=cours_id)
        
        if not accessible_courses.exists():
            return Response({
                "query": query,
                "count": 0,
                "results": [],
                "message": "Aucun cours accessible"
            })
        
        # Récupérer les IDs des fichiers sources liés à ces cours
        fichier_ids = set()
        for cours in accessible_courses:
            # Parcourir la hiérarchie pour trouver les fichiers sources
            granules = Granule.objects.filter(
                sous_section__section__chapitre__partie__cours=cours
            ).values_list('fichier_source_id', flat=True).distinct()
            fichier_ids.update(granules)
        
        if not fichier_ids:
            return Response({
                "query": query,
                "count": 0,
                "results": [],
                "message": "Aucun contenu disponible"
            })
        
        # Rechercher dans MongoDB avec filtrage
        from .json_utils import search_in_granules_filtered
        mongo_results = search_in_granules_filtered(query, list(fichier_ids))
        
        # Enrichir les résultats avec métadonnées MySQL
        enriched_results = []
        for result in mongo_results:
            mongo_contenu_id = result.get('_id') or result.get('granule_id')
            
            try:
                granule = Granule.objects.select_related(
                    'sous_section__section__chapitre__partie__cours',
                    'sous_section__section__chapitre__partie__cours__enseignant__utilisateur',
                    'fichier_source'
                ).get(mongo_contenu_id=mongo_contenu_id)
                
                cours = granule.sous_section.section.chapitre.partie.cours
                
                enriched_results.append({
                    'granule_id': str(granule.id),
                    'mongo_id': mongo_contenu_id,
                    'titre': granule.titre,
                    'type_contenu': granule.type_contenu,
                    'ordre': granule.ordre,
                    'content_preview': result.get('content', '')[:200] + '...' if result.get('content') else '',
                    'cours': {
                        'id': str(cours.id),
                        'titre': cours.titre,
                        'code': cours.code,
                    },
                    'chemin_hierarchique': {
                        'partie': granule.sous_section.section.chapitre.partie.titre,
                        'chapitre': granule.sous_section.section.chapitre.titre,
                        'section': granule.sous_section.section.titre,
                        'sous_section': granule.sous_section.titre,
                    },
                    'enseignant': cours.enseignant.utilisateur.get_full_name() if cours.enseignant else 'N/A',
                    'source_pdf_page': granule.source_pdf_page,
                })
            except Granule.DoesNotExist:
                # Granule MongoDB existe mais pas dans MySQL (données incohérentes)
                continue
            except Exception as e:
                print(f"⚠️ Erreur lors de l'enrichissement du granule {mongo_contenu_id}: {e}")
                continue
        
        return Response({
            "query": query,
            "count": len(enriched_results),
            "user_role": user_role,
            "accessible_courses_count": accessible_courses.count(),
            "results": enriched_results
        })


# ==============================================================================
# 6. STATISTIQUES MONGODB
# ==============================================================================

class MongoStatisticsView(APIView):
    """
    Retourne des statistiques sur les données MongoDB.
    URL: GET /api/v1/statistics/mongodb/
    
    Réponse:
        - Nombre de documents
        - Nombre de granules
        - Nom de la base
    """
    permission_classes = []  # Authentification désactivée pour DEV
    
    def get(self, request):
        stats = get_statistics()
        
        return Response(stats)