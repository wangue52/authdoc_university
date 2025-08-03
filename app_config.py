# app_config.py
"""Module central pour les dépendances partagées de l'application."""
from fastapi.templating import Jinja2Templates

# Création de l'objet templates centralisé.
# Ce fichier NE DOIT PAS importer d'autres modules de votre application.
templates = Jinja2Templates(directory="templates")

# Vous pouvez ajouter d'autres dépendances globales ici si nécessaire.