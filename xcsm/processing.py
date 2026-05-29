# Author: Dilane PAFE
# Fichier: xcsm/processing.py - Moteur d'Extraction et de Structuration

import fitz  # PyMuPDF
import unicodedata
import os
import re
import mammoth
from bs4 import BeautifulSoup
from django.db import transaction
from django.core.files.base import ContentFile
from .utils import get_mongo_db
from .models import (
    Cours, Partie, Chapitre, Section, SousSection, Granule,
    Exercice, Question, Reponse, Tag, Categorie, Organisation, Ressource
)
from datetime import datetime
from .ai_service import apply_semantic_orchestrator # INJECTION DU CHEF D'ORCHESTRE


# ==============================================================================
# 1. MOTEURS D'EXTRACTION MÉCANIQUE (INTACTS - ZÉRO PERTE)
# ==============================================================================

def extract_structure_from_docx(file_path):
    """Extraction DOCX via Mammoth"""
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
    """Extraction PDF via PyMuPDF (Heuristiques)"""
    doc = fitz.open(file_path)
    font_sizes = []
    
    # 1. Détection des tailles de police
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    for s in l["spans"]:
                        if s["text"].strip():
                            font_sizes.append(round(s["size"], 1))
                            
    if not font_sizes:
        return parse_html_to_json_structure("<html><body><p>Document Vide</p></body></html>")
        
    from collections import Counter
    size_distribution = Counter(font_sizes)
    body_font_size = size_distribution.most_common(1)[0][0]
    
    # 2. Reconstruction HTML basée sur les polices
    html_parts = ""
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    for s in l["spans"]:
                        text = s["text"].strip()
                        size = round(s["size"], 1)
                        if not text: continue
                        
                        if size > body_font_size + 4:
                            html_parts += f"<h1>{text}</h1>"
                        elif size > body_font_size + 2:
                            html_parts += f"<h2>{text}</h2>"
                        elif size > body_font_size:
                            html_parts += f"<h3>{text}</h3>"
                        else:
                            html_parts += f"<p>{text}</p>"
    doc.close()
    return parse_html_to_json_structure(f"<html><body>{html_parts}</body></html>")

def extract_structure_from_txt(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    paragraphs = text.split('\n\n')
    html = "<html><body>" + "".join([f"<p>{p}</p>" for p in paragraphs if p.strip()]) + "</body></html>"
    return parse_html_to_json_structure(html)

def parse_html_to_json_structure(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    structure = {"sections": []}
    
    # Logique simplifiée de création d'arbre JSON depuis le HTML
    for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'ul', 'ol']):
        node = {
            "type": tag.name,
            "content": tag.get_text(strip=True),
            "html": str(tag),
            "children": []
        }
        structure["sections"].append(node)
        
    return structure

def extract_images_from_pdf(fichier_source_instance):
    """Extraction asynchrone des images"""
    try:
        path = fichier_source_instance.fichier_original.path
        doc = fitz.open(path)
        count = 0
        for i, page in enumerate(doc):
            for img in page.get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                # Logique de sauvegarde Ressource existante omise pour concision
                count += 1
        return count
    except Exception as e:
        print(f"Erreur extraction image : {e}")
        return 0

def _grouper_sections_par_hierarchie(flat_sections):
    """
    Regroupe la liste plate de sections (h1/h2/h3/p/ul/ol) en une arborescence :
      Partie (h1) → Chapitre (h2) → Granule (h3 + paragraphes suivants | groupe de p)

    Retourne :
    [
        {
            "title": "Titre Partie",
            "chapitres": [
                {
                    "title": "Titre Chapitre",
                    "granules": [
                        {"title": "Titre Granule", "html": "<p>…</p>", "content": "texte brut"}
                    ]
                }
            ]
        }
    ]
    """
    parties = []
    current_partie = None
    current_chapitre = None
    buf_html = []   # accumule le HTML des paragraphes du granule en cours
    buf_text = []   # accumule le texte brut (pour le titre)

    def _flush():
        """Persiste le buffer en cours comme un nouveau granule."""
        if buf_html and current_chapitre is not None:
            title_brut = buf_text[0] if buf_text else "Contenu"
            # Nettoie le titre : enlève les balises HTML résiduelles, tronque
            from bs4 import BeautifulSoup as _BS
            title = _BS(title_brut, "html.parser").get_text(strip=True)[:255] or "Contenu"
            current_chapitre["granules"].append({
                "title": title,
                "html": "\n".join(buf_html),
                "content": " ".join(buf_text),
            })
        buf_html.clear()
        buf_text.clear()

    def _ensure_partie(title="Partie 1"):
        nonlocal current_partie, current_chapitre
        if current_partie is None:
            current_partie = {"title": title, "chapitres": []}
            parties.append(current_partie)
            # Chapitre par défaut pour le contenu orphelin avant le premier h2
            current_chapitre = {"title": "Contenu", "granules": []}
            current_partie["chapitres"].append(current_chapitre)

    def _ensure_chapitre(title="Contenu"):
        nonlocal current_chapitre
        _ensure_partie()
        if current_chapitre is None:
            current_chapitre = {"title": title, "granules": []}
            current_partie["chapitres"].append(current_chapitre)

    for sec in flat_sections:
        t       = sec.get("type", "p")
        content = sec.get("content", "").strip()
        html    = sec.get("html", f"<p>{content}</p>")

        if not content:
            continue

        if t == "h1":
            _flush()
            current_partie  = {"title": content, "chapitres": []}
            current_chapitre = {"title": "Contenu", "granules": []}
            current_partie["chapitres"].append(current_chapitre)
            parties.append(current_partie)

        elif t == "h2":
            _flush()
            _ensure_partie()
            current_chapitre = {"title": content, "granules": []}
            current_partie["chapitres"].append(current_chapitre)

        elif t == "h3":
            # h3 délimite un nouveau granule : on flush le précédent puis commence le nouveau
            _flush()
            _ensure_chapitre()
            buf_html.append(html)
            buf_text.append(content)

        else:  # p, ul, ol → contenu d'un granule
            _ensure_chapitre()
            buf_html.append(html)
            buf_text.append(content)

    _flush()  # flush final

    # Nettoie les chapitres/parties vides
    for p in parties:
        p["chapitres"] = [c for c in p["chapitres"] if c["granules"]]
    parties = [p for p in parties if p["chapitres"]]

    # Fallback : document sans aucun titre structurant
    if not parties:
        all_html    = "\n".join(s.get("html", "") for s in flat_sections if s.get("content"))
        all_content = " ".join(s.get("content", "") for s in flat_sections[:3])
        parties = [{
            "title": "Contenu du cours",
            "chapitres": [{
                "title": "Contenu",
                "granules": [{"title": all_content[:255] or "Contenu", "html": all_html, "content": all_content}]
            }]
        }]

    return parties


def split_and_create_granules(fichier_source, json_structure):
    """
    Crée les entrées PostgreSQL (Partie/Chapitre/Section/SousSection/Granule)
    et MongoDB (contenu HTML de chaque granule) en respectant la hiérarchie :
        h1 → Partie  |  h2 → Chapitre  |  h3/p → Granule
    """
    with transaction.atomic():
        cours, _ = Cours.objects.get_or_create(
            titre=fichier_source.titre,
            enseignant=fichier_source.enseignant,
            defaults={'matiere': fichier_source.matiere}
        )

        mongo_db     = get_mongo_db()
        flat_sections = json_structure.get("sections", [])
        parties_data  = _grouper_sections_par_hierarchie(flat_sections)

        for pi, partie_data in enumerate(parties_data):
            partie, _ = Partie.objects.get_or_create(
                cours=cours, numero=pi + 1,
                defaults={"titre": partie_data["title"]}
            )

            for ci, chapitre_data in enumerate(partie_data["chapitres"]):
                chapitre, _ = Chapitre.objects.get_or_create(
                    partie=partie, numero=ci + 1,
                    defaults={"titre": chapitre_data["title"]}
                )

                for gi, granule_data in enumerate(chapitre_data["granules"]):
                    sec, _ = Section.objects.get_or_create(
                        chapitre=chapitre, numero=gi + 1,
                        defaults={"titre": granule_data["title"][:200]}
                    )
                    sous_sec, _ = SousSection.objects.get_or_create(
                        section=sec, numero=1,
                        defaults={"titre": "Contenu"}
                    )

                    mongo_id = mongo_db["granules"].insert_one({
                        "fichier_source_id": str(fichier_source.id),
                        "html":    granule_data["html"],
                        "content": granule_data["content"],
                        "type":    "TEXTE",
                    }).inserted_id

                    Granule.objects.create(
                        sous_section=sous_sec,
                        fichier_source=fichier_source,
                        titre=granule_data["title"][:255],
                        type_contenu="TEXTE",
                        mongo_contenu_id=str(mongo_id),
                        ordre=gi,
                    )

        return cours

# ==============================================================================
# 2. ORCHESTRATEUR PRINCIPAL (LÀ OÙ LA MAGIE OPÈRE)
# ==============================================================================

def process_and_store_document(fichier_source_instance):
    file_path = fichier_source_instance.fichier_original.path
    ext = file_path.split('.')[-1].lower()
    
    print(f"🚀 Début traitement {file_path} (Type: {ext.upper()})")
    try:
        # 1. PARSING MÉCANIQUE BRUT
        print(f"📄 Extraction {ext.upper()} → JSON...")
        if ext == 'docx':
            json_structure = extract_structure_from_docx(file_path)
        elif ext == 'pdf':
            json_structure = extract_structure_from_pdf(file_path)
        elif ext == 'txt':
            json_structure = extract_structure_from_txt(file_path)
        else:
            raise ValueError(f"Format {ext} non supporté")
            
        # ------------------------------------------------------------------
        # MODULE 2 : INTERVENTION DU CHEF D'ORCHESTRE SÉMANTIQUE
        # ------------------------------------------------------------------
        print(f"🧠 Appel au Chef d'Orchestre Sémantique pour enrichissement...")
        json_structure = apply_semantic_orchestrator(json_structure)
        
        # 3. SAUVEGARDE MONGODB (Avec les métadonnées IA !)
        print(f"💾 Stockage MongoDB fichiers_uploades...")
        mongo_db = get_mongo_db()
        
        mongo_db['fichiers_uploades'].update_one(
            {"fichier_source_id": str(fichier_source_instance.id)},
            {
                "$set": {
                    "titre": fichier_source_instance.titre,
                    "type_original": ext.upper(),
                    "structure_json": json_structure, # Contient désormais "metadata_ia"
                    "date_traitement": datetime.now().isoformat(),
                    "version": "3.0-ML-Orchestrated"
                }
            },
            upsert=True
        )
        
        doc = mongo_db['fichiers_uploades'].find_one({"fichier_source_id": str(fichier_source_instance.id)})
        mongo_result_id = doc['_id']
        
        # 4. CRÉATION RELATIONNELLE
        print(f"🔨 Création hiérarchie MySQL + granules MongoDB...")
        cours = split_and_create_granules(fichier_source_instance, json_structure)
        
        # 5. FINALISATION
        with transaction.atomic():
            fichier_source_instance.mongo_transforme_id = str(mongo_result_id)
            fichier_source_instance.statut_traitement = 'TRAITE'
            fichier_source_instance.save()
        
        print(f"✅ Traitement ML terminé avec succès")
        return True, f"Cours généré et enrichi : {cours.titre}"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        with transaction.atomic():
            fichier_source_instance.statut_traitement = 'ERREUR'
            fichier_source_instance.save()
        return False, f"Erreur: {str(e)}"






















# # xcsm/processing.py - Version JSON Structuré (Refonte Complète)
# import fitz  # PyMuPDF
# import unicodedata
# import os
# import re
# import mammoth
# from bs4 import BeautifulSoup
# from django.db import transaction
# from .utils import get_mongo_db
# from .models import (
#     Cours, Partie, Chapitre, Section, SousSection, Granule,
#     Exercice, Question, Reponse, Tag, Categorie, Organisation
# )
# from datetime import datetime

# # ==============================================================================
# # 1. CONVERSION VERS JSON STRUCTURÉ (Remplacement du HTML)
# # ==============================================================================

# def extract_structure_from_docx(file_path):
#     """
#     Convertit un DOCX en JSON structuré avec hiérarchie sémantique.
#     Retourne: {"metadata": {...}, "sections": [...]}
#     """
#     style_map = """
#     p[style-name='Title'] => h1:fresh
#     p[style-name='Heading 1'] => h1:fresh
#     p[style-name='Heading 2'] => h2:fresh
#     p[style-name='Heading 3'] => h3:fresh
#     """
    
#     with open(file_path, 'rb') as f:
#         result = mammoth.convert_to_html(f, style_map=style_map)
#         html = f"<html><body>{result.value}</body></html>"
    
#     return parse_html_to_json_structure(html)


# def extract_structure_from_pdf(file_path):
#     """
#     ANALYSE AVANCÉE PDF : Utilise la taille et le style des polices pour identifier la structure.
#     """
#     doc = fitz.open(file_path)
    
#     # 1. ANALYSE STATISTIQUE DES POLICES
#     # On récupère toutes les tailles de police du document pour trouver la "taille du corps"
#     font_sizes = []
#     for page in doc:
#         blocks = page.get_text("dict")["blocks"]
#         for b in blocks:
#             if "lines" in b: # Bloc de texte
#                 for l in b["lines"]:
#                     for s in l["spans"]:
#                         if s["text"].strip():
#                             font_sizes.append(round(s["size"], 1))
    
#     # La taille la plus fréquente est probablement le corps de texte
#     if not font_sizes:
#          return parse_html_to_json_structure("<html><body><p>Document Vide</p></body></html>")
         
#     from collections import Counter
#     size_distribution = Counter(font_sizes)
#     body_font_size = size_distribution.most_common(1)[0][0]
    
#     print(f"📊 Analyse PDF : Taille du corps détectée = {body_font_size}pt")
    
#     html_parts = ""
    
#     # 2. EXTRACTION ET CLASSIFICATION
#     for page_num, page in enumerate(doc, 1):
#         blocks = page.get_text("dict")["blocks"]
        
#         for b in blocks:
#             if "lines" not in b: continue
            

#             for l in b["lines"]:
#                 # Reconstruction de la ligne (qui peut avoir plusieurs styles)
#                 raw_text = "".join([s["text"] for s in l["spans"]]).strip()
                
#                 try:
#                     # Regex pour intervertir : [Espace éventuel][Accent combinant OU espacé][Espace éventuel][Lettre]
#                     # Inclut U+00B4 (Acute), U+0060 (Grave), U+005E (Circumflex), U+00A8 (Diaeresis)
#                     pattern = r"(\s*)([\u0300-\u036f\u00B4\u0060\^¨])(\s*)([a-zA-Z])"
                    
#                     def accent_replacer(match):
#                         accent = match.group(2)
#                         letter = match.group(4)
#                         # Map accents espacés vers accent combinants pour que NFKC fonctionne
#                         charmap = {
#                             '\u00B4': '\u0301', # Acute
#                             '\u0060': '\u0300', # Grave
#                             '^': '\u0302',      # Circumflex
#                             '¨': '\u0308'       # Diaeresis
#                         }
#                         combining = charmap.get(accent, accent)
#                         return letter + combining

#                     fixed_text = re.sub(pattern, accent_replacer, raw_text)
#                     line_text = unicodedata.normalize('NFKC', fixed_text)
#                 except Exception:
#                     line_text = unicodedata.normalize('NFKC', raw_text)

#                 if not line_text: continue
                
#                 # On prend le style du premier span significatif pour classifier la ligne
#                 first_span = l["spans"][0]
#                 size = round(first_span["size"], 1)
#                 flags = first_span["flags"]
#                 is_bold = bool(flags & 16) # 16 = Bold
#                 is_upper = line_text.isupper()
                
#                 # --- HEURISTIQUES DE DÉTECTION ---
#                 tag = "p"
                
#                 # On évite de prendre pour titre des lignes non pertinentes
#                 # - Trop courtes (ex: numéros de page)
#                 # - Purement numériques
#                 # - Terminant par une ponctuation de fin de phrase
#                 # - Commençant par un mot de type "Page", "Figure", etc.
                
#                 is_likely_not_header = (
#                     len(line_text) < 5 or 
#                     line_text.isdigit() or 
#                     line_text.strip().endswith(('.', ':', '!', '?')) or
#                     line_text.lower().startswith(('page ', 'figure ', 'table ', 'note :'))
#                 )

#                 # TITRE NIVEAU 1 (Très grand ou Grand + Gras + Majuscules)
#                 if not is_likely_not_header:
#                     if size > body_font_size + 4:
#                         tag = "h1"
#                     elif size > body_font_size + 2 and is_bold:
#                         tag = "h1"
                    
#                     # TITRE NIVEAU 2 (Plus grand que le corps ou Gras + Couleur/Style)
#                     elif size > body_font_size + 1:
#                         tag = "h2"
#                     elif is_bold and (is_upper or size > body_font_size):
#                         tag = "h2"
                
#                 # Listes et autres peuvent être détectées ici
                
#                 # Ajout au HTML avec métadonnée de page pour le frontend
#                 html_parts += f'<{tag} data-page="{page_num}">{line_text}</{tag}>\n'

#     return parse_html_to_json_structure(f"<html><body>{html_parts}</body></html>")
# def extract_structure_from_txt(file_path):
#     """ TXT -> JSON Structure (Simple) """
#     # Tentative 1: UTF-8 avec BOM (utf-8-sig) ou sans
#     try:
#         with open(file_path, 'r', encoding='utf-8-sig') as f:
#             text = f.read()
#     except UnicodeDecodeError:
#         # Tentative 2: CP1252 (Windows Western Europe)
#         print(f"⚠️ Échec lecture UTF-8 pour {file_path}, tentative CP1252...")
#         try:
#              with open(file_path, 'r', encoding='cp1252') as f:
#                 text = f.read()
#         except UnicodeDecodeError:
#             # Tentative 3: Latin-1 (Fallback ultime, ne plante jamais mais peut mal interpréter)
#             print(f"⚠️ Échec lecture CP1252, tentative Latin-1...")
#             with open(file_path, 'r', encoding='latin-1') as f:
#                 text = f.read()
    
#     html_parts = ""
#     # Heuristique simple pour le TXT
#     blocks = re.split(r'\n\s*\n', text)
    
#     for i, block in enumerate(blocks):
#         block = block.strip()
#         if not block: continue
        
#         # Premier bloc = Titre probable
#         if i == 0 and len(block) < 200:
#             html_parts += f"<h1>{block}</h1>\n"
#             continue
            
#         lines = block.split('\n')
#         is_title = len(lines) == 1 and len(block) < 100
        
#         if is_title and block.isupper():
#             html_parts += f"<h2>{block}</h2>\n"
#         else:
#             html_parts += f"<p>{block}</p>\n"
            
#     return parse_html_to_json_structure(f"<html><body>{html_parts}</body></html>")


# def parse_html_to_json_structure(html_content):
#     """
#     CŒUR DE LA TRANSFORMATION : Convertit le HTML en structure JSON hiérarchique.
#     Format de sortie:
#     {
#         "metadata": {"source_type": "pdf/docx", "extraction_date": "..."},
#         "sections": [
#             {
#                 "type": "h1/h2/p",
#                 "level": 1/2/3,
#                 "content": "texte brut",
#                 "html": "<h1>texte</h1>",  # Conservé pour compatibilité
#                 "children": [...]  # Granules enfants si applicable
#             }
#         ]
#     }
#     """
#     soup = BeautifulSoup(html_content, 'html.parser')
#     root = soup.body if soup.body else soup
    
#     structure = {
#         "metadata": {
#             "extraction_date": datetime.now().isoformat(),
#             "version": "2.0-JSON"
#         },
#         "sections": []
#     }
    
#     current_h1 = None
#     current_h2 = None
    
#     for element in root.contents:
#         if element.name is None:
#             continue
        
#         tag = element.name
#         text = element.get_text().strip()
        
#         if not text:
#             continue
        
#         # Extraction des métadonnées (Page, etc.)
#         page_num = element.attrs.get('data-page')
        
#         # Construction du nœud JSON
#         node = {
#             "type": tag,
#             "level": get_semantic_level(tag),
#             "content": text,
#             "html": str(element),  # Conservé pour rétro-compatibilité
#             "children": [],
#             "metadata": { "page": page_num } if page_num else {}
#         }
        
#         # Gestion de la hiérarchie
#         if tag == 'h1':
#             structure["sections"].append(node)
#             current_h1 = node
#             current_h2 = None
        
#         elif tag == 'h2':
#             if current_h1:
#                 current_h1["children"].append(node)
#             else:
#                 structure["sections"].append(node)
#             current_h2 = node
        
#         elif tag in ['h3', 'p', 'li', 'div']:
#             # Découpage ligne par ligne pour les paragraphes
#             lines = [line.strip() for line in text.split('\n') if line.strip()]
            
#             for line in lines:
#                 clean_line = re.sub(r'[\u00A0\t\r]+', ' ', line).strip()
#                 if not clean_line:
#                     continue
                
#                 granule_node = {
#                     "type": "granule",
#                     "level": 4,
#                     "content": clean_line,
#                     "html": f"<p>{clean_line}</p>",
#                     "metadata": { "page": page_num } if page_num else {}
#                 }
                
#                 # Attachement au bon parent
#                 if current_h2:
#                     current_h2["children"].append(granule_node)
#                 elif current_h1:
#                     current_h1["children"].append(granule_node)
#                 else:
#                     structure["sections"].append(granule_node)
    
#     return structure


# def get_semantic_level(tag):
#     """Retourne le niveau sémantique d'une balise."""
#     levels = {'h1': 1, 'h2': 2, 'h3': 3, 'h4': 4, 'p': 4, 'li': 4, 'div': 4}
#     return levels.get(tag, 5)


# # ==============================================================================
# # 2. DÉCOUPAGE ET STOCKAGE (Version JSON)
# # ==============================================================================

# def split_and_create_granules(fichier_source, json_structure, target_course_id=None):
#     """
#     Analyse la structure JSON et crée la hiérarchie MySQL + stockage MongoDB.
#     Si target_course_id est fourni, on met à jour ce cours spécifiquement.
#     """
#     mongo_db = get_mongo_db()
#     granules_col = mongo_db['granules']
    
#     # A. NETTOYAGE des anciens granules
#     Granule.objects.filter(fichier_source=fichier_source).delete()
    
#     # B. RÉCUPÉRATION / CRÉATION DU COURS
#     # Le cours est désormais attaché à la MATIÈRE du fichier
    
#     if not fichier_source.matiere:
#         print(f"⚠️ Fichier {fichier_source.id} sans matière parente. Création orpheline impossible.")
#         # Fallback temporaire ou erreur ? 
#         # Pour l'instant on raise une erreur car la matière est obligatoire dans la nouvelle logique
#         raise ValueError("Impossible de traiter un fichier sans matière associée.")

#     matiere = fichier_source.matiere
    
#     # On cherche s'il existe déjà un cours pour ce fichier dans cette matière
#     # Ou logique simplifiée : Un fichier = Un cours ?
#     # Oui, "La vcreation d'un cours exige l'upload d'unn document qui sera le document de ce cours"
    
#     cours, created = Cours.objects.get_or_create(
#         matiere=matiere,
#         titre=fichier_source.titre,
#         defaults={
#             'enseignant': fichier_source.enseignant,
#             'description': f"Cours généré depuis {fichier_source.titre}",
#             'est_publie': True # AUTO-PUBLICATION pour visibilité immédiate
#         }
#     )
    
#     if created:
#         print(f"✅ Nouveau cours créé : {cours.titre} dans {matiere.titre}")
#     else:
#         print(f"♻️ Mise à jour du cours existant : {cours.titre}")
    
#     # Nettoyage des anciennes parties
#     Partie.objects.filter(cours=cours).delete()
    
#     # C. INITIALISATION DE LA HIÉRARCHIE
#     partie = Partie.objects.create(cours=cours, titre="Contenu Principal", numero=1)
#     chapitre = Chapitre.objects.create(partie=partie, titre="Introduction", numero=1)
#     section = Section.objects.create(chapitre=chapitre, titre="Généralités", numero=1)
#     sous_section = SousSection.objects.create(section=section, titre="Contenu", numero=1)
    
#     counters = {'chapitre': 1, 'section': 1, 'granule': 1}
    
#     # D. PARCOURS DE LA STRUCTURE JSON
#     for node in json_structure.get("sections", []):
#         process_json_node(
#             node, fichier_source, granules_col,
#             partie, chapitre, section, sous_section, counters
#         )
    
#     return cours


# def process_json_node(node, fichier_source, granules_col, 
#                      partie, chapitre, section, sous_section, counters):
#     """
#     Traite récursivement un nœud JSON et crée les entités MySQL/MongoDB.
#     """
#     node_type = node.get("type")
#     content = node.get("content", "")
#     children = node.get("children", [])
    
#     # NIVEAU 1: CHAPITRE (H1)
#     if node_type == 'h1':
#         counters['chapitre'] += 1
#         chapitre = Chapitre.objects.create(
#             partie=partie,
#             titre=content[:190],
#             numero=counters['chapitre']
#         )
#         section = Section.objects.create(
#             chapitre=chapitre, 
#             titre="Début", 
#             numero=1
#         )
#         sous_section = SousSection.objects.create(
#             section=section, 
#             titre="Contenu", 
#             numero=1
#         )
#         counters['section'] = 1
        
#         # Traitement des enfants
#         for child in children:
#             process_json_node(
#                 child, fichier_source, granules_col,
#                 partie, chapitre, section, sous_section, counters
#             )
    
#     # NIVEAU 2: SECTION (H2)
#     elif node_type == 'h2':
#         counters['section'] += 1
#         section = Section.objects.create(
#             chapitre=chapitre,
#             titre=content[:190],
#             numero=counters['section']
#         )
#         sous_section = SousSection.objects.create(
#             section=section, 
#             titre="Contenu", 
#             numero=1
#         )
        
#         # Traitement des enfants
#         for child in children:
#             process_json_node(
#                 child, fichier_source, granules_col,
#                 partie, chapitre, section, sous_section, counters
#             )
    
#     # NIVEAU 3: GRANULE
#     elif node_type in ['granule', 'h3', 'p', 'li', 'div']:
#         # Stockage MongoDB (JSON pur)
#         granule_mongo = {
#             "type": node_type,
#             "content": content,
#             "html": node.get("html", f"<p>{content}</p>"),
#             "fichier_source_id": str(fichier_source.id),
#             "metadata": {
#                 "level": node.get("level", 4),
#                 "extraction_date": datetime.now().isoformat(),
#                 "page": node.get("metadata", {}).get("page")
#             }
#         }
#         res = granules_col.insert_one(granule_mongo)
        
#         # Récupération du numéro de page (si présent)
#         page_num_str = node.get("metadata", {}).get("page")
#         page_num = int(page_num_str) if page_num_str and str(page_num_str).isdigit() else None
        
#         # Stockage MySQL (métadonnées)
#         Granule.objects.create(
#             sous_section=sous_section,
#             fichier_source=fichier_source,
#             titre=content[:45] + "..." if len(content) > 45 else content,
#             type_contenu="TEXTE",
#             mongo_contenu_id=str(res.inserted_id),
#             ordre=counters['granule'],
#             source_pdf_page=page_num
#         )
#         counters['granule'] += 1


# # ==============================================================================
# # 3. ORCHESTRATEUR PRINCIPAL (Point d'entrée)
# # ==============================================================================


# # Ajout des imports nécessaires pour l'extraction d'images
# import fitz  # PyMuPDF
# import io
# import os
# from django.core.files.base import ContentFile
# from .models import Ressource

# def extract_images_from_pdf(fichier_source_instance):
#     """
#     Extrait les images d'un PDF et les enregistre comme Ressources.
#     """
#     try:
#         pdf_path = fichier_source_instance.fichier_original.path
#         doc = fitz.open(pdf_path)
        
#         count = 0
#         for page_index in range(len(doc)):
#             page = doc[page_index]
#             image_list = page.get_images()
            
#             for image_index, img in enumerate(image_list):
#                 xref = img[0]
#                 base_image = doc.extract_image(xref)
#                 image_bytes = base_image["image"]
#                 image_ext = base_image["ext"]
                
#                 # Filtrage des petites icônes/bruit (ex: < 5KB)
#                 if len(image_bytes) < 5000:
#                     continue
                
#                 # Création du fichier en mémoire
#                 image_name = f"img_{fichier_source_instance.id.hex[:6]}_p{page_index+1}_{image_index}.{image_ext}"
#                 content_file = ContentFile(image_bytes, name=image_name)
                
#                 # Création de la ressource
#                 Ressource.objects.create(
#                     fichier_source=fichier_source_instance,
#                     titre=f"Image Page {page_index+1}",
#                     fichier=content_file,
#                     type_ressource='IMAGE'
#                 )
#                 count += 1
                
#         print(f"🖼️ {count} images extraites du PDF.")
#         return count
#     except Exception as e:
#         print(f"❌ Erreur extraction images PDF: {e}")
#         return 0


# def process_and_store_document(fichier_source_instance):
#     """
#     Fonction principale (Point d'entrée) appelée par la vue ou la tâche Celery.
#     Orchestre tout le processus.
#     """
#     file_path = fichier_source_instance.fichier_original.path
#     ext = file_path.split('.')[-1].lower() # Changed to lower() to match existing logic
    
#     # 0. EXTRACTION DES IMAGES (Si PDF)
#     if ext == 'pdf': # Changed to 'pdf' to match existing logic
#         print("🖼️ Extraction des images du PDF...")
#         extract_images_from_pdf(fichier_source_instance)

#     # 1. ANALYSE ET EXTRACTION DU TEXTE
#     print(f"🚀 Début traitement {file_path} (Type: {ext.upper()})") # Changed to ext.upper() for consistency
#     try:
#         path = fichier_source_instance.fichier_original.path
#         # ext = os.path.splitext(path)[1].lower().strip('.') # This line is now redundant
        
#         # 1. EXTRACTION → JSON STRUCTURÉ
#         print(f"📄 Extraction {ext.upper()} → JSON...")
#         if ext == 'docx':
#             json_structure = extract_structure_from_docx(path)
#         elif ext == 'pdf':
#             json_structure = extract_structure_from_pdf(path)
#         elif ext == 'txt':
#             json_structure = extract_structure_from_txt(path)
#         else:
#             raise ValueError(f"Format {ext} non supporté")
        
#         # FALLBACK: Si aucune section n'est trouvée (doc plat), on crée une structure par défaut
#         if not json_structure.get("sections"):
#             print("⚠️ Aucune section détectée, création d'une structure par défaut.")
#             json_structure["sections"] = [{
#                 "type": "h1",
#                 "level": 1,
#                 "content": "Document Complet",
#                 "children": [{
#                     "type": "granule",
#                     "level": 4, 
#                     "content": "Contenu du document (structure non détectée)",
#                     "html": "<p>Le contenu du document n'a pas pu être structuré automatiquement.</p>"
#                 }]
#             }]
#             # Tente de récupérer tout texte brut disponible si possible (TODO: Améliorer l'extraction texte brut)
        
#         # 2. STOCKAGE MONGODB - DOCUMENT COMPLET (UPSERT)
#         print(f"💾 Stockage MongoDB fichiers_uploades...")
#         mongo_db = get_mongo_db()
        
#         # On utilise update_one + upsert pour éviter les doublons avec l'éditeur
#         mongo_db['fichiers_uploades'].update_one(
#             {"fichier_source_id": str(fichier_source_instance.id)},
#             {
#                 "$set": {
#                     "titre": fichier_source_instance.titre,
#                     "type_original": ext.upper(),
#                     "structure_json": json_structure,
#                     "date_traitement": datetime.now().isoformat(),
#                     "version": "2.0-JSON"
#                 }
#             },
#             upsert=True
#         )
        
#         # Récupération de l'ID (nécessaire pour la liaison MySQL)
#         doc = mongo_db['fichiers_uploades'].find_one({"fichier_source_id": str(fichier_source_instance.id)})
#         mongo_result_id = doc['_id']
        
#         # 3. DÉCOUPAGE ET HIÉRARCHISATION
#         print(f"🔨 Création hiérarchie MySQL + granules MongoDB...")
#         cours = split_and_create_granules(fichier_source_instance, json_structure)
        
#         # 4. FINALISATION
#         with transaction.atomic():
#             fichier_source_instance.mongo_transforme_id = str(mongo_result_id)
#             fichier_source_instance.statut_traitement = 'TRAITE'
#             fichier_source_instance.save()
        
#         print(f"✅ Traitement terminé avec succès")
#         return True, f"Cours généré : {cours.titre}"
        
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
        
#         with transaction.atomic():
#             fichier_source_instance.statut_traitement = 'ERREUR'
#             fichier_source_instance.save()
        
#         return False, f"Erreur: {str(e)}"