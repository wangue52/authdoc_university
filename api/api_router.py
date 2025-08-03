# api/api_router.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Importation de la configuration centralisée
from app_config import templates

# Importation des routeurs spécifiques
from api.routes import (
    auth_routes,
    user_routes,
    demande_routes,
    role_routes,
    permission_routes,
    taux_change_routes,
    partenaire_routes,
    paiement_routes,
    couriel_routes,
)

# Création du routeur principal
api_router = APIRouter()

# Inclusion des routeurs spécifiques
api_router.include_router(auth_routes.router)
api_router.include_router(user_routes.router)
api_router.include_router(demande_routes.router)
api_router.include_router(role_routes.router)
api_router.include_router(permission_routes.router)
api_router.include_router(taux_change_routes.router)
api_router.include_router(partenaire_routes.router)
api_router.include_router(paiement_routes.router)
api_router.include_router(couriel_routes.router)

# Routes publiques
@api_router.get("/a-propos", response_class=HTMLResponse, include_in_schema=False, name="a_propos")
async def a_propos(request: Request):
    """Page À Propos"""
    return templates.TemplateResponse("pages/a_propos.html", {"request": request})

@api_router.get("/contact", response_class=HTMLResponse, include_in_schema=False, name="contact_page")
async def contact(request: Request):
    """Page Contact"""
    return templates.TemplateResponse("pages/contact.html", {"request": request})

@api_router.post("/contact", response_class=HTMLResponse, include_in_schema=False, name="envoyer_contact")
async def envoyer_message_contact(
    request: Request,
    nom: str = Form(...),
    email: str = Form(...),
    sujet: str = Form(...),
    message: str = Form(...)
):
    """Traite le formulaire de contact"""
    try:
        # Configuration de l'email
        EMAIL_CONFIG = {
            "smtp_server": os.getenv("SMTP_SERVER", "localhost"),
            "smtp_port": int(os.getenv("SMTP_PORT", 1025)),
            "username": os.getenv("SMTP_USERNAME", "votre_email@exemple.com"),
            "password": os.getenv("SMTP_PASSWORD", "votre_mot_de_passe"),
            "sender": os.getenv("SMTP_SENDER", "Site Web <contact@votre-domaine.com>"),
            "recipient": os.getenv("CONTACT_RECIPIENT", "admin@votre-domaine.com")
        }
        
        # Créer le message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG["sender"]
        msg['To'] = EMAIL_CONFIG["recipient"]
        msg['Subject'] = f"[Contact Site] {sujet}"
        
        body = f"""
        Nouveau message via le formulaire de contact :
        
        Nom : {nom}
        Email : {email}
        Sujet : {sujet}
        
        Message :
        {message}
        """
        msg.attach(MIMEText(body, 'plain'))
        
        # Envoyer l'email
        server = smtplib.SMTP(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"])
        text = msg.as_string()
        server.sendmail(EMAIL_CONFIG["sender"], EMAIL_CONFIG["recipient"], text)
        server.quit()
        
        # Page de succès
        return templates.TemplateResponse(
            "pages/contact_succes.html", 
            {"request": request, "nom": nom}
        )
             
    except Exception as e:
        # En cas d'erreur, réafficher le formulaire avec un message d'erreur
        print(f"Erreur lors de l'envoi du message: {e}")
        return templates.TemplateResponse(
            "pages/contact.html", 
            {
                "request": request, 
                "error": "Une erreur est survenue lors de l'envoi du message. Veuillez réessayer.",
                "form_data": {"nom": nom, "email": email, "sujet": sujet, "message": message}
            }
        )
 
