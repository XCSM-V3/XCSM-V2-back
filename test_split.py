import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "xcsm_project.settings")
django.setup()

from xcsm.models import Matiere, FichierSource, Enseignant, Utilisateur
from xcsm.processing import parse_html_to_json_structure, split_and_create_granules
from django.core.files.base import ContentFile
from xcsm.json_utils import get_xccm_cours_structure
import json

# 1. Setup mock data
user, _ = Utilisateur.objects.get_or_create(username='test_user_hi', type_compte='enseignant', email='testhi@test.com')
enseignant, _ = Enseignant.objects.get_or_create(utilisateur=user)
matiere, _ = Matiere.objects.get_or_create(titre='Test Matiere HI', code='TEST102', enseignant=user.profil_id)

fichier = FichierSource.objects.create(
    enseignant=enseignant,
    matiere=matiere,
    titre='Document de Test Hierarchique',
    type_fichier='TXT',
    statut_traitement='EN_ATTENTE'
)

# 2. Mock HTML structure
html = """
<h1>Chapitre 1 : Introduction</h1>
<p>Premier paragraphe d'introduction.</p>
<p>Deuxième paragraphe.</p>
<h2>Section 1.1</h2>
<p>Un peu de détails.</p>
<h1>Chapitre 2 : La suite</h1>
<p>On continue ici.</p>
"""

# 3. Parse to JSON
json_structure = parse_html_to_json_structure(html)

# 4. Create Granules
cours = split_and_create_granules(fichier, json_structure)

# 5. Extract Structure via API
result = get_xccm_cours_structure(cours)
print(json.dumps(result, indent=2))
