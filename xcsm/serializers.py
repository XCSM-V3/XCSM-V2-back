# xcsm/serializers.py
"""
Serializers pour l'API XCSM
À créer ou remplacer complètement
"""

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import (
    Utilisateur, Enseignant, Etudiant, Administrateur,
    Matiere, Cours, Partie, Chapitre, Section, SousSection,
    FichierSource, Granule, Exercice, Question, Reponse, Progression, Ressource
)


# ============================================================================
# SERIALIZERS UTILISATEURS & PROFILS
# ============================================================================

class UtilisateurSerializer(serializers.ModelSerializer):
    """Serializer de base pour les utilisateurs"""
    
    class Meta:
        model = Utilisateur
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                  'type_compte', 'date_joined', 'last_login', 'photo_url']
        read_only_fields = ['id', 'date_joined', 'last_login']

class RegisterSerializer(serializers.ModelSerializer):
    """Serializer pour l'inscription"""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    nom = serializers.CharField(required=True, max_length=100)
    prenom = serializers.CharField(required=True, max_length=100)
    role = serializers.ChoiceField(choices=['enseignant', 'etudiant'], default='etudiant')
    
    class Meta:
        model = Utilisateur
        fields = ['email', 'password', 'password2', 'nom', 'prenom', 'role']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Les mots de passe ne correspondent pas"})
        
        if Utilisateur.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({"email": "Un utilisateur avec cet email existe déjà"})
        
        return attrs
    
    def create(self, validated_data):
        # Extraire les données
        password = validated_data.pop('password')
        password2 = validated_data.pop('password2')
        role = validated_data.pop('role')
        email = validated_data['email']
        
        # Mapper 'role' vers 'type_compte'
        role_map = {
            'enseignant': 'ENSEIGNANT',
            'etudiant': 'ETUDIANT',
            'admin': 'ADMIN'
        }
        type_compte = role_map.get(role, 'ETUDIANT')
        
        # Créer l'utilisateur AVEC username=email
        user = Utilisateur.objects.create_user(
            username=email,  # ← TRÈS IMPORTANT
            email=email,
            password=password,
            first_name=validated_data['prenom'],
            last_name=validated_data['nom'],
            type_compte=type_compte
        )
        
        # Créer le profil selon le rôle
        if type_compte == 'ENSEIGNANT':
            Enseignant.objects.create(
                utilisateur=user,
                specialite="Non spécifié",
                departement="Non spécifié"
            )
        elif type_compte == 'ETUDIANT':
            Etudiant.objects.create(
                utilisateur=user,
                matricule=f"ETU{user.id.hex[:8].upper()}",
                niveau="L1",
                filiere="Informatique"
            )
        elif type_compte == 'ADMIN':
            Administrateur.objects.create(
                utilisateur=user,
                role_admin="SuperAdmin",
                permissions="toutes"
            )
        
        return user

class EnseignantSerializer(serializers.ModelSerializer):
    """Serializer pour les enseignants"""
    utilisateur = UtilisateurSerializer(read_only=True)
    nom_complet = serializers.SerializerMethodField()
    
    class Meta:
        model = Enseignant
        fields = ['id', 'utilisateur', 'specialite', 'nom_complet']
    
    def get_nom_complet(self, obj):
        return f"{obj.utilisateur.prenom} {obj.utilisateur.nom}"


class EtudiantSerializer(serializers.ModelSerializer):
    """Serializer pour les étudiants"""
    utilisateur = UtilisateurSerializer(read_only=True)
    nom_complet = serializers.SerializerMethodField()
    
    class Meta:
        model = Etudiant
        fields = ['id', 'utilisateur', 'niveau', 'nom_complet']
    
    def get_nom_complet(self, obj):
        return f"{obj.utilisateur.prenom} {obj.utilisateur.nom}"



class RessourceSerializer(serializers.ModelSerializer):
    """Serializer pour les ressources (images, médias)"""
    fichier_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Ressource
        fields = ['id', 'titre', 'fichier', 'fichier_url', 'type_ressource', 'date_ajout']
        
    def get_fichier_url(self, obj):
        if obj.fichier:
            return obj.fichier.url
        return None

# ============================================================================
# SERIALIZERS COURS 
# ============================================================================


# ============================================================================
# SERIALIZERS MATIERE & COURS 
# ============================================================================

class MatiereSerializer(serializers.ModelSerializer):
    """Serializer pour la gestion des matières"""
    enseignant_nom = serializers.SerializerMethodField()
    nb_etudiants = serializers.SerializerMethodField()
    nb_cours = serializers.SerializerMethodField()
    est_inscrit = serializers.SerializerMethodField() # Pour l'étudiant
    
    class Meta:
        model = Matiere
        fields = [
            'id', 'titre', 'code', 'description', 'image', 'date_creation',
            'enseignant', 'enseignant_nom', 'nb_etudiants', 'nb_cours', 'est_inscrit'
        ]
        read_only_fields = ['id', 'date_creation', 'enseignant', 'code'] # Code généré ou géré par vue
        
    def get_enseignant_nom(self, obj):
        user = obj.enseignant.utilisateur
        return f"{user.first_name} {user.last_name}"
        
    def get_nb_etudiants(self, obj):
        return obj.etudiants_inscrits.count()
        
    def get_nb_cours(self, obj):
        return obj.cours_associes.count()

    def get_est_inscrit(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and hasattr(request.user, 'profil_etudiant'):
            return obj.etudiants_inscrits.filter(pk=request.user.profil_etudiant.pk).exists()
        return False
        
class MatiereCreateSerializer(serializers.ModelSerializer):
    """Pour la création : on laisse l'enseignant choisir le code"""
    class Meta:
        model = Matiere
        fields = ['titre', 'code', 'description', 'image']
        
    def validate_code(self, value):
        if Matiere.objects.filter(code=value).exists():
            raise serializers.ValidationError("Ce code matière est déjà utilisé.")
        return value

class CoursListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des cours (Désormais rattachés à une Matière)"""
    nb_parties = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    last_accessed = serializers.SerializerMethodField()
    code = serializers.ReadOnlyField(source='matiere.code', default="N/A")
    
    nb_etudiants = serializers.SerializerMethodField()
    enseignant_nom = serializers.SerializerMethodField()

    class Meta:
        model = Cours
        fields = [
            'id', 'titre', 'code', 'description', 'date_creation', 'matiere',
            'nb_parties', 'progress', 'last_accessed', 'nb_etudiants', 'enseignant_nom'
        ]
        read_only_fields = ['id', 'date_creation', 'matiere', 'nb_etudiants']

    def get_enseignant_nom(self, obj):
        if obj.enseignant and obj.enseignant.utilisateur:
             return f"{obj.enseignant.utilisateur.first_name} {obj.enseignant.utilisateur.last_name}"
        return "Enseignant Inconnu"

    def get_nb_etudiants(self, obj):
        if obj.matiere:
            return obj.matiere.etudiants_inscrits.count()
        return 0
    
    def get_nb_parties(self, obj):
        return obj.parties.count()

    def get_progress(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        try:
            from .models import Etudiant, Progression, Granule
            etudiant = Etudiant.objects.filter(utilisateur=request.user).first()
            if not etudiant: return 0
            
            total_granules = Granule.objects.filter(sous_section__section__chapitre__partie__cours=obj).count()
            if total_granules == 0: return 0
            
            completed_granules = Progression.objects.filter(etudiant=etudiant, cours=obj).count()
            return int((completed_granules / total_granules) * 100)
        except:
            return 0

    def get_last_accessed(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        try:
            from .models import Etudiant, Progression
            etudiant = Etudiant.objects.filter(utilisateur=request.user).first()
            if not etudiant: return None
            
            last_p = Progression.objects.filter(etudiant=etudiant, cours=obj).order_by('-date_consultation').first()
            return last_p.date_consultation if last_p else None
        except:
            return None

class CoursDetailSerializer(CoursListSerializer):
    """Serializer détaillé"""
    class Meta(CoursListSerializer.Meta):
        fields = CoursListSerializer.Meta.fields + ['description'] # Ensure all fields are present or just inherit logic

class CoursCreateSerializer(serializers.ModelSerializer):
    """
    Création de cours = Upload de fichier désormais.
    Ce serializer sert à valider les métadonnées de base si besoin,
    mais la logique principale passe par FichierSource.
    """
    class Meta:
        model = Cours
        fields = ['titre', 'description', 'est_publie']

#========================================================================
# SERIALIZERS DOCUMENTS & GRANULES
# ============================================================================

class FichierSourceSerializer(serializers.ModelSerializer):
    """Serializer pour les fichiers sources"""
    enseignant_nom = serializers.SerializerMethodField()
    taille_fichier = serializers.SerializerMethodField()
    type_fichier = serializers.SerializerMethodField()
    course_id = serializers.SerializerMethodField() # ID du cours généré
    
    class Meta:
        model = FichierSource
        fields = [
            'id', 'titre', 'fichier_original', 'type_fichier',
            'statut_traitement', 'date_upload', 'enseignant', 'matiere',
            'enseignant_nom', 'taille_fichier', 'mongo_transforme_id', 'course_id'
        ]
        read_only_fields = [
            'id', 'statut_traitement', 
            'date_upload', 'enseignant', 'mongo_transforme_id'
        ]
        extra_kwargs = {'matiere': {'required': True}} # Matière obligatoire à l'upload
    
    def get_course_id(self, obj):
        # Essayer de trouver le cours généré lié à ce fichier (via Matiere)
        # Note: Notre logique lie le Cours à la Matière, et le Cours au FichierSource?
        # Non, le modèle Cours n'a pas de lien explicite "fichier_source_id" dans ma modif précédente?
        # Ah, j'ai oublié d'ajouter un lien direct Cours <-> FichierSource ou Granule <-> FichierSource
        # Le modèle FichierSource a le lien "enseignant". 
        # Modèle Granule a "fichier_source".
        return None 
    
    def get_enseignant_nom(self, obj):
        if obj.enseignant:
            return f"{obj.enseignant.utilisateur.first_name} {obj.enseignant.utilisateur.last_name}"
        return None
    
    def get_taille_fichier(self, obj):
        if obj.fichier_original:
            try:
                size_bytes = obj.fichier_original.size
                if size_bytes < 1024: return f"{size_bytes} B"
                elif size_bytes < 1024 * 1024: return f"{size_bytes / 1024:.1f} KB"
                else: return f"{size_bytes / (1024 * 1024):.1f} MB"
            except: return "Unknown"
        return "0 B"

    def get_type_fichier(self, obj):
        if obj.fichier_original:
            name = obj.fichier_original.name.lower()
            if name.endswith('.pdf'): return 'PDF'
            if name.endswith('.docx'): return 'DOCX'
            if name.endswith('.txt'): return 'TXT'
        return 'AUTRE'


class GranuleSerializer(serializers.ModelSerializer):
    """Serializer pour les granules"""
    chemin_hierarchique = serializers.SerializerMethodField()
    
    class Meta:
        model = Granule
        fields = [
            'id', 'titre', 'type_contenu', 'ordre',
            'mongo_contenu_id', 'sous_section',
            'chemin_hierarchique'
        ]
    
    def get_chemin_hierarchique(self, obj):
        """Retourne le chemin complet"""
        ss = obj.sous_section
        s = ss.section
        c = s.chapitre
        p = c.partie
        cours = p.cours
        matiere = cours.matiere
        
        return {
            'matiere': matiere.titre,
            'cours': cours.titre,
            'partie': p.titre,
            'chapitre': c.titre,
            'section': s.titre,
            'sous_section': ss.titre
        }

class GranuleDetailSerializer(GranuleSerializer):
    """Serializer détaillé"""
    contenu = serializers.SerializerMethodField()
    cours_id = serializers.SerializerMethodField()
    
    class Meta(GranuleSerializer.Meta):
        fields = GranuleSerializer.Meta.fields + ['contenu', 'cours_id']
    
    def get_contenu(self, obj):
        from .json_utils import get_granule_content
        return get_granule_content(obj.mongo_contenu_id)
    
    def get_cours_id(self, obj):
        return str(obj.sous_section.section.chapitre.partie.cours.id)

# ============================================================================
# SERIALIZERS RECHERCHE
# ============================================================================

class SearchResultSerializer(serializers.Serializer):
    granule_id = serializers.UUIDField()
    titre = serializers.CharField()
    type_contenu = serializers.CharField()
    contenu_extrait = serializers.CharField()
    score = serializers.FloatField()
    chemin = serializers.DictField()

# ============================================================================
# SERIALIZERS EXERCICES
# ============================================================================

class ReponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reponse
        fields = ['id', 'texte', 'est_correcte', 'feedback', 'correspondance']

class QuestionSerializer(serializers.ModelSerializer):
    reponses = ReponseSerializer(many=True, read_only=True)
    class Meta:
        model = Question
        fields = ['id', 'enonce', 'type_question', 'point', 'ordre', 'reponses']

class ExerciceSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    class Meta:
        model = Exercice
        fields = ['id', 'titre', 'description', 'granule', 'cours', 'date_creation', 'difficulte', 'questions']
        read_only_fields = ['id', 'date_creation']
        
class ProgressionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Progression
        fields = ['id', 'etudiant', 'cours', 'granule', 'date_consultation']
        read_only_fields = ['id', 'date_consultation']
