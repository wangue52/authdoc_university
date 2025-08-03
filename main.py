# main.py
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from fastapi.responses import RedirectResponse

# Importation de la configuration centralisée
from app_config import templates
from database import init_db
from api.api_router import api_router
from auth import RedirectToHomeException 
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialisation de la base de données au démarrage
    print("Initialisation de la base de données...")
    try:
        init_db()
        print("Base de données initialisée avec succès")
    except Exception as e:
        print(f"Erreur lors de l'initialisation de la base de données: {e}")
        raise
    yield
    # Actions de nettoyage à l'arrêt (si nécessaire)
    print("L'application est arrêtée")

# Création de l'application FastAPI
app = FastAPI(lifespan=lifespan, title="API de Gestion de Demandes")

# Montage des fichiers statiques
app.mount("/static", StaticFiles(directory="static"), name="static")
@app.exception_handler(RedirectToHomeException)
async def redirect_to_home_exception_handler(request: Request, exc: RedirectToHomeException):
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
@app.get("/")
def home_redirect():
    return RedirectResponse(url="/auth/")

# Redirections pour les URLs courantes sans préfixe
@app.get("/login")
def login_redirect():
    return RedirectResponse(url="/auth/login")

@app.get("/register")
def register_redirect():
    return RedirectResponse(url="/auth/register")

@app.get("/logout")
def logout_redirect():
    return RedirectResponse(url="/auth/logout")
@app.get("/admin/dashboard")
def register_redirect():
    return RedirectResponse(url="/admin/users/admin/dashboard")
@app.get("/admin/users")
def register_redirect():
    return RedirectResponse(url="/admin/users/users")
# Inclusion du routeur principal
app.include_router(api_router)

# Point d'entrée pour Uvicorn
if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8002, 
        reload=True,  # Le reload fonctionne quand lancé via python main.py
        workers=1,
        log_level="info"
    )
