# create_enseignant.py
# Script pour créer un enseignant de test dans XCSM

from xcsm.models import Utilisateur

# Email de l'enseignant de test
email_test = "test@example.com"
password_test = "Test123456!"

try:
    # Vérifier si l'utilisateur existe déjà
    user_existant = Utilisateur.objects.get(email=email_test)
    print(f"✅ Enseignant existe déjà:")
    print(f"   ID: {user_existant.id}")
    print(f"   Email: {user_existant.email}")
    print(f"   Nom: {user_existant.prenom} {user_existant.nom}")
    print(f"   Rôle: {user_existant.role}")
    
except Utilisateur.DoesNotExist:
    print(f"📝 Création d'un nouvel enseignant...")
    
    # Créer l'utilisateur (utilise create_user pour hasher le mot de passe)
    user = Utilisateur.objects.create_user(
        email=email_test,
        nom='Test',
        prenom='Enseignant',
        password=password_test,
        role='enseignant'
    )
    
    print(f"✅ Utilisateur créé avec succès:")
    print(f"   ID: {user.id}")
    print(f"   Email: {user.email}")
    print(f"   Nom: {user.prenom} {user.nom}")
    print(f"   Rôle: {user.role}")
    print(f"\n🔑 Identifiants de connexion:")
    print(f"   Email: {email_test}")
    print(f"   Mot de passe: {password_test}")

# Vérification finale - Afficher tous les enseignants
print(f"\n📊 Liste de tous les enseignants:")
enseignants = Utilisateur.objects.filter(role='enseignant')
print(f"   Nombre total: {enseignants.count()}")

for ens in enseignants:
    print(f"\n   - {ens.prenom} {ens.nom}")
    print(f"     Email: {ens.email}")
    print(f"     ID: {ens.id}")