# from django.test import TestCase

# # Create your tests here.






# xcsm/tests.py - Tests pour la version JSON
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Utilisateur, Enseignant, FichierSource, Cours, Granule
from .processing import (
    parse_html_to_json_structure,
    split_and_create_granules,
    process_and_store_document
)
from .json_utils import (
    get_fichier_json_structure,
    get_granule_content,
    get_cours_complete_structure
)
from .utils import get_mongo_db
import json


class JsonStructureTestCase(TestCase):
    """Tests de la conversion vers JSON structuré."""
    
    def test_parse_html_to_json_basic(self):
        """Vérifie que le parsing HTML → JSON fonctionne."""
        html = """
        <html><body>
            <h1>Chapitre 1</h1>
            <p>Premier paragraphe</p>
            <h2>Section 1.1</h2>
            <p>Deuxième paragraphe</p>
        </body></html>
        """
        
        result = parse_html_to_json_structure(html)
        
        # Vérifications
        self.assertIn('metadata', result)
        self.assertIn('sections', result)
        self.assertGreater(len(result['sections']), 0)
        
        # Vérification de la hiérarchie
        first_section = result['sections'][0]
        self.assertEqual(first_section['type'], 'h1')
        self.assertEqual(first_section['content'], 'Chapitre 1')
        self.assertIn('children', first_section)
    
    def test_json_structure_levels(self):
        """Vérifie que les niveaux hiérarchiques sont corrects."""
        html = """
        <html><body>
            <h1>Niveau 1</h1>
            <h2>Niveau 2</h2>
            <p>Texte granule</p>
        </body></html>
        """
        
        result = parse_html_to_json_structure(html)
        
        h1 = result['sections'][0]
        self.assertEqual(h1['level'], 1)
        
        h2 = h1['children'][0]
        self.assertEqual(h2['level'], 2)
        
        granule = h2['children'][0]
        self.assertEqual(granule['level'], 4)


class DocumentProcessingTestCase(TestCase):
    """Tests du processus complet de traitement."""
    
    def setUp(self):
        """Création des données de test."""
        # Création utilisateur et enseignant
        self.user = Utilisateur.objects.create_user(
            username='prof_test',
            email='prof@test.com',
            password='test123',
            type_compte='ENSEIGNANT'
        )
        
        self.enseignant = Enseignant.objects.create(
            utilisateur=self.user,
            specialite='Informatique',
            departement='Sciences'
        )
    
    def test_fichier_source_creation(self):
        """Vérifie la création d'un FichierSource."""
        fichier = FichierSource.objects.create(
            enseignant=self.enseignant,
            titre="Test Document",
            fichier_original=SimpleUploadedFile(
                "test.txt", 
                b"Contenu de test",
                content_type="text/plain"
            )
        )
        
        self.assertEqual(fichier.statut_traitement, 'EN_ATTENTE')
        self.assertIsNotNone(fichier.id)
    
    def test_split_and_create_granules(self):
        """Vérifie la création de la hiérarchie depuis JSON."""
        fichier = FichierSource.objects.create(
            enseignant=self.enseignant,
            titre="Test Hiérarchie",
            fichier_original=SimpleUploadedFile("test.txt", b"test")
        )
        
        json_structure = {
            "metadata": {"version": "2.0"},
            "sections": [
                {
                    "type": "h1",
                    "level": 1,
                    "content": "Chapitre Test",
                    "html": "<h1>Chapitre Test</h1>",
                    "children": [
                        {
                            "type": "granule",
                            "level": 4,
                            "content": "Contenu granule test",
                            "html": "<p>Contenu granule test</p>"
                        }
                    ]
                }
            ]
        }
        
        cours = split_and_create_granules(fichier, json_structure)
        
        # Vérifications
        self.assertIsNotNone(cours)
        self.assertEqual(cours.parties.count(), 1)
        
        partie = cours.parties.first()
        self.assertGreater(partie.chapitres.count(), 0)
        
        # Vérification des granules
        total_granules = Granule.objects.filter(fichier_source=fichier).count()
        self.assertGreater(total_granules, 0)


class MongoDBIntegrationTestCase(TestCase):
    """Tests de l'intégration MongoDB."""
    
    def setUp(self):
        """Nettoyage de la base MongoDB de test."""
        mongo_db = get_mongo_db()
        mongo_db['fichiers_uploades'].delete_many({})
        mongo_db['granules'].delete_many({})
        
        # Création utilisateur test
        self.user = Utilisateur.objects.create_user(
            username='prof_mongo',
            email='mongo@test.com',
            password='test123',
            type_compte='ENSEIGNANT'
        )
        
        self.enseignant = Enseignant.objects.create(
            utilisateur=self.user,
            specialite='Test',
            departement='Test'
        )
    
    def test_mongo_storage(self):
        """Vérifie le stockage dans MongoDB."""
        mongo_db = get_mongo_db()
        
        test_doc = {
            "fichier_source_id": "test-123",
            "structure_json": {
                "sections": [
                    {"type": "h1", "content": "Test"}
                ]
            }
        }
        
        result = mongo_db['fichiers_uploades'].insert_one(test_doc)
        self.assertIsNotNone(result.inserted_id)
        
        # Récupération
        retrieved = mongo_db['fichiers_uploades'].find_one({
            "fichier_source_id": "test-123"
        })
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(
            retrieved['structure_json']['sections'][0]['content'], 
            "Test"
        )
    
    def test_get_fichier_json_structure(self):
        """Vérifie la récupération du JSON depuis MongoDB."""
        fichier = FichierSource.objects.create(
            enseignant=self.enseignant,
            titre="Test Mongo Retrieval",
            fichier_original=SimpleUploadedFile("test.txt", b"test")
        )
        
        # Stockage manuel dans MongoDB
        mongo_db = get_mongo_db()
        mongo_db['fichiers_uploades'].insert_one({
            "fichier_source_id": str(fichier.id),
            "structure_json": {"test": "data"}
        })
        
        # Récupération via utilitaire
        retrieved = get_fichier_json_structure(fichier.id)
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved['structure_json']['test'], 'data')
    
    def tearDown(self):
        """Nettoyage après tests."""
        mongo_db = get_mongo_db()
        mongo_db['fichiers_uploades'].delete_many({})
        mongo_db['granules'].delete_many({})


class JsonUtilsTestCase(TestCase):
    """Tests des utilitaires JSON."""
    
    def setUp(self):
        """Préparation des données de test."""
        self.user = Utilisateur.objects.create_user(
            username='prof_utils',
            email='utils@test.com',
            password='test123',
            type_compte='ENSEIGNANT'
        )
        
        self.enseignant = Enseignant.objects.create(
            utilisateur=self.user,
            specialite='Utils',
            departement='Test'
        )
        
        # Création d'un cours complet
        self.cours = Cours.objects.create(
            enseignant=self.enseignant,
            titre="Cours Test Utils",
            code="TEST-UTILS",
            description="Test"
        )
    
    def test_get_cours_complete_structure(self):
        """Vérifie l'export complet d'un cours."""
        structure = get_cours_complete_structure(self.cours)
        
        self.assertIn('cours', structure)
        self.assertIn('parties', structure)
        self.assertEqual(structure['cours']['code'], 'TEST-UTILS')
    
    def test_statistics(self):
        """Vérifie les statistiques MongoDB."""
        from .json_utils import get_statistics
        
        stats = get_statistics()
        
        self.assertIn('fichiers_uploades', stats)
        self.assertIn('granules', stats)
        self.assertIn('database_name', stats)


# ==============================================================================
# COMMANDES DE TEST
# ==============================================================================
# Pour exécuter tous les tests:
#   python manage.py test xcsm
#
# Pour un test spécifique:
#   python manage.py test xcsm.tests.JsonStructureTestCase.test_parse_html_to_json_basic
#
# Avec verbosité:
#   python manage.py test xcsm --verbosity=2