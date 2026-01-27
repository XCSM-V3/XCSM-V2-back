# xcsm/views_auth.py - VERSION CORRIGÉE
"""
VERSION FINALE CORRIGÉE - Compatible avec AbstractUser (first_name/last_name)
CORRECTION: Ajout de username=email lors de create_user()
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Utilisateur, Enseignant, Etudiant, Administrateur, Cours
from .serializers import RegisterSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """
    POST /api/auth/register/
    
    Body: {
        "email": "user@example.com",
        "nom": "Nom",
        "prenom": "Prénom",
        "password": "motdepasse",
        "password2": "motdepasse",
        "role": "enseignant" ou "etudiant"
    }
    """
    serializer = RegisterSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        with transaction.atomic():
            # ✅ CORRIGÉ : Ajouter username=email (OBLIGATOIRE pour AbstractUser)
            utilisateur = Utilisateur.objects.create_user(
                username=serializer.validated_data['email'],  # ← LIGNE AJOUTÉE
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password']
            )
            
            # ✅ CORRIGÉ : Utiliser first_name et last_name (champs d'AbstractUser)
            utilisateur.first_name = serializer.validated_data['prenom']
            utilisateur.last_name = serializer.validated_data['nom']
            
            # Mapper le rôle
            role = serializer.validated_data.get('role', 'etudiant')
            role_map = {
                'enseignant': 'ENSEIGNANT',
                'etudiant': 'ETUDIANT',
                'admin': 'ADMIN'
            }
            utilisateur.type_compte = role_map.get(role, 'ETUDIANT')
            utilisateur.save()
            
            # Créer le profil selon le rôle
            if role == 'enseignant':
                profil = Enseignant.objects.create(
                    utilisateur=utilisateur,
                    specialite='Non spécifié',
                    departement='Non spécifié'
                )
            else:  # etudiant
                profil = Etudiant.objects.create(
                    utilisateur=utilisateur,
                    matricule=f"ETU{str(utilisateur.id)[:8].upper()}",
                    niveau='Non spécifié',
                    filiere='Non spécifié'
                )
            
            # Générer les tokens JWT
            refresh = RefreshToken.for_user(utilisateur)
            
            return Response({
                'message': 'Inscription réussie',
                'user': {
                    'id': str(utilisateur.pk),
                    'email': utilisateur.email,
                    'nom': utilisateur.last_name,
                    'prenom': utilisateur.first_name,
                    'role': role,
                    'profil_id': str(profil.pk)
                },
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response(
            {'error': f'Erreur lors de l\'inscription: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    POST /api/auth/login/
    """
    email = request.data.get('email')
    password = request.data.get('password')
    
    if not email or not password:
        return Response(
            {'error': 'Email et mot de passe requis'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Authentifier l'utilisateur
    utilisateur = authenticate(request, username=email, password=password)
    
    if utilisateur is None:
        return Response(
            {'error': 'Email ou mot de passe incorrect'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    if not utilisateur.is_active:
        return Response(
            {'error': 'Ce compte est désactivé'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Déterminer le rôle et récupérer le profil
    role = 'etudiant'
    profil_id = None
    profil_data = {}
    
    # Chercher l'enseignant
    try:
        enseignant = Enseignant.objects.get(utilisateur=utilisateur)
        role = 'enseignant'
        profil_id = enseignant.pk
        profil_data = {
            'specialite': enseignant.specialite,
            'departement': enseignant.departement
        }
    except Enseignant.DoesNotExist:
        pass
    
    # Si pas enseignant, chercher étudiant
    if not profil_id:
        try:
            etudiant = Etudiant.objects.get(utilisateur=utilisateur)
            role = 'etudiant'
            profil_id = etudiant.pk
            profil_data = {
                'matricule': etudiant.matricule,
                'niveau': etudiant.niveau,
                'filiere': etudiant.filiere
            }
        except Etudiant.DoesNotExist:
            pass
    
    # Si pas étudiant, chercher admin
    if not profil_id:
        try:
            admin = Administrateur.objects.get(utilisateur=utilisateur)
            role = 'admin'
            profil_id = admin.pk
            profil_data = {
                'role_admin': admin.role_admin,
                'permissions': admin.permissions
            }
        except Administrateur.DoesNotExist:
            pass
    
    # Générer les tokens JWT
    refresh = RefreshToken.for_user(utilisateur)
    
    return Response({
        'message': 'Connexion réussie',
        'user': {
            'id': str(utilisateur.pk),
            'email': utilisateur.email,
            'nom': utilisateur.last_name,
            'prenom': utilisateur.first_name,
            'role': role,
            'profil_id': str(profil_id) if profil_id else None,
            'profil': profil_data
        },
        'tokens': {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """POST /api/auth/logout/"""
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'message': 'Déconnexion réussie'}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


def _get_user_profile_data(utilisateur):
    """Calcule les données de profil pour un utilisateur donné."""
    role = 'etudiant'
    profil_data = None
    profil_id = None
    
    try:
        enseignant = Enseignant.objects.get(utilisateur=utilisateur)
        role = 'enseignant'
        profil_id = enseignant.pk
        profil_data = {
            'id': str(enseignant.pk),
            'specialite': enseignant.specialite,
            'departement': enseignant.departement,
            'nb_cours': Cours.objects.filter(enseignant=enseignant).count()
        }
    except Enseignant.DoesNotExist:
        try:
            etudiant = Etudiant.objects.get(utilisateur=utilisateur)
            role = 'etudiant'
            profil_id = etudiant.pk
            profil_data = {
                'id': str(etudiant.pk),
                'matricule': etudiant.matricule,
                'niveau': etudiant.niveau,
                'filiere': etudiant.filiere
            }
        except Etudiant.DoesNotExist:
            try:
                admin = Administrateur.objects.get(utilisateur=utilisateur)
                role = 'admin'
                profil_id = admin.pk
                profil_data = {
                    'role_admin': admin.role_admin,
                    'permissions': admin.permissions
                }
            except Administrateur.DoesNotExist:
                pass
    
    return {
        'id': str(utilisateur.pk),
        'email': utilisateur.email,
        'nom': utilisateur.last_name,
        'prenom': utilisateur.first_name,
        'role': role,
        'profil_id': str(profil_id) if profil_id else None,
        'profil': profil_data,
        'date_creation': utilisateur.date_joined,
        'derniere_connexion': utilisateur.last_login
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """GET /api/auth/me/"""
    data = _get_user_profile_data(request.user)
    return Response(data, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def update_profile_view(request):
    """PUT /api/auth/profile/"""
    utilisateur = request.user
    
    # Mise à jour des champs Utilisateur
    if 'nom' in request.data:
        utilisateur.last_name = request.data['nom']
    if 'prenom' in request.data:
        utilisateur.first_name = request.data['prenom']
        
    # GESTION DE LA PHOTO DE PROFIL
    if 'photo' in request.FILES:
        utilisateur.photo_url = request.FILES['photo']
        
    utilisateur.save()

    # Mise à jour des champs de profil spécifiques
    if utilisateur.type_compte == 'ENSEIGNANT':
        try:
            profil = Enseignant.objects.get(utilisateur=utilisateur)
            if 'specialite' in request.data:
                profil.specialite = request.data['specialite']
            if 'departement' in request.data:
                profil.departement = request.data['departement']
            profil.save()
        except Enseignant.DoesNotExist:
            pass
    elif utilisateur.type_compte == 'ETUDIANT':
        try:
            profil = Etudiant.objects.get(utilisateur=utilisateur)
            if 'niveau' in request.data:
                profil.niveau = request.data['niveau']
            if 'filiere' in request.data:
                profil.filiere = request.data['filiere']
            profil.save()
        except Etudiant.DoesNotExist:
            pass
    
    data = _get_user_profile_data(utilisateur)
    return Response(data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """POST /api/auth/change-password/"""
    utilisateur = request.user
    
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    new_password2 = request.data.get('new_password2')
    
    if not all([old_password, new_password, new_password2]):
        return Response({'error': 'Tous les champs sont requis'}, status=status.HTTP_400_BAD_REQUEST)
    
    if new_password != new_password2:
        return Response({'error': 'Les nouveaux mots de passe ne correspondent pas'}, status=status.HTTP_400_BAD_REQUEST)
    
    if not utilisateur.check_password(old_password):
        return Response({'error': 'Ancien mot de passe incorrect'}, status=status.HTTP_400_BAD_REQUEST)
    
    utilisateur.set_password(new_password)
    utilisateur.save()
    
    return Response({'message': 'Mot de passe modifié avec succès'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_cours_view(request):
    """GET /api/cours/mes-cours/"""
    try:
        enseignant = Enseignant.objects.get(utilisateur=request.user)
        cours = Cours.objects.filter(enseignant=enseignant).order_by('-date_creation')
        role = 'enseignant'
    except Enseignant.DoesNotExist:
        try:
            etudiant = Etudiant.objects.get(utilisateur=request.user)
            # Récupérer les cours auxquels l'étudiant est inscrit (via les matières)
            cours = Cours.objects.filter(matiere__etudiants_inscrits=etudiant).order_by('-date_creation')
            role = 'etudiant'
        except Etudiant.DoesNotExist:
            cours = Cours.objects.none()
            role = 'guest'
    
    from .serializers import CoursListSerializer
    serializer = CoursListSerializer(cours, many=True, context={'request': request})
    
    return Response({
        'role': role,
        'count': cours.count(),
        'cours': serializer.data
    })