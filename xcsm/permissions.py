# xcsm/permissions.py
from rest_framework import permissions

class IsEnseignant(permissions.BasePermission):
    """
    Permission personnalisée pour autoriser uniquement les enseignants à uploader.
    """
    def has_permission(self, request, view):
        # Vérifie si l'utilisateur est connecté ET s'il a le type de compte 'ENSEIGNANT'
        return request.user.is_authenticated and request.user.type_compte == 'ENSEIGNANT'


def is_teacher_of_cours(user, cours):
    """Propriétaire du cours, propriétaire de la matière, ou co-enseignant de la matière."""
    if not hasattr(user, 'profil_enseignant'):
        return False
    ens = user.profil_enseignant
    if cours.enseignant_id == ens.pk:
        return True
    matiere = cours.matiere
    if matiere and (matiere.enseignant_id == ens.pk or matiere.enseignants.filter(pk=ens.pk).exists()):
        return True
    return False


class IsCommentAuthorOrCourseTeacher(permissions.BasePermission):
    """
    Modération/suppression d'un commentaire réservée à son auteur ou à un
    enseignant (propriétaire/co-enseignant) du cours concerné.
    """
    def has_object_permission(self, request, view, obj):
        if obj.auteur_id == request.user.id:
            return True
        return is_teacher_of_cours(request.user, obj.cours)