# Author: Dilane PAFE
# Fichier: xcsm/views_commentaires.py - API pour Collaboration et Notifications

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Commentaire, Granule, Cours, Notification
from .serializers import CommentSerializer, CommentReplySerializer, NotificationSerializer
from .permissions import IsCommentAuthorOrCourseTeacher, is_teacher_of_cours
from django.db.models import Count
from django.db.models import Q


def _actor_role(user):
    return 'enseignant' if hasattr(user, 'profil_enseignant') else 'etudiant'


def _notify_course_teachers(cours, exclude_user, **notif_kwargs):
    """Notifie le propriétaire du cours + le propriétaire de la matière + tous les co-enseignants (sans doublon)."""
    destinataires = {}
    if cours.enseignant:
        destinataires[cours.enseignant.utilisateur_id] = cours.enseignant.utilisateur
    if cours.matiere:
        if cours.matiere.enseignant:
            destinataires[cours.matiere.enseignant.utilisateur_id] = cours.matiere.enseignant.utilisateur
        for co_ens in cours.matiere.enseignants.all():
            destinataires[co_ens.utilisateur_id] = co_ens.utilisateur

    destinataires.pop(exclude_user.id, None)

    for utilisateur in destinataires.values():
        Notification.objects.create(destinataire=utilisateur, **notif_kwargs)


class CommentaireViewSet(viewsets.ModelViewSet):
    """
    Gère les routes /api/v1/comments/ appelées par le Next.js FrontEnd.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CommentSerializer

    def get_permissions(self):
        if self.action in ('update', 'partial_update', 'destroy'):
            return [IsAuthenticated(), IsCommentAuthorOrCourseTeacher()]
        return [IsAuthenticated()]

    def get_queryset(self):
        # On ne renvoie que les commentaires principaux (pas les réponses imbriquées)
        queryset = Commentaire.objects.filter(parent__isnull=True).select_related('auteur', 'granule', 'cours')

        granule_id = self.request.query_params.get('granule_id')
        course_id = self.request.query_params.get('course_id')
        type_filtre = self.request.query_params.get('type')
        sort = self.request.query_params.get('sort', 'top')

        if granule_id:
            queryset = queryset.filter(granule_id=granule_id)
        if course_id:
            queryset = queryset.filter(cours_id=course_id)
        if type_filtre and type_filtre != 'all':
            queryset = queryset.filter(type_commentaire=type_filtre)

        # Visibilité : les commentaires en attente/rejetés ne sont visibles que par
        # leur auteur ou l'enseignant (propriétaire/co-enseignant) du cours concerné.
        user = self.request.user
        queryset = queryset.filter(
            Q(statut='approved') |
            Q(auteur=user) |
            Q(cours__enseignant__utilisateur=user) |
            Q(cours__matiere__enseignant__utilisateur=user) |
            Q(cours__matiere__enseignants__utilisateur=user)
        ).distinct()

        # Tri : Pinned d'abord, puis selon le paramètre
        if sort == 'top':
            # Annotation pour trier par upvotes
            queryset = queryset.annotate(upvote_count=Count('upvotes')).order_by('-is_pinned', '-upvote_count', '-created_at')
        else: # 'recent'
            queryset = queryset.order_by('-is_pinned', '-created_at')

        return queryset

    @action(detail=False, methods=['get'], url_path='teacher')
    def teacher(self, request, *args, **kwargs):
        """
        Retourne tous les commentaires des cours appartenant à l'enseignant connecté.
        Utilisé par le tableau de bord enseignant.
        """
        if not hasattr(request.user, 'profil_enseignant'):
            return Response({"error": "Accès réservé aux enseignants."}, status=status.HTTP_403_FORBIDDEN)

        queryset = Commentaire.objects.filter(parent__isnull=True).filter(
            Q(cours__enseignant__utilisateur=request.user) |
            Q(cours__matiere__enseignant__utilisateur=request.user) |
            Q(cours__matiere__enseignants__utilisateur=request.user)
        ).select_related('auteur', 'granule', 'cours').distinct()

        course_id = request.query_params.get('course_id')
        type_filtre = request.query_params.get('type')
        status_filtre = request.query_params.get('status')
        sort = request.query_params.get('sort', 'recent')

        if course_id:
            queryset = queryset.filter(cours_id=course_id)
        if type_filtre and type_filtre != 'all':
            queryset = queryset.filter(type_commentaire=type_filtre)
        if status_filtre:
            queryset = queryset.filter(statut=status_filtre)

        # Tri
        if sort == 'top':
            queryset = queryset.annotate(upvote_count=Count('upvotes')).order_by('-upvote_count', '-created_at')
        elif sort == 'pending':
            # Les commentaires en attente d'abord
            queryset = queryset.order_by('statut', '-created_at')  # 'approved' vs 'pending' (pending < approved alphabétiquement? Non. 'approved' < 'pending'. Donc order_by('-statut') mettra 'pending' d'abord)
            queryset = queryset.order_by('-statut', '-created_at')
        else:
            queryset = queryset.order_by('-created_at')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "comments": serializer.data,
            "total": queryset.count(),
            "pending": queryset.filter(statut="pending").count(),
            "suggestions": queryset.filter(type_commentaire__in=["suggestion", "correction"]).count()
        })


    def list(self, request, *args, **kwargs):
        """Surcharge pour correspondre au format de réponse paginé attendu par useComments.ts"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "comments": serializer.data,
            "total": queryset.count()
        })

    def create(self, request, *args, **kwargs):
        """Surcharge POST pour mapper les données brutes venant du FrontEnd"""
        data = request.data
        try:
            granule = Granule.objects.get(id=data.get('granule_id'))
            cours = Cours.objects.get(id=data.get('course_id'))
            
            # Détermination du statut initial basé sur le type
            type_c = data.get('type', 'comment')
            statut = 'pending' if type_c in ['suggestion', 'correction'] else 'approved'

            commentaire = Commentaire.objects.create(
                auteur=request.user,
                granule=granule,
                cours=cours,
                type_commentaire=type_c,
                contenu=data.get('content'),
                statut=statut
            )

            # ── Notification pour l'enseignant propriétaire du cours + co-enseignants ──
            _notify_course_teachers(
                cours,
                exclude_user=request.user,
                type_notif='new_comment',
                title="Nouveau commentaire" if type_c == 'comment' else f"Nouvelle {type_c}",
                message=f"{request.user.first_name} a laissé un {type_c} sur votre cours '{cours.titre}'.",
                link=f"/dashboard/commentaires?course_id={cours.id}",
                actor_name=f"{request.user.first_name} {request.user.last_name}",
                actor_role=_actor_role(request.user),
            )

            serializer = self.get_serializer(commentaire)
            return Response({"comment": serializer.data}, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='vote')
    def vote(self, request, pk=None):
        """
        POST /api/v1/comments/{id}/vote/
        Body: {"vote": "up" | "down" | null}
        """
        commentaire = self.get_object()
        vote = request.data.get('vote')
        user = request.user
        already_upvoted = commentaire.upvotes.filter(pk=user.pk).exists()

        if vote == 'up':
            commentaire.downvotes.remove(user)
            commentaire.upvotes.add(user)
            if not already_upvoted and commentaire.auteur_id != user.id:
                Notification.objects.create(
                    destinataire=commentaire.auteur,
                    type_notif='upvote',
                    title="Vote positif",
                    message=f"{user.first_name} a trouvé votre {commentaire.type_commentaire} utile.",
                    link=f"/cours/{commentaire.cours_id}/lecture?granule={commentaire.granule_id}",
                    actor_name=f"{user.first_name} {user.last_name}",
                    actor_role=_actor_role(user),
                )
        elif vote == 'down':
            commentaire.upvotes.remove(user)
            commentaire.downvotes.add(user)
        elif vote is None:
            commentaire.upvotes.remove(user)
            commentaire.downvotes.remove(user)

        # On renvoie les nouveaux compteurs au front
        return Response({
            "upvotes": commentaire.upvotes.count(),
            "downvotes": commentaire.downvotes.count(),
            "user_vote": vote
        })

    @action(detail=True, methods=['post'], url_path='replies')
    def replies(self, request, pk=None):
        """
        POST /api/v1/comments/{id}/replies/
        Body: {"content": "..."}
        """
        parent = self.get_object()

        reply = Commentaire.objects.create(
            auteur=request.user,
            granule=parent.granule,
            cours=parent.cours,
            parent=parent,
            contenu=request.data.get('content'),
            type_commentaire='comment',
            statut='approved'
        )

        # Création d'une notification pour l'auteur du commentaire parent
        if parent.auteur_id != request.user.id:
            Notification.objects.create(
                destinataire=parent.auteur,
                type_notif='reply',
                title="Nouvelle réponse",
                message=f"{request.user.first_name} a répondu à votre {parent.type_commentaire}.",
                link=f"/cours/{parent.cours_id}/lecture?granule={parent.granule_id}",
                actor_name=f"{request.user.first_name} {request.user.last_name}",
                actor_role=_actor_role(request.user),
            )

        serializer = CommentReplySerializer(reply, context={'request': request})
        return Response({"reply": serializer.data}, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        """Notifie l'auteur d'une suggestion/correction quand un enseignant approuve ou rejette."""
        old_statut = serializer.instance.statut
        instance = serializer.save()

        if (
            old_statut != instance.statut
            and instance.statut in ('approved', 'rejected')
            and instance.type_commentaire in ('suggestion', 'correction')
            and instance.auteur_id != self.request.user.id
        ):
            if instance.statut == 'approved':
                type_notif, title, verbe = 'suggestion_approved', "Suggestion approuvée ✓", "approuvée"
            else:
                type_notif, title, verbe = 'suggestion_rejected', "Suggestion rejetée", "rejetée"

            Notification.objects.create(
                destinataire=instance.auteur,
                type_notif=type_notif,
                title=title,
                message=f"Votre {instance.type_commentaire} sur '{instance.cours.titre}' a été {verbe} par l'enseignant.",
                link=f"/cours/{instance.cours_id}/lecture?granule={instance.granule_id}",
                actor_name=f"{self.request.user.first_name} {self.request.user.last_name}",
                actor_role=_actor_role(self.request.user),
            )


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Gère les routes /api/v1/notifications/ appelées par NotificationsBell.tsx
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(destinataire=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset[:50], many=True) # Max 50 notifs
        unread_count = queryset.filter(is_read=False).count()

        return Response({
            "notifications": serializer.data,
            "unread_count": unread_count
        })

    @action(detail=False, methods=['patch'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """PATCH /api/v1/notifications/mark-all-read/"""
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"success": True, "marked_read": updated})