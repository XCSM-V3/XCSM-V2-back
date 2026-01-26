"""
Test de la génération QCM après retraitement
"""
import os
import django
import sys

sys.path.append('/home/rouchda-yampen/Bureau/XCSM_Backend-relié/XCSM_Backend-main')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xcsm_project.settings')
django.setup()

from xcsm.models import FichierSource, Granule
from xcsm.json_utils import get_fichier_json_structure
import json

print("=" * 80)
print("TEST GÉNÉRATION QCM - Vérification Enrichissement")
print("=" * 80)

# Prendre un fichier fraîchement traité
fichier = FichierSource.objects.filter(statut_traitement='TRAITE').first()

if not fichier:
    print("❌ Aucun fichier traité trouvé!")
    sys.exit(1)

print(f"\nFichier de test: {fichier.titre} (ID: {fichier.id})")

# 1. Récupérer la structure JSON
json_structure = get_fichier_json_structure(fichier.id)

if not json_structure:
    print("❌ Structure JSON introuvable!")
    sys.exit(1)

print("✅ Structure JSON récupérée")

# 2. Récupérer les granules PostgreSQL
granules = Granule.objects.filter(
    sous_section__section__chapitre__partie__cours__fichiers_sources=fichier
)[:10]  # Prendre les 10 premiers

print(f"\nGranules PostgreSQL: {Granule.objects.filter(sous_section__section__chapitre__partie__cours__fichiers_sources=fichier).count()}")

# 3. Créer le mapping
granule_map = {}
for g in Granule.objects.filter(sous_section__section__chapitre__partie__cours__fichiers_sources=fichier):
    granule_map[g.titre] = str(g.id)

print(f"Mapping créé: {len(granule_map)} entrées")

# 4. Enrichir
def enrich_structure(node):
    if isinstance(node, dict):
        if 'titre' in node or 'title' in node:
            titre = node.get('titre') or node.get('title')
            if titre and titre in granule_map:
                node['granule_id'] = granule_map[titre]
        
        for key, value in node.items():
            if isinstance(value, (dict, list)):
                enrich_structure(value)
    elif isinstance(node, list):
        for item in node:
            enrich_structure(item)

enrich_structure(json_structure)

# 5. Compter les granule_id
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

print(f"\n{'='*80}")
print(f"RÉSULTAT: {total_ids} granule_id enrichis")
print("=" * 80)

if total_ids > 0:
    print("\n✅ L'ENRICHISSEMENT FONCTIONNE!")
    print("✅ La génération de QCM devrait maintenant fonctionner")
    
    # Afficher un échantillon
    print("\nÉchantillon de structure enrichie:")
    print(json.dumps(json_structure, indent=2, ensure_ascii=False)[:1000])
else:
    print("\n❌ PROBLÈME: Aucun granule_id enrichi")
    print("Vérifier que les titres correspondent")

print("\n" + "=" * 80)
