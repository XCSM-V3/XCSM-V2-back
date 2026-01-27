# # xcsm/admin.py
# from django.contrib import admin
# from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
# from .models import Utilisateur, Enseignant, Etudiant, Administrateur, FichierSource

# # ====================================================================
# # 1. CLASSES ADMIN POUR AFFICHAGE OPTIMISÉ
# # ====================================================================

# # Admin personnalisé pour le modèle Utilisateur (hérite des fonctionnalités de BaseUserAdmin)
# class UtilisateurAdmin(BaseUserAdmin):
#     # Champs affichés dans la liste d'aperçu de l'utilisateur
#     list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'type_compte')
    
#     # Ajout des champs spécifiques à notre modèle dans le formulaire d'édition
#     fieldsets = BaseUserAdmin.fieldsets + (
#         ('Informations Supplémentaires XCSM', {'fields': ('photo_url', 'type_compte')}),
#     )

# # Admin simple pour les profils métiers (pour la lisibilité)
# class EnseignantAdmin(admin.ModelAdmin):
#     list_display = ('utilisateur', 'specialite', 'departement')
#     search_fields = ('utilisateur__username', 'specialite')

# class EtudiantAdmin(admin.ModelAdmin):
#     list_display = ('utilisateur', 'matricule', 'niveau', 'filiere')
#     search_fields = ('matricule', 'utilisateur__username')

# class AdministrateurAdmin(admin.ModelAdmin):
#     list_display = ('utilisateur', 'role_admin')

# class FichierSourceAdmin(admin.ModelAdmin):
#     list_display = ('titre', 'enseignant', 'date_upload', 'statut_traitement')
#     list_filter = ('statut_traitement', 'date_upload')
#     search_fields = ('titre', 'enseignant__utilisateur__username')


# # ====================================================================
# # 2. ENREGISTREMENT DES MODÈLES (CRITIQUE pour le 404)
# # ====================================================================
# admin.site.register(Utilisateur, UtilisateurAdmin)
# admin.site.register(Enseignant, EnseignantAdmin)
# admin.site.register(Etudiant, EtudiantAdmin)
# admin.site.register(Administrateur, AdministrateurAdmin)
# admin.site.register(FichierSource, FichierSourceAdmin)








# xcsm/admin.py - Version améliorée avec prévisualisation JSON
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from .models import Utilisateur, Enseignant, Etudiant, Administrateur, FichierSource
from .models import Cours, Partie, Chapitre, Section, SousSection, Granule
from .utils import get_mongo_db

# Import tracking admin to register tracking models
from .admin_tracking import *


# ==============================================================================
# 1. ADMIN UTILISATEURS (Inchangé)
# ==============================================================================

class UtilisateurAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'type_compte')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Informations XCSM', {'fields': ('photo_url', 'type_compte')}),
    )

class EnseignantAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'specialite', 'departement')
    search_fields = ('utilisateur__username', 'specialite')

class EtudiantAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'matricule', 'niveau', 'filiere')
    search_fields = ('matricule', 'utilisateur__username')

class AdministrateurAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'role_admin')


# ==============================================================================
# 2. ADMIN FICHIER SOURCE - AVEC PRÉVISUALISATION JSON
# ==============================================================================

class FichierSourceAdmin(admin.ModelAdmin):
    list_display = ('titre', 'enseignant', 'date_upload', 'statut_badge', 'preview_json_link')
    list_filter = ('statut_traitement', 'date_upload')
    search_fields = ('titre', 'enseignant__utilisateur__username')
    readonly_fields = ('mongo_transforme_id', 'preview_json_structure')
    
    def statut_badge(self, obj):
        """Affiche un badge coloré pour le statut."""
        colors = {
            'TRAITE': 'green',
            'EN_ATTENTE': 'orange',
            'ERREUR': 'red'
        }
        color = colors.get(obj.statut_traitement, 'gray')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color, obj.get_statut_traitement_display()
        )
    statut_badge.short_description = 'Statut'
    
    def preview_json_link(self, obj):
        """Lien vers la prévisualisation JSON MongoDB."""
        if obj.mongo_transforme_id:
            return format_html(
                '<a href="#" onclick="alert(\'Voir preview_json_structure ci-dessous\'); return false;" '
                'style="color:blue;">📊 Voir JSON</a>'
            )
        return "-"
    preview_json_link.short_description = 'JSON MongoDB'
    
    def preview_json_structure(self, obj):
        """Affiche un aperçu de la structure JSON stockée dans MongoDB."""
        if not obj.mongo_transforme_id:
            return format_html('<i>Aucune donnée MongoDB</i>')
        
        try:
            mongo_db = get_mongo_db()
            doc = mongo_db['fichiers_uploades'].find_one({"fichier_source_id": str(obj.id)})
            
            if not doc:
                return format_html('<i>Document MongoDB introuvable</i>')
            
            # Comptage des sections
            structure = doc.get('structure_json', {})
            nb_sections = len(structure.get('sections', []))
            
            # Affichage compact
            json_preview = f"""
            <div style="background:#f5f5f5; padding:10px; border-radius:5px;">
                <strong>📄 Structure JSON</strong><br>
                <code>MongoDB ID: {obj.mongo_transforme_id}</code><br>
                <code>Sections extraites: {nb_sections}</code><br>
                <code>Type: {doc.get('type_original', 'N/A')}</code><br>
                <code>Date traitement: {doc.get('date_traitement', 'N/A')}</code><br>
                <br>
                <small>💡 Utilisez MongoDB Compass pour voir le JSON complet</small>
            </div>
            """
            return format_html(json_preview)
            
        except Exception as e:
            return format_html('<span style="color:red;">❌ Erreur: {}</span>', str(e))
    
    preview_json_structure.short_description = 'Aperçu Structure JSON'


# ==============================================================================
# 3. ADMIN HIÉRARCHIE PÉDAGOGIQUE (Amélioré)
# ==============================================================================

class CoursAdmin(admin.ModelAdmin):
    list_display = ('titre', 'enseignant', 'est_publie', 'date_creation', 'nb_parties')
    list_filter = ('est_publie', 'date_creation')
    search_fields = ('titre', )
    
    def nb_parties(self, obj):
        return obj.parties.count()
    nb_parties.short_description = 'Parties'

class PartieAdmin(admin.ModelAdmin):
    list_display = ('titre', 'cours', 'numero', 'nb_chapitres')
    list_filter = ('cours',)
    ordering = ('cours', 'numero')
    
    def nb_chapitres(self, obj):
        return obj.chapitres.count()
    nb_chapitres.short_description = 'Chapitres'

class ChapitreAdmin(admin.ModelAdmin):
    list_display = ('titre', 'partie', 'numero', 'nb_sections')
    list_filter = ('partie__cours',)
    ordering = ('partie', 'numero')
    
    def nb_sections(self, obj):
        return obj.sections.count()
    nb_sections.short_description = 'Sections'

class SectionAdmin(admin.ModelAdmin):
    list_display = ('titre', 'chapitre', 'numero', 'nb_sous_sections')
    ordering = ('chapitre', 'numero')
    
    def nb_sous_sections(self, obj):
        return obj.sous_sections.count()
    nb_sous_sections.short_description = 'Sous-sections'

class SousSectionAdmin(admin.ModelAdmin):
    list_display = ('titre', 'section', 'numero', 'nb_granules')
    ordering = ('section', 'numero')
    
    def nb_granules(self, obj):
        return obj.granules.count()
    nb_granules.short_description = 'Granules'


# ==============================================================================
# 4. ADMIN GRANULE - AVEC APERÇU JSON
# ==============================================================================

class GranuleAdmin(admin.ModelAdmin):
    list_display = ('titre_court', 'sous_section', 'type_contenu', 'ordre', 'preview_mongo')
    list_filter = ('type_contenu', 'fichier_source')
    search_fields = ('titre', 'sous_section__titre')
    readonly_fields = ('mongo_contenu_id', 'preview_contenu_json')
    ordering = ('sous_section', 'ordre')
    
    def titre_court(self, obj):
        return obj.titre[:50] + "..." if len(obj.titre) > 50 else obj.titre
    titre_court.short_description = 'Titre'
    
    def preview_mongo(self, obj):
        """Indicateur de présence dans MongoDB."""
        if obj.mongo_contenu_id:
            return format_html('✅ <code>{}</code>', obj.mongo_contenu_id[:12] + "...")
        return "❌"
    preview_mongo.short_description = 'MongoDB'
    
    def preview_contenu_json(self, obj):
        """Affiche le contenu JSON du granule depuis MongoDB."""
        if not obj.mongo_contenu_id:
            return format_html('<i>Aucun contenu MongoDB</i>')
        
        try:
            from bson.objectid import ObjectId
            mongo_db = get_mongo_db()
            doc = mongo_db['granules'].find_one({"_id": ObjectId(obj.mongo_contenu_id)})
            
            if not doc:
                return format_html('<i>Granule MongoDB introuvable</i>')
            
            content_preview = doc.get('content', '')[:200]
            html_preview = doc.get('html', '')[:100]
            
            json_display = f"""
            <div style="background:#f9f9f9; padding:10px; border:1px solid #ddd;">
                <strong>📦 Contenu JSON</strong><br>
                <code>Type: {doc.get('type', 'N/A')}</code><br>
                <code>Contenu: {content_preview}...</code><br>
                <code>HTML: {html_preview}...</code><br>
            </div>
            """
            return format_html(json_display)
            
        except Exception as e:
            return format_html('<span style="color:red;">❌ {}</span>', str(e))
    
    preview_contenu_json.short_description = 'Aperçu Contenu JSON'


# ==============================================================================
# 5. ENREGISTREMENT DES MODÈLES
# ==============================================================================

# Utilisateurs
admin.site.register(Utilisateur, UtilisateurAdmin)
admin.site.register(Enseignant, EnseignantAdmin)
admin.site.register(Etudiant, EtudiantAdmin)
admin.site.register(Administrateur, AdministrateurAdmin)

# Ressources
admin.site.register(FichierSource, FichierSourceAdmin)

# Hiérarchie pédagogique
admin.site.register(Cours, CoursAdmin)
admin.site.register(Partie, PartieAdmin)
admin.site.register(Chapitre, ChapitreAdmin)
admin.site.register(Section, SectionAdmin)
admin.site.register(SousSection, SousSectionAdmin)
admin.site.register(Granule, GranuleAdmin)