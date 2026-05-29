# Generated manually 2026-05-29
# Create TrackingSession and CourseAnalyticsSnapshot tables (models_analytics.py)
# These were missing from all previous migrations.

import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('xcsm', '0011_matiere_enseignants'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrackingSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('time_spent_seconds', models.IntegerField(default=0)),
                ('success_rate', models.FloatField(
                    blank=True,
                    help_text='Taux de réussite aux QCM sur ce granule (0.0 à 1.0)',
                    null=True,
                )),
                ('date_session', models.DateTimeField(auto_now_add=True)),
                ('cours', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sessions_tracking_cours',
                    to='xcsm.cours',
                )),
                ('etudiant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sessions_tracking',
                    to='xcsm.etudiant',
                )),
                ('granule', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sessions_tracking_granules',
                    to='xcsm.granule',
                )),
            ],
            options={
                'ordering': ['-date_session'],
            },
        ),
        migrations.CreateModel(
            name='CourseAnalyticsSnapshot',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('total_students', models.IntegerField(default=0)),
                ('active_students', models.IntegerField(default=0)),
                ('at_risk_students', models.IntegerField(default=0)),
                ('average_completion_rate', models.FloatField(default=0.0)),
                ('total_time_spent_hours', models.FloatField(default=0.0)),
                ('difficulty_zones', models.JSONField(default=list)),
                ('date_snapshot', models.DateTimeField(auto_now_add=True)),
                ('cours', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='analytics_snapshots',
                    to='xcsm.cours',
                )),
            ],
            options={
                'ordering': ['-date_snapshot'],
            },
        ),
    ]
