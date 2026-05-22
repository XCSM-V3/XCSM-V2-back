# Author: Dilane PAFE
# Fichier: xcsm/views_commentaires.py - API pour Collaboration et Notifications

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Commentaire, Granule, Cours, Notification
from .serializers import CommentSerializer, CommentReplySerializer, NotificationSerializer
from django.db.models import Count

class CommentaireViewSet(viewsets.ModelViewSet):
    """
    Gère les routes /api/v1/comments/ appelées par le Next.js FrontEnd.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CommentSerializer

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

        # Tri : Pinned d'abord, puis selon le paramètre
        if sort == 'top':
            # Annotation pour trier par upvotes
            queryset = queryset.annotate(upvote_count=Count('upvotes')).order_by('-is_pinned', '-upvote_count', '-created_at')
        else: # 'recent'
            queryset = queryset.order_by('-is_pinned', '-created_at')

        return queryset

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

        if vote == 'up':
            commentaire.downvotes.remove(user)
            commentaire.upvotes.add(user)
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
        if parent.auteur != request.user:
            Notification.objects.create(
                destinataire=parent.auteur,
                type_notif='reply',
                title="Nouvelle réponse",
                message=f"{request.user.first_name} a répondu à votre {parent.type_commentaire}.",
                actor_name=f"{request.user.first_name} {request.user.last_name}"
            )
            
        serializer = CommentReplySerializer(reply, context={'request': request})
        return Response({"reply": serializer.data}, status=status.HTTP_201_CREATED)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Gère les routes /api/v1/notifications/ appelées par useNotifications.ts
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

    def partial_update(self, request, *args, **kwargs):
        """Utilisé par markAllRead dans useNotifications.ts (appel sans ID)"""
        if not kwargs.get('pk'):
            self.get_queryset().filter(is_read=False).update(is_read=True)
            return Response({"success": True})
        return super().partial_update(request, *args, **kwargs)