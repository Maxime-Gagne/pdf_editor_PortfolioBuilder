import os
import sys
import fitz  # PyMuPDF
import base64
import shutil
import webbrowser # Pour ouvrir le navigateur auto
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
# --- 1. FONCTION MAGIQUE POUR PYINSTALLER ---
# Elle permet de trouver le dossier 'static' même quand il est compacté dans le .exe
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller crée un dossier temporaire _MEIxxxxxx
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

app = FastAPI()

# Configuration des chemins
UPLOAD_DIR = "uploads"

# LOGIQUE INTELLIGENTE :
# 1. On regarde si l'utilisateur a un dossier 'static' à côté de l'exe (Personnalisation)
if os.path.exists("static"):
    STATIC_DIR = "static"
    print("Mode Personnalisé : Utilisation du dossier static local")
# 2. Sinon, on utilise le dossier 'static' enfermé dans l'exe (Défaut)
else:
    STATIC_DIR = resource_path("static")
    print("Mode Défaut : Utilisation des ressources internes")

os.makedirs(UPLOAD_DIR, exist_ok=True)
# Pas besoin de makedirs pour static, il est packagé

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# --- MAPPING FONTS ---
FONT_MAP = {
    "Arial": "helv", "Helvetica": "helv", "Verdana": "helv",
    "Times New Roman": "tiro", "Times": "tiro", "Georgia": "tiro",
    "Courier New": "cour", "Courier": "cour", "Consolas": "cour"
}

def hex_to_rgb(hex_color: str):
    if not hex_color: return (0, 0, 0)
    
    # Gestion des noms de couleurs courants (sécurité)
    if hex_color.lower() == "white": return (1, 1, 1) # Blanc pur
    if hex_color.lower() == "black": return (0, 0, 0)
    
    # Nettoyage
    hex_color = hex_color.lstrip('#')
    
    try:
        # Conversion Hex standard
        return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        print(f"⚠️ Couleur inconnue reçue : {hex_color}, on met du noir par défaut.")
        return (0, 0, 0) # Fallback noir pour éviter le crash
    
# --- NOUVEAU MODÈLE UNIFIÉ ---
class CanvasObject(BaseModel):
    type: str  # 'text', 'image', 'rect'
    left: float
    top: float
    width: float = 0
    height: float = 0
    
    # Propriétés Texte
    text: Optional[str] = None
    fontSize: Optional[float] = 0
    fontFamily: Optional[str] = "helv"
    color: Optional[str] = "#000000"
    
    # Propriétés Image
    data_url: Optional[str] = None
    
    # Propriétés Forme (Rect)
    fill: Optional[str] = "#ffffff"

class SaveRequest(BaseModel):
    filename: str
    page_num: int
    scale: float
    objects: List[CanvasObject] # Une seule liste pour respecter l'ordre des calques !
    page_order: List[int] = []

# --- ROUTES ---

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    # Nettoyage cache
    edited_filename = f"edited_{file.filename}"
    if os.path.exists(os.path.join(UPLOAD_DIR, edited_filename)):
        os.remove(os.path.join(UPLOAD_DIR, edited_filename))

    doc = fitz.open(file_path)
    info = {"filename": file.filename, "page_count": len(doc)}
    doc.close()
    return {"status": "success", "data": info}

@app.post("/api/append")
async def append_pdf(current_filename: str = Form(...), file: UploadFile = File(...)):
    try:
        current_path = os.path.join(UPLOAD_DIR, current_filename)
        new_file_path = os.path.join(UPLOAD_DIR, f"temp_{file.filename}")
        
        with open(new_file_path, "wb") as f:
            f.write(await file.read())
            
        if not os.path.exists(current_path):
             return {"status": "error", "message": "Session expirée."}
        
        doc_main = fitz.open(current_path)
        doc_new = fitz.open(new_file_path)
        doc_main.insert_pdf(doc_new)
        
        temp_output = os.path.join(UPLOAD_DIR, f"merged_{current_filename}")
        doc_main.save(temp_output)
        doc_main.close()
        doc_new.close()
        
        os.replace(temp_output, current_path)
        if os.path.exists(new_file_path): os.remove(new_file_path)

        return {"status": "success", "filename": current_filename}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/save")
async def save_pdf(request: SaveRequest):
    try:
        input_path = os.path.join(UPLOAD_DIR, request.filename)
        output_filename = f"edited_{request.filename}"
        output_path = os.path.join(UPLOAD_DIR, output_filename)
        target_path = output_path if os.path.exists(output_path) else input_path
        
        doc = fitz.open(target_path)
        
        # Gestion Page Virtuelle vs Réelle (Simplifiée pour l'exemple : on prend l'index brut)
        # Idéalement, le frontend envoie le bon numéro de page physique
        page_index = request.page_num - 1
        page = doc[page_index]

        # --- DESSIN DES OBJETS DANS L'ORDRE (LAYERS) ---
        for obj in request.objects:
            # Coordonnées réelles
            x = obj.left / request.scale
            y = obj.top / request.scale
            w = obj.width / request.scale
            h = obj.height / request.scale

            if obj.type == 'rect':
                # Dessin du rectangle (Correcteur)
                rect = fitz.Rect(x, y, x+w, y+h)
                # On dessine un shape rempli
                page.draw_rect(rect, color=hex_to_rgb(obj.fill), fill=hex_to_rgb(obj.fill))

            elif obj.type == 'i-text':
                real_size = obj.fontSize / request.scale
                # Baseline correction
                page.insert_text(
                    (x, y + (real_size * 0.8)), 
                    obj.text, 
                    fontsize=real_size, 
                    fontname=FONT_MAP.get(obj.fontFamily, "helv"),
                    color=hex_to_rgb(obj.color)
                )

            elif obj.type == 'image':
                rect = fitz.Rect(x, y, x+w, y+h)
                if obj.data_url and "," in obj.data_url:
                    header, encoded = obj.data_url.split(",", 1)
                    img_data = base64.b64decode(encoded)
                    page.insert_image(rect, stream=img_data)

        # Réorganisation
        if request.page_order:
            doc.select(request.page_order)
            doc.save(output_path) # Rewrite complet nécessaire
        else:
            if target_path == output_path:
                doc.save(output_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
            else:
                doc.save(output_path)
        
        doc.close()
        return {"status": "success", "new_filename": output_filename}

    except Exception as e:
        print(f"ERREUR: {e}")
        return {"status": "error", "message": str(e)}
    
if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    
    import uvicorn
    from threading import Timer
    
    # --- CORRECTION DU CRASH --noconsole ---
    # Si sys.stdout n'existe pas (mode fenêtre), on le redirige vers null
    # Cela empêche l'erreur 'NoneType object has no attribute isatty'
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    # ---------------------------------------

    def open_browser():
        webbrowser.open("http://127.0.0.1:8001/static/index.html")

    # On ne lance le navigateur que si on n'est pas en mode "rechargement" (protection multiprocessing)
    if not os.environ.get("UVICORN_RELOADER_RUN"):
        Timer(1.5, open_browser).start()
    
    # Lancement du serveur avec log_config=None pour désactiver le logging console qui plante
    uvicorn.run(app, host="127.0.0.1", port=8001, log_config=None)