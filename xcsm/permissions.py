# xcsm/permissions.py
from rest_framework import permissions

class IsEnseignant(permissions.BasePermission):
    """
    Permission personnalisée pour autoriser uniquement les enseignants à uploader.
    """
    def has_permission(self, request, view):
        # Vérifie si l'utilisateur est connecté ET s'il a le type de compte 'ENSEIGNANT'
        return request.user.is_authenticated and request.user.type_compte == 'ENSEIGNANT'