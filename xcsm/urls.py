"""
Configuration complète des endpoints XCSM - VERSION CORRIGÉE
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import des vues existantes
from .views import (
    DocumentUploadView,
    DocumentUpdateStructureView,
    DocumentListView,
    DocumentDeleteView,
    FichierJsonStructureView,
    GranuleSearchView,
    MongoStatisticsView,
)

# Import des vues granules
from .views_granules import (
    GranuleListView,
    GranuleDetailView as GranuleDetailManagementView,
)

# Import de la vue d'édition des granules
from .views_granule_edit import GranuleUpdateView

# Import de la vue d'édition en masse
from .views_bulk_edit import BulkEditContentView

# Import des vues de ressources
from .views_ressources import CoursRessourcesView, UploadRessourceView

# Import des vues de contenu hiérarchique
from .views_contenu import (
    CoursContentView,
    PartieContentView,
    ChapitreContentView,
    SectionContentView,
    SousSectionContentView,
)

# Import des vues d'authentification
from .views_auth import (
    register_view,
    login_view,
    logout_view,
    me_view,
    update_profile_view,
    change_password_view,
    mes_cours_view  # Vue séparée pour mes-cours
)

# Import du ViewSet Cours
from .views_cours import CoursViewSet, ExerciceViewSet

# Configuration du router pour les ViewSets
router = DefaultRouter()
router.register(r'cours', CoursViewSet, basename='cours')
router.register(r'exercices', ExerciceViewSet, basename='exercices')

# Configuration des URLs
urlpatterns = [
    # =========================================================================
    # AUTHENTIFICATION
    # =========================================================================
    path('auth/register/', register_view, name='register'),
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/me/', me_view, name='me'),
    path('auth/profile/', update_profile_view, name='update-profile'),
    path('auth/change-password/', change_password_view, name='change-password'),
    
    # =========================================================================
    # MES COURS (VUE SÉPARÉE)
    # =========================================================================
    path('cours/mes-cours/', mes_cours_view, name='mes-cours'),
    
    # =========================================================================
    # GESTION DES DOCUMENTS
    # =========================================================================
    path('documents/upload/', DocumentUploadView.as_view(), name='document-upload'),
    path('documents/', DocumentListView.as_view(), name='document-list'),
    path('documents/<uuid:pk>/', DocumentDeleteView.as_view(), name='document-delete'),
    path('documents/<uuid:pk>/structure/', DocumentUpdateStructureView.as_view(), name='document-structure-update'),
    path('documents/<uuid:fichier_id>/json/', FichierJsonStructureView.as_view(), 
         name='fichier-json-structure'),
    
    # =========================================================================
    # CONSULTATION DES GRANULES
    # =========================================================================
    path('granules/', GranuleListView.as_view(), name='granule-list'),
    path('granules/search/', GranuleSearchView.as_view(), name='granule-search'),
    path('granules/<uuid:granule_id>/', GranuleDetailManagementView.as_view(), 
         name='granule-management'),
    path('granules/<uuid:granule_id>/update/', GranuleUpdateView.as_view(), 
         name='granule-update'),
    
    # =========================================================================
    # AFFICHAGE DU CONTENU HIÉRARCHIQUE
    # =========================================================================
    path('contenu/cours/<uuid:cours_id>/', CoursContentView.as_view(), name='contenu-cours'),
    path('contenu/partie/<uuid:partie_id>/', PartieContentView.as_view(), name='contenu-partie'),
    path('contenu/chapitre/<uuid:chapitre_id>/', ChapitreContentView.as_view(), name='contenu-chapitre'),
    path('contenu/section/<uuid:section_id>/', SectionContentView.as_view(), name='contenu-section'),
    path('contenu/sous_section/<uuid:sous_section_id>/', SousSectionContentView.as_view(), name='contenu-sous-section'),
    
    # Édition en masse du contenu
    path('contenu/bulk-edit/', BulkEditContentView.as_view(), name='contenu-bulk-edit'),
    
    # =========================================================================
    # STATISTIQUES
    # =========================================================================
    path('statistics/mongodb/', MongoStatisticsView.as_view(), name='mongo-statistics'),
    
    # =========================================================================
    # RESSOURCES DE COURS (IMAGES, VIDÉOS, DOCUMENTS)
    # =========================================================================
    path('cours/<uuid:cours_id>/ressources/', CoursRessourcesView.as_view(), name='cours-ressources'),
    path('cours/<uuid:cours_id>/upload-resource/', UploadRessourceView.as_view(), name='cours-upload-resource'),
    
    # =========================================================================
    # ROUTER (COURS VIEWSET) - TOUTES LES AUTRES ACTIONS COURS
    # =========================================================================
    path('', include(router.urls)),
]