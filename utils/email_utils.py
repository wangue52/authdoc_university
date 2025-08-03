# utils/email_utils.py
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formatdate
from datetime import datetime
from models import DemandeClient, ReponseDemande
import os

# Configuration email (e remplacer par vos propres param�tres)
EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "votre_email@gmail.com",
    "password": "votre_mot_de_passe",
    "sender": "Service Authentification <authentification@institut.edu>"
}

def envoyer_notification_reponse(demande: DemandeClient, reponse: ReponseDemande):
    """Envoie une notification par email e l'utilisateur concernant la r�ponse e sa demande."""
    try:
        # D�terminer l'email du destinataire
        destinataire = demande.client.email
        if demande.pour_tiers and demande.tiers_email:
            destinataire = demande.tiers_email
            
        # Cr�er le message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG["sender"]
        msg['To'] = destinataire
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = f"R�ponse e votre demande {demande.reference}"
        
        # Corps du message
        corps_message = f"""
        <html>
            <body>
                <p>Bonjour,</p>
                <p>Votre demande <strong>{demande.reference}</strong> a �te trait�e avec succ�s.</p>
                <div style="background-color: #f8f9fa; border-left: 4px solid #0d6efd; padding: 15px; margin: 15px 0;">
                    <h5 style="color: #0d6efd;">D�tails de la demande :</h5>
                    <ul>
                        <li><strong>Type de service :</strong> {demande.type_service.value}</li>
                        <li><strong>Date de traitement :</strong> {datetime.now().strftime('%d/%m/%Y e %H:%M')}</li>
                        <li><strong>R�f�rence du document :</strong> {reponse.contenu}</li>
                    </ul>
                </div>
                <p>Vous pouvez t�l�charger votre document s�curise en pi�ce jointe.</p>
                <p style="margin-top: 20px;">
                    <a href="https://votre-domaine.com/verification/{demande.code_verification}" 
                       style="display: inline-block; background-color: #0d6efd; color: white; 
                              padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                        V�rifier l'authenticite du document
                    </a>
                </p>
                <p>Cordialement,<br>Le Service d'Authentification</p>
            </body>
        </html>
        """
        msg.attach(MIMEText(corps_message, "html"))
        
        # Ajouter le document en pi�ce jointe si disponible
        if reponse.chemin_fichier_securise and os.path.exists(reponse.chemin_fichier_securise):
            with open(reponse.chemin_fichier_securise, "rb") as attachment:
                part = MIMEApplication(attachment.read(), Name=os.path.basename(reponse.chemin_fichier_securise))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(reponse.chemin_fichier_securise)}"'
                msg.attach(part)
        
        # Connexion au serveur SMTP et envoi
        with smtplib.SMTP(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"]) as server:
            server.starttls()
            server.login(EMAIL_CONFIG["username"], EMAIL_CONFIG["password"])
            server.send_message(msg)
            
        # Marquer la notification comme envoy�e
        reponse.notification_envoyee = True
        reponse.date_envoi = datetime.now()
        reponse.email_envoi = destinataire
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email: {str(e)}")
        return False
 
