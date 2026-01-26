"""
Script pour retraiter automatiquement les fichiers non-traités
"""
import os
import django
import sys

sys.path.append('/home/rouchda-yampen/Bureau/XCSM_Backend-relié/XCSM_Backend-main')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xcsm_project.settings')
django.setup()

from xcsm.models import FichierSource
from xcsm.processing import process_and_store_document
from xcsm.utils import get_mongo_db

print("=" * 80)
print("RETRAITEMENT AUTOMATIQUE DES FICHIERS")
print("=" * 80)

# 1. Identifier les fichiers non-traités
fichiers_pg = FichierSource.objects.filter(statut_traitement='EN_ATTENTE')
print(f"\nFichiers à retraiter: {fichiers_pg.count()}")

if fichiers_pg.count() == 0:
    print("✅ Aucun fichier à retraiter!")
    sys.exit(0)

# 2. Retraiter chaque fichier
for i, fichier in enumerate(fichiers_pg, 1):
    print(f"\n{'='*80}")
    print(f"[{i}/{fichiers_pg.count()}] Traitement: {fichier.titre}")
    print(f"ID: {fichier.id}")
    print(f"Fichier: {fichier.fichier_original.name if fichier.fichier_original else 'N/A'}")
    print("=" * 80)
    
    try:
        # Vérifier que le fichier existe
        if not fichier.fichier_original:
            print("❌ Pas de fichier original attaché!")
            continue
        
        if not os.path.exists(fichier.fichier_original.path):
            print(f"❌ Fichier physique introuvable: {fichier.fichier_original.path}")
            continue
        
        # Lancer le traitement
        print("🚀 Lancement du traitement...")
        success, message = process_and_store_document(fichier)
        
        if success:
            print(f"✅ SUCCÈS: {message}")
            
            # Vérifier MongoDB
            mongo_db = get_mongo_db()
            mongo_doc = mongo_db['fichiers_uploades'].find_one({
                'fichier_source_id': str(fichier.id)
            })
            
            if mongo_doc:
                print(f"✅ Structure MongoDB créée")
                granules_count = mongo_db['granules'].count_documents({
                    'fichier_source_id': str(fichier.id)
                })
                print(f"✅ {granules_count} granules créés dans MongoDB")
            else:
                print("⚠️ Structure MongoDB non trouvée (vérifier)")
        else:
            print(f"❌ ÉCHEC: {message}")
            
    except Exception as e:
        print(f"❌ ERREUR: {str(e)}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
print("RÉSUMÉ FINAL")
print("=" * 80)

# 3. Statistiques finales
fichiers_traites = FichierSource.objects.filter(statut_traitement='TRAITE').count()
fichiers_en_attente = FichierSource.objects.filter(statut_traitement='EN_ATTENTE').count()
fichiers_erreur = FichierSource.objects.filter(statut_traitement='ERREUR').count()

print(f"\nStatut des fichiers:")
print(f"  ✅ Traités: {fichiers_traites}")
print(f"  ⏳ En attente: {fichiers_en_attente}")
print(f"  ❌ En erreur: {fichiers_erreur}")

mongo_db = get_mongo_db()
print(f"\nMongoDB:")
print(f"  Fichiers: {mongo_db['fichiers_uploades'].count_documents({})}")
print(f"  Granules: {mongo_db['granules'].count_documents({})}")

print("\n" + "=" * 80)
