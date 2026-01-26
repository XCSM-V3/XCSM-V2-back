"""
Script de test pour vérifier la logique complète de génération de QCM
"""
import os
import django
import sys

# Setup Django
sys.path.append('/home/rouchda-yampen/Bureau/XCSM_Backend-relié/XCSM_Backend-main')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xcsm_project.settings')
django.setup()

from xcsm.models import FichierSource, Granule, Cours
from xcsm.json_utils import get_fichier_json_structure
import json

print("=" * 80)
print("TEST COMPLET: Vérification de la logique QCM")
print("=" * 80)

# 1. Vérifier qu'il y a des fichiers et des granules
print("\n1. Vérification de la base de données...")
fichiers = FichierSource.objects.all()[:5]
print(f"   Nombre de fichiers: {FichierSource.objects.count()}")
print(f"   Nombre de granules: {Granule.objects.count()}")

if not fichiers:
    print("   ❌ Aucun fichier trouvé!")
    sys.exit(1)

# 2. Prendre le premier fichier et vérifier sa structure
fichier = fichiers[0]
print(f"\n2. Test avec le fichier: {fichier.titre} (ID: {fichier.id})")

# 3. Récupérer la structure JSON depuis MongoDB
print("\n3. Récupération de la structure JSON depuis MongoDB...")
json_structure = get_fichier_json_structure(fichier.id)

if not json_structure:
    print("   ❌ Aucune structure JSON trouvée dans MongoDB!")
    sys.exit(1)

print(f"   ✓ Structure JSON récupérée")

# 4. Vérifier les granules liés à ce fichier
print("\n4. Vérification des granules PostgreSQL...")
granules = Granule.objects.filter(
    sous_section__section__chapitre__partie__cours__fichiers_sources=fichier
).select_related('sous_section__section__chapitre__partie')

print(f"   Nombre de granules liés: {granules.count()}")

if granules.count() == 0:
    print("   ⚠️  Aucun granule lié à ce fichier!")
    print("   Cela signifie que le fichier n'a pas été traité correctement.")
else:
    print("\n   Granules trouvés:")
    for g in granules[:5]:
        print(f"     - {g.titre} (ID: {g.id})")

# 5. Simuler l'enrichissement
print("\n5. Simulation de l'enrichissement...")
granule_map = {}
for granule in granules:
    granule_map[granule.titre] = str(granule.id)

print(f"   Mapping créé: {len(granule_map)} entrées")

# 6. Fonction d'enrichissement (copie de views.py)
def enrich_structure(node):
    if isinstance(node, dict):
        if 'titre' in node or 'title' in node:
            titre = node.get('titre') or node.get('title')
            if titre and titre in granule_map:
                node['granule_id'] = granule_map[titre]
                print(f"     ✓ Enrichi: {titre} -> {granule_map[titre]}")
        
        for key, value in node.items():
            if isinstance(value, (dict, list)):
                enrich_structure(value)
    elif isinstance(node, list):
        for item in node:
            enrich_structure(item)

# 7. Enrichir la structure
print("\n6. Enrichissement de la structure...")
enrich_structure(json_structure)

# 8. Vérifier si des granule_id ont été ajoutés
print("\n7. Vérification des granule_id ajoutés...")
def count_granule_ids(node, count=[0]):
    if isinstance(node, dict):
        if 'granule_id' in node:
            count[0] += 1
        for value in node.values():
            count_granule_ids(value, count)
    elif isinstance(node, list):
        for item in node:
            count_granule_ids(item, count)
    return count[0]

total_ids = count_granule_ids(json_structure)
print(f"   Nombre de granule_id ajoutés: {total_ids}")

if total_ids == 0:
    print("\n   ❌ PROBLÈME: Aucun granule_id n'a été ajouté!")
    print("   Causes possibles:")
    print("   - Les titres dans MongoDB ne correspondent pas aux titres dans PostgreSQL")
    print("   - La structure JSON n'a pas de champs 'titre' ou 'title'")
    
    # Debug: afficher un échantillon de la structure
    print("\n   Échantillon de la structure JSON:")
    print(json.dumps(json_structure, indent=2, ensure_ascii=False)[:500])
else:
    print(f"   ✓ {total_ids} granule_id ont été ajoutés avec succès!")

# 9. Sauvegarder la structure enrichie pour inspection
output_file = '/tmp/structure_enrichie_test.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(json_structure, f, indent=2, ensure_ascii=False)

print(f"\n8. Structure enrichie sauvegardée dans: {output_file}")

print("\n" + "=" * 80)
print("FIN DU TEST")
print("=" * 80)
