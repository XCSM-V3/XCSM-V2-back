# Author: Dilane PAFE
# Fichier: xcsm/models.py

import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

# ==============================================================================
# 1. BLOC ACTEURS (UTILISATEURS) - Conforme au Diagramme de Classe
# ==============================================================================

class Utilisateur(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    photo_url = models.ImageField(upload_to='photos_profil/', null=True, blank=True, verbose_name="Photo URL")
    
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date Création")
    derniere_connexion = models.DateTimeField(null=True, blank=True, verbose_name="Dernière Connexion")

    ROLE_CHOICES = (
        ('ADMIN', 'Administrateur'),
        ('ENSEIGNANT', 'Enseignant'),
        ('ETUDIANT', 'Etudiant'),
    )
    type_compte = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name="Type de Compte")

    def __str__(self):
        return f"{self.username}"

class Enseignant(models.Model):
    utilisateur = models.OneToOneField(Utilisateur, on_delete=models.CASCADE, primary_key=True, related_name='profil_enseignant')
    specialite = models.CharField(max_length=100, verbose_name="Spécialité")
    departement = models.CharField(max_length=100, verbose_name="Département")

    def __str__(self):
        return f"Ens. {self.utilisateur.last_name} ({self.specialite})"

class Etudiant(models.Model):
    utilisateur = models.OneToOneField(Utilisateur, on_delete=models.CASCADE, primary_key=True, related_name='profil_etudiant')
    matricule = models.CharField(max_length=50, unique=True, verbose_name="Matricule")
    niveau = models.CharField(max_length=50, verbose_name="Niveau")
    filiere = models.CharField(max_length=100, verbose_name="Filière")

    def __str__(self):
        return f"Etu. {self.matricule}"

class Administrateur(models.Model):
    utilisateur = models.OneToOneField(Utilisateur, on_delete=models.CASCADE, primary_key=True, related_name='profil_admin')
    role_admin = models.CharField(max_length=100, verbose_name="Rôle Admin")
    permissions = models.TextField(null=True, blank=True, verbose_name="Liste Permissions")

    def __str__(self):
        return f"Admin {self.utilisateur.username}"

# ==============================================================================
# 2. BLOC RESSOURCES ET FICHIERS
# ==============================================================================

class FichierSource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enseignant = models.ForeignKey(Enseignant, on_delete=models.CASCADE, related_name="mes_fichiers")
    titre = models.CharField(max_length=255, verbose_name="Titre du document")
    fichier_original = models.FileField(upload_to='documents_bruts/', verbose_name="PDF Original")
    
    mongo_transforme_id = models.CharField(max_length=100, null=True, blank=True)
    
    statut_traitement = models.CharField(
        max_length=20, 
        choices=[('EN_ATTENTE', 'En attente'), ('TRAITE', 'Traité'), ('ERREUR', 'Erreur')],
        default='EN_ATTENTE'
    )
    
    matiere = models.ForeignKey('Matiere', on_delete=models.CASCADE, related_name="fichiers", null=True, blank=True)
    date_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.titre} ({self.statut_traitement})"

class Ressource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cours = models.ForeignKey('Cours', on_delete=models.CASCADE, related_name="ressources", null=True, blank=True)
    fichier_source = models.ForeignKey(FichierSource, on_delete=models.SET_NULL, null=True, blank=True, related_name="ressources_extraites")
    
    titre = models.CharField(max_length=255)
    fichier = models.ImageField(upload_to='ressources/', verbose_name="Fichier Média")
    type_ressource = models.CharField(max_length=50, default='IMAGE')
    date_ajout = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titre

# ==============================================================================
# 3. BLOC STRUCTURE PÉDAGOGIQUE
# ==============================================================================

class Matiere(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titre = models.CharField(max_length=200, verbose_name="Nom de la matière")
    code = models.CharField(max_length=50, unique=True, verbose_name="Code d'accès")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='matieres_images/', null=True, blank=True)
    
    enseignant = models.ForeignKey(Enseignant, on_delete=models.CASCADE, related_name="mes_matieres")
    etudiants_inscrits = models.ManyToManyField('Etudiant', related_name='matieres_suivies', blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # BUG CRITIQUE CORRIGÉ ICI (self.code au lieu de self.matiere.code)
        return f"{self.titre} ({self.code})"

class Cours(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name="cours_associes", null=True, blank=True)
    enseignant = models.ForeignKey(Enseignant, on_delete=models.CASCADE, related_name="mes_cours")
    
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='cours_images/', null=True, blank=True)
    est_publie = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titre

class Partie(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cours = models.ForeignKey(Cours, on_delete=models.CASCADE, related_name="parties")
    titre = models.CharField(max_length=200)
    numero = models.PositiveIntegerField()
    class Meta: ordering = ['numero']

class Chapitre(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partie = models.ForeignKey(Partie, on_delete=models.CASCADE, related_name="chapitres")
    titre = models.CharField(max_length=200)
    numero = models.PositiveIntegerField()
    class Meta: ordering = ['numero']

class Section(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chapitre = models.ForeignKey(Chapitre, on_delete=models.CASCADE, related_name="sections")
    titre = models.CharField(max_length=200)
    numero = models.PositiveIntegerField()
    class Meta: ordering = ['numero']

class SousSection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="sous_sections")
    titre = models.CharField(max_length=200)
    numero = models.PositiveIntegerField()
    class Meta: ordering = ['numero']

# ==============================================================================
# 4. LE GRANULE (EXTRAIT DU FICHIER TRANSFORMÉ)
# ==============================================================================

class Granule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sous_section = models.ForeignKey(SousSection, on_delete=models.CASCADE, related_name="granules")
    fichier_source = models.ForeignKey(FichierSource, on_delete=models.CASCADE, related_name="granules_extraits")
    
    titre = models.CharField(max_length=255)
    type_contenu = models.CharField(max_length=50, default='TEXTE')
    mongo_contenu_id = models.CharField(max_length=100)
    ordre = models.PositiveIntegerField(default=0)
    
    tags = models.ManyToManyField('Tag', blank=True, related_name='granules')
    source_pdf_page = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return self.titre

# ==============================================================================
# 5. ORGANISATION ET RECHERCHE
# ==============================================================================

class Categorie(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    def __str__(self): return self.titre

class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titre = models.CharField(max_length=50, unique=True)
    def __str__(self): return self.titre

class Organisation(models.Model):
    nom = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='logos_organisations/', null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.nom

# ==============================================================================
# 6. EXERCICES ET ÉVALUATIONS
# ==============================================================================

class Exercice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    granule = models.ForeignKey('Granule', on_delete=models.SET_NULL, null=True, blank=True, related_name="exercices")
    cours = models.ForeignKey('Cours', on_delete=models.CASCADE, related_name="exercices_globaux")
    date_creation = models.DateTimeField(auto_now_add=True)
    difficulte = models.IntegerField(choices=[(1, 'Facile'), (2, 'Moyen'), (3, 'Difficile')], default=1)
    def __str__(self): return self.titre

class Question(models.Model):
    TYPE_CHOICES = (
        ('QCM', 'QCM'), ('VRAI_FAUX', 'Vrai/Faux'), ('TROUS', 'Texte à trous'),
        ('ASSOCIATION', 'Association'), ('ORDRE', 'Mise en ordre'), ('OUVERTE', 'Question Ouverte'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exercice = models.ForeignKey(Exercice, on_delete=models.CASCADE, related_name="questions")
    enonce = models.TextField()
    type_question = models.CharField(max_length=20, choices=TYPE_CHOICES)
    point = models.FloatField(default=1.0)
    ordre = models.PositiveIntegerField(default=0)
    class Meta: ordering = ['ordre']
    def __str__(self): return f"{self.type_question} - {self.enonce[:50]}..."

class Reponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="reponses")
    texte = models.TextField()
    est_correcte = models.BooleanField(default=False)
    feedback = models.TextField(blank=True)
    correspondance = models.CharField(max_length=255, blank=True, null=True)
    def __str__(self): return f"{self.texte} ({'Vrai' if self.est_correcte else 'Faux'})"

# ==============================================================================
# 7. TRACKING ET ANALYTICS
# ==============================================================================

class Progression(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name="progressions")
    cours = models.ForeignKey(Cours, on_delete=models.CASCADE, related_name="progressions_etudiants")
    granule = models.ForeignKey(Granule, on_delete=models.CASCADE)
    date_consultation = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('etudiant', 'granule')
        verbose_name = "Progression"
        verbose_name_plural = "Progressions"

    def __str__(self):
        return f"{self.etudiant.utilisateur.username} - {self.granule.titre}"

# ==============================================================================
# 8. MODULE 4 : COLLABORATION ET NOTIFICATIONS
# ==============================================================================

class Commentaire(models.Model):
    TYPE_CHOICES = [
        ('comment', 'Commentaire'),
        ('suggestion', 'Suggestion'),
        ('question', 'Question'),
        ('correction', 'Correction')
    ]
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('rejected', 'Rejeté'),
        ('implemented', 'Implémenté')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auteur = models.ForeignKey('Utilisateur', on_delete=models.CASCADE, related_name='commentaires')
    granule = models.ForeignKey('Granule', on_delete=models.CASCADE, related_name='commentaires')
    cours = models.ForeignKey('Cours', on_delete=models.CASCADE, related_name='commentaires_cours')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='reponses_fil')
    
    type_commentaire = models.CharField(max_length=20, choices=TYPE_CHOICES, default='comment')
    contenu = models.TextField()
    
    statut = models.CharField(max_length=20, choices=STATUS_CHOICES, default='approved')
    is_pinned = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    upvotes = models.ManyToManyField('Utilisateur', related_name='upvotes_commentaires', blank=True)
    downvotes = models.ManyToManyField('Utilisateur', related_name='downvotes_commentaires', blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.type_commentaire}] {self.auteur.username} sur {self.granule.titre}"

class Notification(models.Model):
    TYPE_CHOICES = [
        ('new_comment', 'Nouveau Commentaire'),
        ('reply', 'Réponse'),
        ('upvote', 'Upvote'),
        ('suggestion_approved', 'Suggestion Approuvée'),
        ('suggestion_rejected', 'Suggestion Rejetée'),
        ('mention', 'Mention')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    destinataire = models.ForeignKey('Utilisateur', on_delete=models.CASCADE, related_name='notifications')
    type_notif = models.CharField(max_length=30, choices=TYPE_CHOICES)
    
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=255, null=True, blank=True)
    actor_name = models.CharField(max_length=100, null=True, blank=True)
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

















# # xcsm/models.py
# import uuid
# from django.db import models
# from django.contrib.auth.models import AbstractUser

# # ==============================================================================
# # BLOC ACTEURS (UTILISATEURS) - Conforme au Diagramme de Classe D_Classe.jpg
# # ==============================================================================

# class Utilisateur(AbstractUser):
#     """
#     Classe Mère correspondante à 'Utilisateur' sur le diagramme.
#     Hérite d'AbstractUser pour la gestion sécu (mot de passe, login, is_active).
#     """
#     # Attributs du Diagramme
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     # email, password, nom, prenom, date_creation, last_login, is_active sont gérés par AbstractUser
    
#     photo_url = models.ImageField(upload_to='photos_profil/', null=True, blank=True, verbose_name="Photo URL")
    
#     # Champs de timestamps explicites si le diagramme les demande distinctement de Django
#     date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date Création")
#     derniere_connexion = models.DateTimeField(null=True, blank=True, verbose_name="Dernière Connexion")

#     # Rôle pour faciliter le typage (même si on a des tables filles)
#     ROLE_CHOICES = (
#         ('ADMIN', 'Administrateur'),
#         ('ENSEIGNANT', 'Enseignant'),
#         ('ETUDIANT', 'Etudiant'),
#     )
#     type_compte = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name="Type de Compte")

#     def __str__(self):
#         return f"{self.username}"

# class Enseignant(models.Model):
#     """
#     Classe Fille : Enseignant
#     """
#     utilisateur = models.OneToOneField(Utilisateur, on_delete=models.CASCADE, primary_key=True, related_name='profil_enseignant')
    
#     # Attributs spécifiques du Diagramme
#     specialite = models.CharField(max_length=100, verbose_name="Spécialité")
#     departement = models.CharField(max_length=100, verbose_name="Département")

#     def __str__(self):
#         return f"Ens. {self.utilisateur.last_name} ({self.specialite})"

# class Etudiant(models.Model):
#     """
#     Classe Fille : Etudiant
#     """
#     utilisateur = models.OneToOneField(Utilisateur, on_delete=models.CASCADE, primary_key=True, related_name='profil_etudiant')
    
#     # Attributs spécifiques du Diagramme
#     matricule = models.CharField(max_length=50, unique=True, verbose_name="Matricule")
#     niveau = models.CharField(max_length=50, verbose_name="Niveau")
#     filiere = models.CharField(max_length=100, verbose_name="Filière")

#     def __str__(self):
#         return f"Etu. {self.matricule}"

# class Administrateur(models.Model):
#     """
#     Classe Fille : Administrateur
#     """
#     utilisateur = models.OneToOneField(Utilisateur, on_delete=models.CASCADE, primary_key=True, related_name='profil_admin')
    
#     # Attributs spécifiques du Diagramme
#     role_admin = models.CharField(max_length=100, verbose_name="Rôle Admin") # Ex: SuperAdmin, Moderateur
#     permissions = models.TextField(null=True, blank=True, verbose_name="Liste Permissions") # Stockage simple ou JSON

#     def __str__(self):
#         return f"Admin {self.utilisateur.username}"




# # ==============================================================================
# # 2. BLOC RESSOURCES (LOGIQUE MODIFIÉE : PONT VERS MONGODB)
# # ==============================================================================

# class FichierSource(models.Model):
#     """
#     Représente le fichier PDF uploadé par l'enseignant.
#     Sert de référence vers la version 'manipulable' (HTML/XML) stockée dans MongoDB.
#     """
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     enseignant = models.ForeignKey(Enseignant, on_delete=models.CASCADE, related_name="mes_fichiers")
    
#     # Métadonnées MySQL
#     titre = models.CharField(max_length=255, verbose_name="Titre du document")
    
#     # Le fichier brut original (PDF) est gardé sur le disque pour archivage/téléchargement
#     fichier_original = models.FileField(upload_to='documents_bruts/', verbose_name="PDF Original")
    
#     # CLÉ CRITIQUE VERS MONGODB (Collection "Fichiers Uploades")
#     # Une fois le PDF transformé en HTML/XML, on stocke son ID Mongo ici.
#     mongo_transforme_id = models.CharField(
#         max_length=100, 
#         null=True, 
#         blank=True, 
#         help_text="ID du document transformé (HTML/XML) dans la collection MongoDB 'Fichiers Uploades'"
#     )
    
#     statut_traitement = models.CharField(
#         max_length=20, 
#         choices=[('EN_ATTENTE', 'En attente'), ('TRAITE', 'Traité'), ('ERREUR', 'Erreur')],
#         default='EN_ATTENTE'
#     )
    
#     # NOUVEAU: Lien vers la matière (pour savoir où créer le cours après traitement)
#     matiere = models.ForeignKey('Matiere', on_delete=models.CASCADE, related_name="fichiers", null=True, blank=True)
    
#     date_upload = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.titre} ({self.statut_traitement})"

# class Ressource(models.Model):
#     """
#     Ressource (Image, Média) liée à un cours ou un document.
#     Stockée localement et accessible pour l'éditeur.
#     """
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     cours = models.ForeignKey('Cours', on_delete=models.CASCADE, related_name="ressources", null=True, blank=True)
#     fichier_source = models.ForeignKey(FichierSource, on_delete=models.SET_NULL, null=True, blank=True, related_name="ressources_extraites")
    
#     titre = models.CharField(max_length=255)
#     fichier = models.ImageField(upload_to='ressources/', verbose_name="Fichier Média")
#     type_ressource = models.CharField(max_length=50, default='IMAGE') # IMAGE, VIDEO, FILE
    
#     date_ajout = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return self.titre

# # ==============================================================================
# # 3. BLOC STRUCTURE PÉDAGOGIQUE
# # ==============================================================================

# class Matiere(models.Model):
#     """
#     [NOUVEAU] Conteneur principal des cours.
#     L'étudiant s'inscrit ici via un CODE.
#     """
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     titre = models.CharField(max_length=200, verbose_name="Nom de la matière")
#     code = models.CharField(max_length=50, unique=True, verbose_name="Code d'accès (défini par l'enseignant)")
#     description = models.TextField(blank=True)
#     image = models.ImageField(upload_to='matieres_images/', null=True, blank=True)
    
#     enseignant = models.ForeignKey(Enseignant, on_delete=models.CASCADE, related_name="mes_matieres")
    
#     # Inscriptions : L'étudiant s'inscrit à la MATIÈRE, pas au cours individuel
#     etudiants_inscrits = models.ManyToManyField(
#         'Etudiant', 
#         related_name='matieres_suivies', 
#         blank=True,
#         verbose_name="Étudiants inscrits"
#     )
    
#     date_creation = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.titre} ({self.matiere.code if self.matiere else 'Sans Matière'})"


# class Cours(models.Model):
#     """
#     Représente un Document traité (PDF/DOCX) devenu un Cours structuré.
#     Doit appartenir à une Matière.
#     """
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
#     # Lien Parent Obligatoire (Temporairement nullable pour migration)
#     matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name="cours_associes", null=True, blank=True)
    
#     # On garde l'enseignant pour accès direct facile, même si accessible via matiere
#     enseignant = models.ForeignKey(Enseignant, on_delete=models.CASCADE, related_name="mes_cours")
    
#     titre = models.CharField(max_length=200)
#     description = models.TextField(blank=True)
#     image = models.ImageField(upload_to='cours_images/', null=True, blank=True)
#     est_publie = models.BooleanField(default=False)
#     date_creation = models.DateTimeField(auto_now_add=True)

#     # Note: On supprime 'etudiants_inscrits' et 'code' ici car gérés par Matière désormais

#     def __str__(self):
#         return self.titre

# # ==============================================================================
# # 5. ORGANISATION ET RECHERCHE
# # ==============================================================================

# class Categorie(models.Model):
#     """
#     Catégorie pour organiser les contenus (ex: Mathématiques, Algèbre, etc.)
#     """
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     titre = models.CharField(max_length=100)
#     slug = models.SlugField(unique=True)

#     def __str__(self):
#         return self.titre

# class Tag(models.Model):
#     """
#     Étiquettes pour le filtrage transversal
#     """
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     titre = models.CharField(max_length=50, unique=True)
    
#     def __str__(self):
#         return self.titre


# # ==============================================================================
# # 6. EXERCICES ET ÉVALUATIONS
# # ==============================================================================

# class Exercice(models.Model):
#     """
#     Un exercice peut être lié à un granule ou autonome dans un cours.
#     """
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     titre = models.CharField(max_length=200)
#     description = models.TextField(blank=True)
    
#     # Lien optionnel vers un granule (contexte de l'exercice)
#     granule = models.ForeignKey('Granule', on_delete=models.SET_NULL, null=True, blank=True, related_name="exercices")
    
#     # Lien vers le cours (si exercice global)
#     cours = models.ForeignKey('Cours', on_delete=models.CASCADE, related_name="exercices_globaux")
    
#     date_creation = models.DateTimeField(auto_now_add=True)
#     difficulte = models.IntegerField(choices=[(1, 'Facile'), (2, 'Moyen'), (3, 'Difficile')], default=1)

#     def __str__(self):
#         return self.titre

# class Question(models.Model):
#     """
#     Question individuelle d'un exercice.
#     """
#     TYPE_CHOICES = (
#         ('QCM', 'QCM'),
#         ('VRAI_FAUX', 'Vrai/Faux'),
#         ('TROUS', 'Texte à trous'),
#         ('ASSOCIATION', 'Association'),
#         ('ORDRE', 'Mise en ordre'),
#         ('OUVERTE', 'Question Ouverte'),
#     )
    
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     exercice = models.ForeignKey(Exercice, on_delete=models.CASCADE, related_name="questions")
#     enonce = models.TextField()
#     type_question = models.CharField(max_length=20, choices=TYPE_CHOICES)
#     point = models.FloatField(default=1.0)
#     ordre = models.PositiveIntegerField(default=0)

#     class Meta:
#         ordering = ['ordre']

#     def __str__(self):
#         return f"{self.type_question} - {self.enonce[:50]}..."

# class Reponse(models.Model):
#     """
#     Réponse possible ou attendue pour une question.
#     """
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="reponses")
#     texte = models.TextField()
#     est_correcte = models.BooleanField(default=False)
#     feedback = models.TextField(blank=True, help_text="Explication affichée après réponse")
    
#     # Pour les questions d'association (A -> B)
#     correspondance = models.CharField(max_length=255, blank=True, null=True)

#     def __str__(self):
#         return f"{self.texte} ({'Vrai' if self.est_correcte else 'Faux'})"


# class Partie(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     cours = models.ForeignKey(Cours, on_delete=models.CASCADE, related_name="parties")
#     titre = models.CharField(max_length=200)
#     numero = models.PositiveIntegerField()

#     class Meta: ordering = ['numero']

# class Chapitre(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     partie = models.ForeignKey(Partie, on_delete=models.CASCADE, related_name="chapitres")
#     titre = models.CharField(max_length=200)
#     numero = models.PositiveIntegerField()

#     class Meta: ordering = ['numero']

# class Section(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     chapitre = models.ForeignKey(Chapitre, on_delete=models.CASCADE, related_name="sections")
#     titre = models.CharField(max_length=200)
#     numero = models.PositiveIntegerField()

#     class Meta: ordering = ['numero']

# class SousSection(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="sous_sections")
#     titre = models.CharField(max_length=200)
#     numero = models.PositiveIntegerField()

#     class Meta: ordering = ['numero']

# # ==============================================================================
# # 4. LE GRANULE (EXTRAIT DU FICHIER TRANSFORMÉ)
# # ==============================================================================

# class Granule(models.Model):
#     """
#     Unité atomique extraite du fichier transformé.
#     """
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     sous_section = models.ForeignKey(SousSection, on_delete=models.CASCADE, related_name="granules")
    
#     # Lien vers le fichier source transformé (La référence dont tu parlais)
#     fichier_source = models.ForeignKey(FichierSource, on_delete=models.CASCADE, related_name="granules_extraits")
    
#     titre = models.CharField(max_length=255)
#     type_contenu = models.CharField(max_length=50, default='TEXTE')
    
#     # ID du contenu spécifique (le petit bout de texte/html) dans la collection "Granules" de MongoDB
#     mongo_contenu_id = models.CharField(max_length=100, help_text="ID du fragment dans MongoDB")
    
#     ordre = models.PositiveIntegerField(default=0)
    
#     # NOUVEAU: Tags pour le filtrage
#     tags = models.ManyToManyField('Tag', blank=True, related_name='granules')
    
#     # Page source du PDF
#     source_pdf_page = models.PositiveIntegerField(null=True, blank=True, help_text="Numéro de page dans le PDF original")

#     class Meta:
#         ordering = ['ordre']

#     def __str__(self):
#         return self.titre
# class Organisation(models.Model):
#     """
#     Modèle pour gérer les organisations (écoles, universités, etc.)
#     """
#     nom = models.CharField(max_length=255)
#     description = models.TextField(blank=True)
#     logo = models.ImageField(upload_to='logos_organisations/', null=True, blank=True)
#     date_creation = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return self.nom

# class Progression(models.Model):
#     """
#     Suit la progression d'un étudiant dans un cours via les granules consultés.
#     """
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name="progressions")
#     cours = models.ForeignKey(Cours, on_delete=models.CASCADE, related_name="progressions_etudiants")
#     granule = models.ForeignKey(Granule, on_delete=models.CASCADE)
#     date_consultation = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         unique_together = ('etudiant', 'granule')
#         verbose_name = "Progression"
#         verbose_name_plural = "Progressions"

#     def __str__(self):
#         return f"{self.etudiant.utilisateur.username} - {self.granule.titre}"






# class Commentaire(models.Model):
#     """
#     MODULE 4 - Système de Collaboration (Aligné avec comments.types.ts)
#     """
#     TYPE_CHOICES = [
#         ('comment', 'Commentaire'),
#         ('suggestion', 'Suggestion'),
#         ('question', 'Question'),
#         ('correction', 'Correction')
#     ]
#     STATUS_CHOICES = [
#         ('pending', 'En attente'),
#         ('approved', 'Approuvé'),
#         ('rejected', 'Rejeté'),
#         ('implemented', 'Implémenté')
#     ]

#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
#     # Liaisons
#     auteur = models.ForeignKey('Utilisateur', on_delete=models.CASCADE, related_name='commentaires')
#     granule = models.ForeignKey('Granule', on_delete=models.CASCADE, related_name='commentaires')
#     cours = models.ForeignKey('Cours', on_delete=models.CASCADE, related_name='commentaires_cours')
#     parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='reponses_fil')
    
#     # Contenu et Typage
#     type_commentaire = models.CharField(max_length=20, choices=TYPE_CHOICES, default='comment')
#     contenu = models.TextField()
    
#     # Statuts et Modération
#     statut = models.CharField(max_length=20, choices=STATUS_CHOICES, default='approved')
#     is_pinned = models.BooleanField(default=False)
#     is_resolved = models.BooleanField(default=False)
    
#     # Dates
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     # Interactions (Votes)
#     upvotes = models.ManyToManyField('Utilisateur', related_name='upvotes_commentaires', blank=True)
#     downvotes = models.ManyToManyField('Utilisateur', related_name='downvotes_commentaires', blank=True)

#     class Meta:
#         ordering = ['-created_at']

#     def __str__(self):
#         return f"[{self.type_commentaire}] {self.auteur.username} sur {self.granule.titre}"


# class Notification(models.Model):
#     """
#     MODULE 4 - Système de Notifications (Aligné avec useNotifications)
#     """
#     TYPE_CHOICES = [
#         ('new_comment', 'Nouveau Commentaire'),
#         ('reply', 'Réponse'),
#         ('upvote', 'Upvote'),
#         ('suggestion_approved', 'Suggestion Approuvée'),
#         ('suggestion_rejected', 'Suggestion Rejetée'),
#         ('mention', 'Mention')
#     ]

#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     destinataire = models.ForeignKey('Utilisateur', on_delete=models.CASCADE, related_name='notifications')
#     type_notif = models.CharField(max_length=30, choices=TYPE_CHOICES)
    
#     title = models.CharField(max_length=255)
#     message = models.TextField()
#     link = models.CharField(max_length=255, null=True, blank=True)
#     actor_name = models.CharField(max_length=100, null=True, blank=True)
    
#     is_read = models.BooleanField(default=False)
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         ordering = ['-created_at']