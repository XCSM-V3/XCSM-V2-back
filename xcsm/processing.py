# import fitz                   # Pour PyMuPDF
# import os
# import re
# import io
# import mammoth                # Pour la conversion DOCX
# from bs4 import BeautifulSoup # Pour le nettoyage final
# from django.db import transaction
# from .utils import get_mongo_db
# # IMPORTS NÉCESSAIRES POUR LE DÉCOUPAGE (MySQL Models)
# from .models import Cours, Partie, Chapitre, Section, SousSection, Granule



# # ==============================================================================
# # 1. OUTIL DE POST-TRAITEMENT (Cœur de la Granulation)
# # ==============================================================================

# def post_process_semantic_html(raw_html: str) -> str:
#     """
#     Fonction CRITIQUE : Prend du HTML brut et force le découpage ligne par ligne.
#     Transforme les blocs <p> multi-lignes en plusieurs <p> unitaires.
#     """
#     soup = BeautifulSoup(raw_html, 'html.parser')
#     new_body = ""
    
#     # On parcourt chaque élément de premier niveau (H1, P, UL, etc.)
#     for element in soup.body.contents:
#         if element.name is None: # Ignore les sauts de ligne entre les balises
#             continue
            
#         tag_name = element.name
#         text = element.get_text().strip()
        
#         if not text:
#             continue
            
#         # A. LES TITRES : On les garde intacts (Unités sémantiques fortes)
#         if tag_name in ['h1', 'h2', 'h3', 'h4']:
#             new_body += f"<{tag_name}>{text}</{tag_name}>\n"
        
#         # B. LES PARAGRAPHES & LISTES : On découpe chaque ligne !
#         elif tag_name in ['p', 'li', 'ul', 'ol', 'div']:
#             # On sépare par les retours à la ligne présents dans le texte source
#             lines = [line.strip() for line in text.split('\n') if line.strip()]
            
#             for line in lines:
#                 # Nettoyage des caractères invisibles (espaces insécables, tabulations)
#                 clean_line = re.sub(r'[\u00A0\t\r]+', ' ', line).strip()
                
#                 # Heuristique : Si la ligne commence par un tiret ou un chiffre, c'est une liste
#                 if re.match(r'^[-•*]\s+', clean_line) or re.match(r'^\d+\.\s+', clean_line):
#                     # On peut choisir de garder <p> ou mettre <li>, restons sur <p> pour la simplicité
#                     new_body += f"<p>{clean_line}</p>\n"
#                 elif clean_line:
#                     new_body += f"<p>{clean_line}</p>\n"
        
#         # C. AUTRES (Images, Tableaux...) : On garde tel quel
#         else:
#             new_body += str(element) + "\n"

#     return f"<html><body>\n{new_body}</body></html>"

# # ==============================================================================
# # 2. CONVERTISSEURS SPÉCIFIQUES
# # ==============================================================================

# def convert_docx_to_semantic_html(file_path):
#     """ Utilise Mammoth pour DOCX + Post-traitement granulaire """
#     # Mapping strict pour récupérer les vrais titres Word
#     style_map = """
#     p[style-name='Title'] => h1:fresh
#     p[style-name='Heading 1'] => h1:fresh
#     p[style-name='Heading 2'] => h2:fresh
#     p[style-name='Heading 3'] => h3:fresh
#     """
    
#     with open(file_path, 'rb') as docx_file:
#         # Mammoth convertit le DOCX en HTML brut
#         result = mammoth.convert_to_html(docx_file, style_map=style_map)
#         raw_html = f"<html><body>{result.value}</body></html>"
        
#     # On passe le résultat à notre découpeur ligne par ligne
#     return post_process_semantic_html(raw_html)


# def convert_pdf_to_semantic_html(file_path):
#     """ Utilise PyMuPDF + Heuristique Titres + Post-traitement granulaire """
#     document = fitz.open(file_path)
#     raw_text = ""
#     for page_num in range(len(document)):
#         page = document.load_page(page_num)
#         raw_text += page.get_text("text") 
#         raw_text += "\n" # Séparateur simple
        
#     content_blocks = re.split(r'\n\s*\n', raw_text)
#     semantic_parts = ""
    
#     for block in content_blocks:
#         block = block.strip()
#         if not block or '--- PAGE BREAK ---' in block: continue
            
#         # Détection H1/H2 (Ligne unique, courte, majuscule ou numérotée)
#         is_single = len(block.split('\n')) == 1
#         is_short = len(block) < 150
        
#         if is_single and is_short and (block.isupper() or re.match(r'^[IVX]+\.', block)):
#              # C'est un titre -> On l'enveloppe direct
#              tag = 'h1' if block.isupper() else 'h2'
#              semantic_parts += f"<{tag}>{block}</{tag}>\n"
#         else:
#              # C'est du texte -> On le met dans un <p> temporaire
#              # Le post-processeur se chargera de le redécouper ligne par ligne
#              semantic_parts += f"<p>{block}</p>\n"
                
#     return post_process_semantic_html(f"<html><body>{semantic_parts}</body></html>")


# # ==============================================================================
# # 3. MOTEUR DE DÉCOUPAGE (GRANULATION)
# # ==============================================================================

# def split_and_create_granules(fichier_source, html_content):
#     """
#     Analyse le HTML sémantique et peuple la base de données MySQL et MongoDB.
#     Crée la hiérarchie : Cours -> Partie -> Chapitre -> Section -> Granule
#     """
#     mongo_db = get_mongo_db()
#     granules_collection = mongo_db['granules']
    
#     soup = BeautifulSoup(html_content, 'html.parser')
    
#     # 1. Création du Conteneur Principal (Le Cours Brouillon)
#     # On vérifie si un cours existe déjà pour ce fichier, sinon on crée
#     cours, created = Cours.objects.get_or_create(
#         code=f"AUTO-{fichier_source.id.hex[:8].upper()}", # Code temporaire unique
#         defaults={
#             'enseignant': fichier_source.enseignant,
#             'titre': f"Cours issu de : {fichier_source.titre}",
#             'description': "Généré automatiquement par XCSM",
#             'matiere': "Non définie",
#             'niveau': "Non défini",
#             'est_publie': False
#         }
#     )
    
#     # Création d'une Partie par défaut (Racine)
#     partie_actuelle = Partie.objects.create(
#         cours=cours,
#         titre="Partie Principale",
#         numero=1
#     )
    
#     # Pointeurs de contexte (pour savoir où ranger les granules)
#     chapitre_actuel = None
#     section_actuelle = None
#     sous_section_actuelle = None
    
#     # Compteurs pour l'ordre
#     ordres = {'chapitre': 1, 'section': 1, 'sous_section': 1, 'granule': 1}

#     # 2. Parcours séquentiel du HTML
#     for element in soup.body.contents:
#         if element.name is None: continue
        
#         tag = element.name
#         text = element.get_text().strip()
#         if not text: continue

#         # --- NIVEAU 1 : CHAPITRE (H1) ---
#         if tag == 'h1':
#             chapitre_actuel = Chapitre.objects.create(
#                 partie=partie_actuelle,
#                 titre=text[:199], # Limite charfield
#                 numero=ordres['chapitre']
#             )
#             ordres['chapitre'] += 1
#             # Reset des niveaux inférieurs
#             section_actuelle = None 
#             sous_section_actuelle = None
#             ordres['section'] = 1

#         # --- NIVEAU 2 : SECTION (H2) ---
#         elif tag == 'h2':
#             # Si pas de chapitre, on en crée un par défaut
#             if not chapitre_actuel:
#                 chapitre_actuel = Chapitre.objects.create(partie=partie_actuelle, titre="Introduction", numero=ordres['chapitre'])
#                 ordres['chapitre'] += 1
            
#             section_actuelle = Section.objects.create(
#                 chapitre=chapitre_actuel,
#                 titre=text[:199],
#                 numero=ordres['section']
#             )
#             ordres['section'] += 1
#             # Reset niveau inférieur
#             sous_section_actuelle = None
#             ordres['sous_section'] = 1

#         # --- NIVEAU 3 : GRANULE (P, LI, etc.) ---
#         elif tag in ['p', 'li', 'ul', 'ol', 'div', 'h3']: 
#             # Note: On traite H3 comme un granule de titre pour simplifier, ou on pourrait créer SousSection
            
#             # Gestion de la hiérarchie minimale pour attacher le granule
#             if not section_actuelle:
#                 if not chapitre_actuel:
#                     chapitre_actuel = Chapitre.objects.create(partie=partie_actuelle, titre="Introduction Générale", numero=ordres['chapitre'])
#                 section_actuelle = Section.objects.create(chapitre=chapitre_actuel, titre="Section Générale", numero=ordres['section'])
            
#             # Si pas de sous-section, on en crée une "contenu" par défaut ou on attache à une sous-section générique
#             if not sous_section_actuelle:
#                 sous_section_actuelle = SousSection.objects.create(
#                     section=section_actuelle, 
#                     titre="Contenu", 
#                     numero=ordres['sous_section']
#                 )
#                 ordres['sous_section'] += 1

#             # A. Stockage Contenu Riche dans MongoDB
#             granule_mongo = {
#                 "html_content": str(element), # On garde le HTML (<p>...</p>)
#                 "texte_brut": text,
#                 "fichier_source_id": str(fichier_source.id)
#             }
#             res_mongo = granules_collection.insert_one(granule_mongo)
            
#             # B. Création Métadonnées dans MySQL
#             Granule.objects.create(
#                 sous_section=sous_section_actuelle,
#                 fichier_source=fichier_source,
#                 titre=text[:50] + "..." if len(text) > 50 else text, # Aperçu du titre
#                 type_contenu="TEXTE",
#                 mongo_contenu_id=str(res_mongo.inserted_id),
#                 ordre=ordres['granule']
#             )
#             ordres['granule'] += 1

#     return cours

# # ==============================================================================
# # 3. ORCHESTRATEUR (INCHANGÉ)
# # ==============================================================================

# def process_and_store_document(fichier_source_instance):
#     file_path = fichier_source_instance.fichier_original.path
#     file_extension = os.path.splitext(file_path)[1].lower().lstrip('.')
    
#     try:
#         # 1. Extraction & Nettoyage
#         if file_extension == 'docx':
#             semantic_html = convert_docx_to_semantic_html(file_path)
#         elif file_extension == 'pdf':
#             semantic_html = convert_pdf_to_semantic_html(file_path)
#         else:
#             with open(file_path, 'r', encoding='utf-8') as f:
#                 semantic_html = post_process_semantic_html(f"<html><body><p>{f.read()}</p></body></html>")
        
#         if not semantic_html or len(semantic_html) < 50:
#             raise ValueError("Contenu vide ou trop court.")

#         # 2. Stockage HTML Global (MongoDB)
#         mongo_db = get_mongo_db()
#         res = mongo_db['fichiers_uploades'].insert_one({
#             "fichier_source_id": str(fichier_source_instance.id),
#             "titre": fichier_source_instance.titre,
#             "type_original": file_extension.upper(),
#             "contenu_transforme": semantic_html,
#             "date_traitement": fichier_source_instance.date_upload.isoformat()
#         })
        
#         # 3. DÉCOUPAGE INTELLIGENT (Nouvelle étape)
#         # On passe le HTML propre au moteur de découpage
#         cours_genere = split_and_create_granules(fichier_source_instance, semantic_html)
        
#         # 4. Finalisation MySQL
#         with transaction.atomic():
#             fichier_source_instance.mongo_transforme_id = str(res.inserted_id)
#             fichier_source_instance.statut_traitement = 'TRAITE'
#             fichier_source_instance.type_mime = f'text/html_semantic'
#             fichier_source_instance.save()
        
#         return True, f"Traité avec succès. Cours généré : {cours_genere.titre}"
        
#     except Exception as e:
#         print(f"Erreur : {e}")
#         with transaction.atomic():
#             fichier_source_instance.statut_traitement = 'ERREUR'
#             fichier_source_instance.save()
#         return False, str(e)



# xcsm/processing.py - Version JSON Structuré (Refonte Complète)
import fitz  # PyMuPDF
import unicodedata
import os
import re
import mammoth
from bs4 import BeautifulSoup
from django.db import transaction
from .utils import get_mongo_db
from .models import (
    Cours, Partie, Chapitre, Section, SousSection, Granule,
    Exercice, Question, Reponse, Tag, Categorie, Organisation
)
from datetime import datetime

# ==============================================================================
# 1. CONVERSION VERS JSON STRUCTURÉ (Remplacement du HTML)
# ==============================================================================

def extract_structure_from_docx(file_path):
    """
    Convertit un DOCX en JSON structuré avec hiérarchie sémantique.
    Retourne: {"metadata": {...}, "sections": [...]}
    """
    style_map = """
    p[style-name='Title'] => h1:fresh
    p[style-name='Heading 1'] => h1:fresh
    p[style-name='Heading 2'] => h2:fresh
    p[style-name='Heading 3'] => h3:fresh
    """
    
    with open(file_path, 'rb') as f:
        result = mammoth.convert_to_html(f, style_map=style_map)
        html = f"<html><body>{result.value}</body></html>"
    
    return parse_html_to_json_structure(html)


def extract_structure_from_pdf(file_path):
    """
    ANALYSE AVANCÉE PDF : Utilise la taille et le style des polices pour identifier la structure.
    """
    doc = fitz.open(file_path)
    
    # 1. ANALYSE STATISTIQUE DES POLICES
    # On récupère toutes les tailles de police du document pour trouver la "taille du corps"
    font_sizes = []
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b: # Bloc de texte
                for l in b["lines"]:
                    for s in l["spans"]:
                        if s["text"].strip():
                            font_sizes.append(round(s["size"], 1))
    
    # La taille la plus fréquente est probablement le corps de texte
    if not font_sizes:
         return parse_html_to_json_structure("<html><body><p>Document Vide</p></body></html>")
         
    from collections import Counter
    size_distribution = Counter(font_sizes)
    body_font_size = size_distribution.most_common(1)[0][0]
    
    print(f"📊 Analyse PDF : Taille du corps détectée = {body_font_size}pt")
    
    html_parts = ""
    
    # 2. EXTRACTION ET CLASSIFICATION
    for page_num, page in enumerate(doc, 1):
        blocks = page.get_text("dict")["blocks"]
        
        for b in blocks:
            if "lines" not in b: continue
            

            for l in b["lines"]:
                # Reconstruction de la ligne (qui peut avoir plusieurs styles)
                raw_text = "".join([s["text"] for s in l["spans"]]).strip()
                
                try:
                    # Regex pour intervertir : [Espace éventuel][Accent combinant OU espacé][Espace éventuel][Lettre]
                    # Inclut U+00B4 (Acute), U+0060 (Grave), U+005E (Circumflex), U+00A8 (Diaeresis)
                    pattern = r"(\s*)([\u0300-\u036f\u00B4\u0060\^¨])(\s*)([a-zA-Z])"
                    
                    def accent_replacer(match):
                        accent = match.group(2)
                        letter = match.group(4)
                        # Map accents espacés vers accent combinants pour que NFKC fonctionne
                        charmap = {
                            '\u00B4': '\u0301', # Acute
                            '\u0060': '\u0300', # Grave
                            '^': '\u0302',      # Circumflex
                            '¨': '\u0308'       # Diaeresis
                        }
                        combining = charmap.get(accent, accent)
                        return letter + combining

                    fixed_text = re.sub(pattern, accent_replacer, raw_text)
                    line_text = unicodedata.normalize('NFKC', fixed_text)
                except Exception:
                    line_text = unicodedata.normalize('NFKC', raw_text)

                if not line_text: continue
                
                # On prend le style du premier span significatif pour classifier la ligne
                first_span = l["spans"][0]
                size = round(first_span["size"], 1)
                flags = first_span["flags"]
                is_bold = bool(flags & 16) # 16 = Bold
                is_upper = line_text.isupper()
                
                # --- HEURISTIQUES DE DÉTECTION ---
                tag = "p"
                
                # On évite de prendre pour titre des lignes non pertinentes
                # - Trop courtes (ex: numéros de page)
                # - Purement numériques
                # - Terminant par une ponctuation de fin de phrase
                # - Commençant par un mot de type "Page", "Figure", etc.
                
                is_likely_not_header = (
                    len(line_text) < 5 or 
                    line_text.isdigit() or 
                    line_text.strip().endswith(('.', ':', '!', '?')) or
                    line_text.lower().startswith(('page ', 'figure ', 'table ', 'note :'))
                )

                # TITRE NIVEAU 1 (Très grand ou Grand + Gras + Majuscules)
                if not is_likely_not_header:
                    if size > body_font_size + 4:
                        tag = "h1"
                    elif size > body_font_size + 2 and is_bold:
                        tag = "h1"
                    
                    # TITRE NIVEAU 2 (Plus grand que le corps ou Gras + Couleur/Style)
                    elif size > body_font_size + 1:
                        tag = "h2"
                    elif is_bold and (is_upper or size > body_font_size):
                        tag = "h2"
                
                # Listes et autres peuvent être détectées ici
                
                # Ajout au HTML avec métadonnée de page pour le frontend
                html_parts += f'<{tag} data-page="{page_num}">{line_text}</{tag}>\n'

    return parse_html_to_json_structure(f"<html><body>{html_parts}</body></html>")
def extract_structure_from_txt(file_path):
    """ TXT -> JSON Structure (Simple) """
    # Tentative 1: UTF-8 avec BOM (utf-8-sig) ou sans
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            text = f.read()
    except UnicodeDecodeError:
        # Tentative 2: CP1252 (Windows Western Europe)
        print(f"⚠️ Échec lecture UTF-8 pour {file_path}, tentative CP1252...")
        try:
             with open(file_path, 'r', encoding='cp1252') as f:
                text = f.read()
        except UnicodeDecodeError:
            # Tentative 3: Latin-1 (Fallback ultime, ne plante jamais mais peut mal interpréter)
            print(f"⚠️ Échec lecture CP1252, tentative Latin-1...")
            with open(file_path, 'r', encoding='latin-1') as f:
                text = f.read()
    
    html_parts = ""
    # Heuristique simple pour le TXT
    blocks = re.split(r'\n\s*\n', text)
    
    for i, block in enumerate(blocks):
        block = block.strip()
        if not block: continue
        
        # Premier bloc = Titre probable
        if i == 0 and len(block) < 200:
            html_parts += f"<h1>{block}</h1>\n"
            continue
            
        lines = block.split('\n')
        is_title = len(lines) == 1 and len(block) < 100
        
        if is_title and block.isupper():
            html_parts += f"<h2>{block}</h2>\n"
        else:
            html_parts += f"<p>{block}</p>\n"
            
    return parse_html_to_json_structure(f"<html><body>{html_parts}</body></html>")


def parse_html_to_json_structure(html_content):
    """
    CŒUR DE LA TRANSFORMATION : Convertit le HTML en structure JSON hiérarchique.
    Format de sortie:
    {
        "metadata": {"source_type": "pdf/docx", "extraction_date": "..."},
        "sections": [
            {
                "type": "h1/h2/p",
                "level": 1/2/3,
                "content": "texte brut",
                "html": "<h1>texte</h1>",  # Conservé pour compatibilité
                "children": [...]  # Granules enfants si applicable
            }
        ]
    }
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    root = soup.body if soup.body else soup
    
    structure = {
        "metadata": {
            "extraction_date": datetime.now().isoformat(),
            "version": "2.0-JSON"
        },
        "sections": []
    }
    
    current_h1 = None
    current_h2 = None
    
    for element in root.contents:
        if element.name is None:
            continue
        
        tag = element.name
        text = element.get_text().strip()
        
        if not text:
            continue
        
        # Extraction des métadonnées (Page, etc.)
        page_num = element.attrs.get('data-page')
        
        # Construction du nœud JSON
        node = {
            "type": tag,
            "level": get_semantic_level(tag),
            "content": text,
            "html": str(element),  # Conservé pour rétro-compatibilité
            "children": [],
            "metadata": { "page": page_num } if page_num else {}
        }
        
        # Gestion de la hiérarchie
        if tag == 'h1':
            structure["sections"].append(node)
            current_h1 = node
            current_h2 = None
        
        elif tag == 'h2':
            if current_h1:
                current_h1["children"].append(node)
            else:
                structure["sections"].append(node)
            current_h2 = node
        
        elif tag in ['h3', 'p', 'li', 'div']:
            # Découpage ligne par ligne pour les paragraphes
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            for line in lines:
                clean_line = re.sub(r'[\u00A0\t\r]+', ' ', line).strip()
                if not clean_line:
                    continue
                
                granule_node = {
                    "type": "granule",
                    "level": 4,
                    "content": clean_line,
                    "html": f"<p>{clean_line}</p>",
                    "metadata": { "page": page_num } if page_num else {}
                }
                
                # Attachement au bon parent
                if current_h2:
                    current_h2["children"].append(granule_node)
                elif current_h1:
                    current_h1["children"].append(granule_node)
                else:
                    structure["sections"].append(granule_node)
    
    return structure


def get_semantic_level(tag):
    """Retourne le niveau sémantique d'une balise."""
    levels = {'h1': 1, 'h2': 2, 'h3': 3, 'h4': 4, 'p': 4, 'li': 4, 'div': 4}
    return levels.get(tag, 5)


# ==============================================================================
# 2. DÉCOUPAGE ET STOCKAGE (Version JSON)
# ==============================================================================

def split_and_create_granules(fichier_source, json_structure, target_course_id=None):
    """
    Analyse la structure JSON et crée la hiérarchie MySQL + stockage MongoDB.
    Si target_course_id est fourni, on met à jour ce cours spécifiquement.
    """
    mongo_db = get_mongo_db()
    granules_col = mongo_db['granules']
    
    # A. NETTOYAGE des anciens granules
    Granule.objects.filter(fichier_source=fichier_source).delete()
    
    # B. RÉCUPÉRATION / CRÉATION DU COURS
    # Le cours est désormais attaché à la MATIÈRE du fichier
    
    if not fichier_source.matiere:
        print(f"⚠️ Fichier {fichier_source.id} sans matière parente. Création orpheline impossible.")
        # Fallback temporaire ou erreur ? 
        # Pour l'instant on raise une erreur car la matière est obligatoire dans la nouvelle logique
        raise ValueError("Impossible de traiter un fichier sans matière associée.")

    matiere = fichier_source.matiere
    
    # On cherche s'il existe déjà un cours pour ce fichier dans cette matière
    # Ou logique simplifiée : Un fichier = Un cours ?
    # Oui, "La vcreation d'un cours exige l'upload d'unn document qui sera le document de ce cours"
    
    cours, created = Cours.objects.get_or_create(
        matiere=matiere,
        titre=fichier_source.titre,
        defaults={
            'enseignant': fichier_source.enseignant,
            'description': f"Cours généré depuis {fichier_source.titre}",
            'est_publie': False
        }
    )
    
    if created:
        print(f"✅ Nouveau cours créé : {cours.titre} dans {matiere.titre}")
    else:
        print(f"♻️ Mise à jour du cours existant : {cours.titre}")
    
    # Nettoyage des anciennes parties
    Partie.objects.filter(cours=cours).delete()
    
    # C. INITIALISATION DE LA HIÉRARCHIE
    partie = Partie.objects.create(cours=cours, titre="Contenu Principal", numero=1)
    chapitre = Chapitre.objects.create(partie=partie, titre="Introduction", numero=1)
    section = Section.objects.create(chapitre=chapitre, titre="Généralités", numero=1)
    sous_section = SousSection.objects.create(section=section, titre="Contenu", numero=1)
    
    counters = {'chapitre': 1, 'section': 1, 'granule': 1}
    
    # D. PARCOURS DE LA STRUCTURE JSON
    for node in json_structure.get("sections", []):
        process_json_node(
            node, fichier_source, granules_col,
            partie, chapitre, section, sous_section, counters
        )
    
    return cours


def process_json_node(node, fichier_source, granules_col, 
                     partie, chapitre, section, sous_section, counters):
    """
    Traite récursivement un nœud JSON et crée les entités MySQL/MongoDB.
    """
    node_type = node.get("type")
    content = node.get("content", "")
    children = node.get("children", [])
    
    # NIVEAU 1: CHAPITRE (H1)
    if node_type == 'h1':
        counters['chapitre'] += 1
        chapitre = Chapitre.objects.create(
            partie=partie,
            titre=content[:190],
            numero=counters['chapitre']
        )
        section = Section.objects.create(
            chapitre=chapitre, 
            titre="Début", 
            numero=1
        )
        sous_section = SousSection.objects.create(
            section=section, 
            titre="Contenu", 
            numero=1
        )
        counters['section'] = 1
        
        # Traitement des enfants
        for child in children:
            process_json_node(
                child, fichier_source, granules_col,
                partie, chapitre, section, sous_section, counters
            )
    
    # NIVEAU 2: SECTION (H2)
    elif node_type == 'h2':
        counters['section'] += 1
        section = Section.objects.create(
            chapitre=chapitre,
            titre=content[:190],
            numero=counters['section']
        )
        sous_section = SousSection.objects.create(
            section=section, 
            titre="Contenu", 
            numero=1
        )
        
        # Traitement des enfants
        for child in children:
            process_json_node(
                child, fichier_source, granules_col,
                partie, chapitre, section, sous_section, counters
            )
    
    # NIVEAU 3: GRANULE
    elif node_type in ['granule', 'h3', 'p', 'li', 'div']:
        # Stockage MongoDB (JSON pur)
        granule_mongo = {
            "type": node_type,
            "content": content,
            "html": node.get("html", f"<p>{content}</p>"),
            "fichier_source_id": str(fichier_source.id),
            "metadata": {
                "level": node.get("level", 4),
                "extraction_date": datetime.now().isoformat(),
                "page": node.get("metadata", {}).get("page")
            }
        }
        res = granules_col.insert_one(granule_mongo)
        
        # Récupération du numéro de page (si présent)
        page_num_str = node.get("metadata", {}).get("page")
        page_num = int(page_num_str) if page_num_str and str(page_num_str).isdigit() else None
        
        # Stockage MySQL (métadonnées)
        Granule.objects.create(
            sous_section=sous_section,
            fichier_source=fichier_source,
            titre=content[:45] + "..." if len(content) > 45 else content,
            type_contenu="TEXTE",
            mongo_contenu_id=str(res.inserted_id),
            ordre=counters['granule'],
            source_pdf_page=page_num
        )
        counters['granule'] += 1


# ==============================================================================
# 3. ORCHESTRATEUR PRINCIPAL (Point d'entrée)
# ==============================================================================


# Ajout des imports nécessaires pour l'extraction d'images
import fitz  # PyMuPDF
import io
import os
from django.core.files.base import ContentFile
from .models import Ressource

def extract_images_from_pdf(fichier_source_instance):
    """
    Extrait les images d'un PDF et les enregistre comme Ressources.
    """
    try:
        pdf_path = fichier_source_instance.fichier_original.path
        doc = fitz.open(pdf_path)
        
        count = 0
        for page_index in range(len(doc)):
            page = doc[page_index]
            image_list = page.get_images()
            
            for image_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Filtrage des petites icônes/bruit (ex: < 5KB)
                if len(image_bytes) < 5000:
                    continue
                
                # Création du fichier en mémoire
                image_name = f"img_{fichier_source_instance.id.hex[:6]}_p{page_index+1}_{image_index}.{image_ext}"
                content_file = ContentFile(image_bytes, name=image_name)
                
                # Création de la ressource
                Ressource.objects.create(
                    fichier_source=fichier_source_instance,
                    titre=f"Image Page {page_index+1}",
                    fichier=content_file,
                    type_ressource='IMAGE'
                )
                count += 1
                
        print(f"🖼️ {count} images extraites du PDF.")
        return count
    except Exception as e:
        print(f"❌ Erreur extraction images PDF: {e}")
        return 0


def process_and_store_document(fichier_source_instance):
    """
    Fonction principale (Point d'entrée) appelée par la vue ou la tâche Celery.
    Orchestre tout le processus.
    """
    file_path = fichier_source_instance.fichier_original.path
    ext = file_path.split('.')[-1].lower() # Changed to lower() to match existing logic
    
    # 0. EXTRACTION DES IMAGES (Si PDF)
    if ext == 'pdf': # Changed to 'pdf' to match existing logic
        print("🖼️ Extraction des images du PDF...")
        extract_images_from_pdf(fichier_source_instance)

    # 1. ANALYSE ET EXTRACTION DU TEXTE
    print(f"🚀 Début traitement {file_path} (Type: {ext.upper()})") # Changed to ext.upper() for consistency
    try:
        path = fichier_source_instance.fichier_original.path
        # ext = os.path.splitext(path)[1].lower().strip('.') # This line is now redundant
        
        # 1. EXTRACTION → JSON STRUCTURÉ
        print(f"📄 Extraction {ext.upper()} → JSON...")
        if ext == 'docx':
            json_structure = extract_structure_from_docx(path)
        elif ext == 'pdf':
            json_structure = extract_structure_from_pdf(path)
        elif ext == 'txt':
            json_structure = extract_structure_from_txt(path)
        else:
            raise ValueError(f"Format {ext} non supporté")
        
        # FALLBACK: Si aucune section n'est trouvée (doc plat), on crée une structure par défaut
        if not json_structure.get("sections"):
            print("⚠️ Aucune section détectée, création d'une structure par défaut.")
            json_structure["sections"] = [{
                "type": "h1",
                "level": 1,
                "content": "Document Complet",
                "children": [{
                    "type": "granule",
                    "level": 4, 
                    "content": "Contenu du document (structure non détectée)",
                    "html": "<p>Le contenu du document n'a pas pu être structuré automatiquement.</p>"
                }]
            }]
            # Tente de récupérer tout texte brut disponible si possible (TODO: Améliorer l'extraction texte brut)
        
        # 2. STOCKAGE MONGODB - DOCUMENT COMPLET (UPSERT)
        print(f"💾 Stockage MongoDB fichiers_uploades...")
        mongo_db = get_mongo_db()
        
        # On utilise update_one + upsert pour éviter les doublons avec l'éditeur
        mongo_db['fichiers_uploades'].update_one(
            {"fichier_source_id": str(fichier_source_instance.id)},
            {
                "$set": {
                    "titre": fichier_source_instance.titre,
                    "type_original": ext.upper(),
                    "structure_json": json_structure,
                    "date_traitement": datetime.now().isoformat(),
                    "version": "2.0-JSON"
                }
            },
            upsert=True
        )
        
        # Récupération de l'ID (nécessaire pour la liaison MySQL)
        doc = mongo_db['fichiers_uploades'].find_one({"fichier_source_id": str(fichier_source_instance.id)})
        mongo_result_id = doc['_id']
        
        # 3. DÉCOUPAGE ET HIÉRARCHISATION
        print(f"🔨 Création hiérarchie MySQL + granules MongoDB...")
        cours = split_and_create_granules(fichier_source_instance, json_structure)
        
        # 4. FINALISATION
        with transaction.atomic():
            fichier_source_instance.mongo_transforme_id = str(mongo_result_id)
            fichier_source_instance.statut_traitement = 'TRAITE'
            fichier_source_instance.save()
        
        print(f"✅ Traitement terminé avec succès")
        return True, f"Cours généré : {cours.titre}"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        with transaction.atomic():
            fichier_source_instance.statut_traitement = 'ERREUR'
            fichier_source_instance.save()
        
        return False, f"Erreur: {str(e)}"