# Generated manually 2026-05-29
# Create Commentaire and Notification tables (models.py)
# These were missing from all previous migrations (fields added in b491b5c4).

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('xcsm', '0012_trackingsession_courseanalyticssnapshot'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Commentaire',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('type_commentaire', models.CharField(
                    choices=[('comment', 'Commentaire'), ('question', 'Question'), ('suggestion', 'Suggestion'), ('erreur', 'Signaler une erreur')],
                    default='comment', max_length=20
                )),
                ('contenu', models.TextField()),
                ('statut', models.CharField(
                    choices=[('pending', 'En attente'), ('approved', 'Approuvé'), ('rejected', 'Rejeté'), ('implemented', 'Implémenté')],
                    default='approved', max_length=20
                )),
                ('is_pinned', models.BooleanField(default=False)),
                ('is_resolved', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('auteur', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='commentaires',
                    to=settings.AUTH_USER_MODEL
                )),
                ('cours', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='commentaires_cours',
                    to='xcsm.cours'
                )),
                ('granule', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='commentaires',
                    to='xcsm.granule'
                )),
                ('parent', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reponses_fil',
                    to='xcsm.commentaire'
                )),
                ('upvotes', models.ManyToManyField(
                    blank=True,
                    related_name='upvotes_commentaires',
                    to=settings.AUTH_USER_MODEL
                )),
                ('downvotes', models.ManyToManyField(
                    blank=True,
                    related_name='downvotes_commentaires',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('type_notif', models.CharField(
                    choices=[
                        ('new_comment', 'Nouveau Commentaire'),
                        ('reply', 'Réponse'),
                        ('upvote', 'Upvote'),
                        ('suggestion_approved', 'Suggestion Approuvée'),
                        ('suggestion_rejected', 'Suggestion Rejetée'),
                        ('mention', 'Mention'),
                    ],
                    max_length=30
                )),
                ('title', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('link', models.CharField(blank=True, max_length=255, null=True)),
                ('actor_name', models.CharField(blank=True, max_length=100, null=True)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('destinataire', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
