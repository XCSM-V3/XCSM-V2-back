from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Matiere, Enseignant, Etudiant
from .serializers import MatiereSerializer, MatiereCreateSerializer

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
        
        # Si Enseignant -> Voir ses matières créées
        if hasattr(user, 'profil_enseignant'):
            return Matiere.objects.filter(enseignant=user.profil_enseignant)
        
        # Si Etudiant -> Voir les matières inscrites
        elif hasattr(user, 'profil_etudiant'):
            return user.profil_etudiant.matieres_suivies.all()
            
        return Matiere.objects.none()
    
    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'profil_enseignant'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Seuls les enseignants peuvent créer des matières.")
            
        serializer.save(enseignant=self.request.user.profil_enseignant)

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
            return Matiere.objects.filter(enseignant=user.profil_enseignant)
        return Matiere.objects.all() # Pour lecture étudiant (permissions à affiner si besoin)
