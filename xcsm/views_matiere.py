from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import Matiere, Enseignant, Etudiant
from .serializers import MatiereSerializer, MatiereCreateSerializer, EnseignantSerializer
from django.db.models import Q

class MatiereListCreateView(generics.ListCreateAPIView):
    """
    GET: Liste les matières (Enseignant: les siennes / Etudiant: celles inscrit)
    POST: Créer une matière (Enseignant uniquement)
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MatiereCreateSerializer
        return MatiereSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        # Si Enseignant -> Voir ses matières (propriétaire OU co-enseignant)
        if hasattr(user, 'profil_enseignant'):
            ens = user.profil_enseignant
            return Matiere.objects.filter(Q(enseignant=ens) | Q(enseignants=ens)).distinct()
        
        # Si Etudiant -> Voir les matières inscrites
        elif hasattr(user, 'profil_etudiant'):
            return user.profil_etudiant.matieres_suivies.all()
            
        return Matiere.objects.none()
    
    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'profil_enseignant'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Seuls les enseignants peuvent créer des matières.")
            
        matiere = serializer.save(enseignant=self.request.user.profil_enseignant)
        # Le créateur devient automatiquement enseignant de la matière
        matiere.enseignants.add(self.request.user.profil_enseignant)

class JoinMatiereView(APIView):
    """
    POST: Rejoindre une matière via son CODE (Pour les étudiants)
    Payload: {"code": "PHY2023"}
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        code = request.data.get('code')
        if not code:
            return Response({"error": "Code requis"}, status=status.HTTP_400_BAD_REQUEST)
            
        if not hasattr(request.user, 'profil_etudiant'):
            return Response({"error": "Seuls les étudiants peuvent s'inscrire."}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            # Recherche insensible à la casse
            matiere = Matiere.objects.get(code__iexact=code)
            etudiant = request.user.profil_etudiant
            
            # Vérifier si déjà inscrit
            if matiere.etudiants_inscrits.filter(pk=etudiant.pk).exists():
                 return Response({"message": "Déjà inscrit à ce cours."}, status=status.HTTP_200_OK)
            
            matiere.etudiants_inscrits.add(etudiant)
            
            return Response({
                "message": f"Inscription réussie à {matiere.titre}",
                "matiere": MatiereSerializer(matiere, context={'request': request}).data
            }, status=status.HTTP_201_CREATED)
            
        except Matiere.DoesNotExist:
            return Response({"error": "Code invalide. Aucune matière trouvée."}, status=status.HTTP_404_NOT_FOUND)

class MatiereDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/DELETE une matière spécifique
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MatiereSerializer
    
    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'profil_enseignant'):
            ens = user.profil_enseignant
            return Matiere.objects.filter(Q(enseignant=ens) | Q(enseignants=ens)).distinct()
        return Matiere.objects.all() # Pour lecture étudiant (permissions à affiner si besoin)

class EnseignantListView(generics.ListAPIView):
    """
    GET: Liste de tous les enseignants inscrits dans la plateforme.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = EnseignantSerializer
    queryset = Enseignant.objects.all().select_related('utilisateur')

class MatiereCoTeachersView(APIView):
    """
    Gestion des co-enseignants pour une matière.
    Uniquement accessible par le propriétaire (le créateur) de la matière.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        matiere = get_object_or_404(Matiere, pk=pk)
        
        # Vérifier si l'utilisateur est propriétaire ou co-enseignant
        if not hasattr(request.user, 'profil_enseignant'):
            return Response({"error": "Accès réservé aux enseignants"}, status=status.HTTP_403_FORBIDDEN)
        
        ens = request.user.profil_enseignant
        if matiere.enseignant != ens and not matiere.enseignants.filter(pk=ens.pk).exists():
            return Response({"error": "Vous n'avez pas accès à cette matière"}, status=status.HTTP_403_FORBIDDEN)

        # Renvoyer la liste des co-enseignants
        co_teachers = matiere.enseignants.all()
        serializer = EnseignantSerializer(co_teachers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk):
        matiere = get_object_or_404(Matiere, pk=pk)
        
        # Seul le propriétaire de la matière peut ajouter des co-enseignants
        if not hasattr(request.user, 'profil_enseignant') or matiere.enseignant != request.user.profil_enseignant:
            return Response({"error": "Seul le propriétaire de la matière peut ajouter des co-enseignants"}, status=status.HTTP_403_FORBIDDEN)

        teacher_ids = request.data.get('teacher_ids')
        email = request.data.get('email')

        if not teacher_ids and not email:
            return Response({"error": "teacher_ids ou email requis"}, status=status.HTTP_400_BAD_REQUEST)

        if teacher_ids:
            if not isinstance(teacher_ids, list):
                return Response({"error": "teacher_ids doit être une liste"}, status=status.HTTP_400_BAD_REQUEST)
            enseignants = Enseignant.objects.filter(pk__in=teacher_ids)
        else:
            try:
                # Chercher l'enseignant par l'email de son compte utilisateur
                enseignant = Enseignant.objects.get(utilisateur__email__iexact=email)
                enseignants = Enseignant.objects.filter(pk=enseignant.pk)
            except Enseignant.DoesNotExist:
                return Response({"error": "Aucun enseignant trouvé avec cet email"}, status=status.HTTP_404_NOT_FOUND)

        if not enseignants.exists():
            return Response({"error": "Aucun enseignant valide trouvé"}, status=status.HTTP_404_NOT_FOUND)

        # Vérifier si c'est le propriétaire lui-même et exclure
        enseignants = enseignants.exclude(pk=matiere.enseignant.pk)

        # Ajouter les co-enseignants
        matiere.enseignants.add(*enseignants)
        
        co_teachers = matiere.enseignants.all()
        serializer = EnseignantSerializer(co_teachers, many=True)
        return Response({
            "message": "Collaborateurs ajoutés avec succès",
            "enseignants": serializer.data
        }, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        matiere = get_object_or_404(Matiere, pk=pk)
        
        # Seul le propriétaire de la matière peut retirer des co-enseignants
        if not hasattr(request.user, 'profil_enseignant') or matiere.enseignant != request.user.profil_enseignant:
            return Response({"error": "Seul le propriétaire de la matière peut retirer des co-enseignants"}, status=status.HTTP_403_FORBIDDEN)

        teacher_id = request.data.get('id')
        email = request.data.get('email')
        
        if not teacher_id and not email:
            return Response({"error": "ID ou Email du co-enseignant requis"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if teacher_id:
                enseignant = Enseignant.objects.get(pk=teacher_id)
            else:
                enseignant = Enseignant.objects.get(utilisateur__email__iexact=email)
        except Enseignant.DoesNotExist:
            return Response({"error": "Co-enseignant non trouvé"}, status=status.HTTP_404_NOT_FOUND)

        # Vérifier s'il est co-enseignant
        if not matiere.enseignants.filter(pk=enseignant.pk).exists():
            return Response({"error": "Cet enseignant ne collabore pas sur cette matière"}, status=status.HTTP_400_BAD_REQUEST)

        # Retirer le co-enseignant
        matiere.enseignants.remove(enseignant)
        
        return Response({"message": "Co-enseignant retiré avec succès"}, status=status.HTTP_200_OK)
