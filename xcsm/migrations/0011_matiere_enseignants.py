# Generated manually 2026-05-29
# Add Matiere.enseignants ManyToManyField (co-enseignants) which was missing from 0010

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('xcsm', '0010_remove_cours_code_remove_cours_etudiants_inscrits_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='matiere',
            name='enseignants',
            field=models.ManyToManyField(
                blank=True,
                related_name='matieres_partagees',
                to='xcsm.enseignant',
            ),
        ),
    ]
