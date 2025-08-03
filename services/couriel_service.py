# services/couriel_service.py
"""Service de gestion des operations du service COURIEL."""
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from models import (
    DemandeClient, TraitementDemande, ReponseDemande, HistoriqueDemande,
    StatutDemande, TypeReponse, NiveauSecurite
)
from utils.file_utils import creer_dossier_demande
from utils.email_utils import envoyer_notification_reponse
import uuid
import os
from datetime import datetime
from typing import List, Optional

def receptionner_demande(db: Session, demande_id: int, notes: str, user_id: int) -> DemandeClient:
    """
    Receptionne une demande par le service COURIEL.
    Cree le dossier physique et met e jour le statut.
    """
    # Verifier que la demande existe et est en statut SOUMISE
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.statut == StatutDemande.SOUMISE
    ).first()
    if not demande:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Demande non trouvee ou ne peut pas etre receptionnee"
        )
    
    # Creer le dossier physique pour la demande
    try:
        dossier_physique = creer_dossier_demande(demande_id)
        # Ici, vous pourriez copier les fichiers originaux dans ce dossier
        # pour preparer l'impression. Cela pourrait etre fait dans une teche asynchrone.
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la creation du dossier physique: {str(e)}"
        )
    
    # Mettre e jour le statut de la demande
    statut_precedent = demande.statut
    demande.statut = StatutDemande.RECU
    demande.date_reception = datetime.now()
    db.commit()
    
    # Ajouter un evenement dans l'historique
    historique = HistoriqueDemande(
        demande_id=demande.id,
        statut_precedent=statut_precedent.value,
        statut_nouveau=StatutDemande.RECU.value,
        commentaire=f"Demande receptionnee par le service COURIEL. Dossier cree. {notes}",
        utilisateur_id=user_id
    )
    db.add(historique)
    db.commit()
    db.refresh(demande)
    
    return demande

# Note : Le traitement manuel se fait hors du systeme.
# La prochaine etape est le scan et la securisation.

def preparer_reponse_document_scanne(
    db: Session,
    demande_id: int,
    user_id: int,
    fichier_scanne_path: str, # Chemin du fichier scanne sur le serveur
    type_reponse: TypeReponse,
    contenu: str, # Description ou reference du document
    niveau_securite: NiveauSecurite = NiveauSecurite.STANDARD,
    qr_code: bool = True,
    filigrane: bool = True,
    signature_numerique: bool = False, # Watermark anti-photocopie
    commentaire_public: str = "",
    commentaire_interne: str = "",
    
) -> ReponseDemande:
    """
    Prepare la reponse en securisant le document scanne.
    """
    # Verifier que la demande existe et est RECU
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.statut == StatutDemande.RECU # Ou EN_TRAITEMENT si vous ajoutez une etape
    ).first()
    if not demande:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Demande non trouvee ou pas prete pour la reponse"
        )

    # Creer un code de verification unique
    code_verification = f"VERIF-{uuid.uuid4().hex[:12].upper()}"
    demande.code_verification = code_verification
    
    # --- Logique de securisation du document ---
    # 1. Creer un dossier pour la reponse si necessaire
    dossier_demande = creer_dossier_demande(demande_id)
    
    # 2. Nom du fichier securise
    nom_fichier_securise = f"document_securise_{demande_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    chemin_fichier_securise = os.path.join(dossier_demande, nom_fichier_securise)
    
    # 3. Appliquer les transformations de securite
    try:
        # Cette fonction est definie dans utils/file_utils.py
        from utils.file_utils import securiser_document 
        securiser_document(
            fichier_scanne_path, 
            chemin_fichier_securise, 
            code_verification,
            qr_code=qr_code,
            filigrane=filigrane,
            signature_numerique=signature_numerique
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la securisation du document: {str(e)}"
        )
    # --- Fin de la securisation ---

    # Creer la reponse dans la base de donnees
    reponse = ReponseDemande(
        demande_id=demande_id,
        type_reponse=type_reponse,
        contenu=contenu,
        niveau_securite=niveau_securite,
        qr_code=qr_code,
        filigrane=filigrane,
        signature_numerique=signature_numerique,
        chemin_fichier_securise=chemin_fichier_securise,
        commentaire_public=commentaire_public,
        commentaire_interne=commentaire_interne
    )
    db.add(reponse)
    db.commit()
    db.refresh(reponse)
    
    # Mettre e jour le statut de la demande
    statut_precedent = demande.statut
    demande.statut = StatutDemande.COMPLETEE
    demande.date_reponse = datetime.now()
    db.commit()
    
    # Ajouter un evenement dans l'historique
    historique = HistoriqueDemande(
        demande_id=demande.id,
        statut_precedent=statut_precedent.value,
        statut_nouveau=StatutDemande.COMPLETEE.value,
        commentaire=f"Reponse preparee et document securise. Type: {type_reponse.value}.",
        utilisateur_id=user_id
    )
    db.add(historique)
    db.commit()
    
    # Notifier l'etudiant/partenaire par email
    try:
        envoyer_notification_reponse(demande, reponse)
    except Exception as e:
        # Log l'erreur mais ne bloque pas la reponse
        print(f"Erreur lors de l'envoi de la notification: {e}")
        # Vous pouvez aussi enregistrer cette erreur dans la base ou un log
    
    db.refresh(demande)
    return reponse

# Les autres fonctions du service (get_statistiques, etc.) restent les memes
# ou peuvent etre adaptees selon les besoins specifiques.

def get_statistiques(db: Session) -> dict:
    """Recupere les statistiques des demandes pour le dashboard COURIEL."""
    stats = {
        "total_demandes": db.query(DemandeClient).count(),
        "nouvelles": db.query(DemandeClient).filter(DemandeClient.statut == StatutDemande.SOUMISE).count(),
        "recues": db.query(DemandeClient).filter(DemandeClient.statut == StatutDemande.RECU).count(),
        "en_traitement": db.query(DemandeClient).filter(DemandeClient.statut == StatutDemande.EN_TRAITEMENT).count(),
        "traitees": db.query(DemandeClient).filter(DemandeClient.statut == StatutDemande.COMPLETEE).count(),
    }
    return stats
