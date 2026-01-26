"""
Script pour identifier et retraiter les fichiers non-traités
"""
import os
import django
import sys

sys.path.append('/home/rouchda-yampen/Bureau/XCSM_Backend-relié/XCSM_Backend-main')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xcsm_project.settings')
django.setup()

from xcsm.models import FichierSource
from xcsm.json_utils import get_fichier_json_structure
from xcsm.utils import get_mongo_db

print("=" * 80)
print("IDENTIFICATION DES FICHIERS NON-TRAITÉS")
print("=" * 80)

# 1. Récupérer tous les fichiers PostgreSQL
fichiers_pg = FichierSource.objects.all()
print(f"\nFichiers dans PostgreSQL: {fichiers_pg.count()}")

# 2. Récupérer tous les fichiers MongoDB
mongo_db = get_mongo_db()
fichiers_mongo = list(mongo_db['fichiers_uploades'].find({}, {'fichier_source_id': 1}))
fichiers_mongo_ids = {f['fichier_source_id'] for f in fichiers_mongo}
print(f"Fichiers dans MongoDB: {len(fichiers_mongo_ids)}")

# 3. Identifier les fichiers manquants
print("\n" + "=" * 80)
print("FICHIERS NON-TRAITÉS:")
print("=" * 80)

fichiers_non_traites = []
for fichier in fichiers_pg:
    fichier_id_str = str(fichier.id)
    if fichier_id_str not in fichiers_mongo_ids:
        fichiers_non_traites.append(fichier)
        print(f"\n❌ {fichier.titre}")
        print(f"   ID: {fichier.id}")
        print(f"   Statut: {fichier.statut_traitement}")
        print(f"   Date upload: {fichier.date_upload}")
        print(f"   Type: {fichier.fichier_original.name if fichier.fichier_original else 'N/A'}")

print(f"\n\nTotal fichiers non-traités: {len(fichiers_non_traites)}")

# 4. Proposer le retraitement
if fichiers_non_traites:
    print("\n" + "=" * 80)
    print("SOLUTION:")
    print("=" * 80)
    print("\nPour retraiter ces fichiers, vous avez deux options:")
    print("\n1. Retraitement automatique (si le fichier original existe)")
    print("   → Relancer le processus de traitement PDF/DOCX")
    print("\n2. Retraitement manuel")
    print("   → Ré-uploader le fichier via l'interface")
    
    print("\n\nVoulez-vous tenter un retraitement automatique ? (y/n)")
    # Note: Pour l'instant, on liste juste. Le retraitement automatique 
    # nécessiterait d'appeler le processeur de documents.
else:
    print("\n✅ Tous les fichiers sont traités!")

print("\n" + "=" * 80)
