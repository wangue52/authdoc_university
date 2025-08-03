# services/paiement_service.py
"""Service de gestion des paiements."""
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from models import DemandeClient, StatutPaiement, StatutDemande, MethodePaiement, Transaction
from services.paiement.passrelles import obtenir_passerelle, CONFIG_PASSERELLES
from services.paiement.base import PasserellePaiement
from typing import Dict, Any
import uuid
from datetime import datetime

def initier_paiement(db: Session, demande_id: int, url_base_retour: str) -> Dict[str, Any]:
    """
    Initie le processus de paiement pour une demande.
    Retourne les informations necessaires pour rediriger l'utilisateur.
    """
    demande = db.query(DemandeClient).filter(DemandeClient.id == demande_id).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvee")
        
    if demande.statut != StatutDemande.PAIEMENT_EN_ATTENTE:
        raise HTTPException(status_code=400, detail="La demande n'est pas en attente de paiement")

    # Creer une reference de transaction unique
    reference_transaction = f"TXN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    # Obtenir la passerelle appropriee
    try:
        passerelle = obtenir_passerelle(demande.methode_paiement, CONFIG_PASSERELLES)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # URLs de retour
    url_retour_succes = f"{url_base_retour}/paiement/succes?demande_id={demande_id}"
    url_retour_echec = f"{url_base_retour}/paiement/echec?demande_id={demande_id}"
    
    # Creer la transaction chez la passerelle
    try:
        details_transaction = passerelle.creer_transaction(demande, url_retour_succes, url_retour_echec)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la creation de la transaction: {str(e)}")

    # Enregistrer la transaction dans la base de donnees
    transaction_db = Transaction(
        demande_id=demande_id,
        reference=reference_transaction,
        methode_paiement=demande.methode_paiement,
        montant=demande.montant_total,
        statut="INITIE",
        donnees_passerelle=str(details_transaction), # Stocker les details en JSON
        url_retour_succes=url_retour_succes,
        url_retour_echec=url_retour_echec
    )
    db.add(transaction_db)
    db.commit()
    db.refresh(transaction_db)
    
    return {
        "url_redirection": details_transaction["url_redirection"],
        "transaction_id": details_transaction["transaction_id"],
        "reference": reference_transaction,
        "passerelle": passerelle.nom()
    }

def traiter_retour_paiement(db: Session, demande_id: int, statut_retour: str, donnees_retour: Dict[str, Any] = None) -> DemandeClient:
    """
    Traite le retour d'une passerelle de paiement (succes ou echec).
    Met e jour le statut de la demande et de la transaction.
    """
    demande = db.query(DemandeClient).filter(DemandeClient.id == demande_id).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvee")
    
    # Recuperer la derniere transaction pour cette demande
    transaction = db.query(Transaction).filter(
        Transaction.demande_id == demande_id
    ).order_by(Transaction.date_creation.desc()).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction non trouvee pour cette demande")
        
    # Mettre e jour le statut de la transaction
    if statut_retour.upper() == "SUCCES":
        transaction.statut = "SUCCES"
        # Mettre e jour le statut de paiement de la demande
        demande.statut_paiement = StatutPaiement.PAYE
        # Passer la demande au statut suivant (ex: SOUMISE)
        demande.statut = StatutDemande.SOUMISE
    else: # ECHEC ou autre
        transaction.statut = "ECHEC"
        demande.statut_paiement = StatutPaiement.ECHEC
        # La demande reste en PAIEMENT_EN_ATTENTE ou passe e un autre statut selon la logique
    
    # Mettre e jour les donnees de la transaction avec les details du retour
    if donnees_retour:
        transaction.donnees_passerelle = str(donnees_retour)
        
    transaction.date_mise_a_jour = datetime.utcnow()
    db.commit()
    db.refresh(demande)
    db.refresh(transaction)
    
    return demande

def traiter_webhook_paiement(db: Session, methode_paiement: MethodePaiement, donnees_webhook: Dict[str, Any]) -> Dict[str, Any]:
    """
    Traite une notification webhook d'une passerelle de paiement.
    Met e jour les statuts en arriere-plan.
    """
    try:
        # Obtenir la passerelle pour verifier les donnees
        passerelle = obtenir_passerelle(methode_paiement, CONFIG_PASSERELLES)
        
        # Verifier et obtenir le statut de la transaction
        resultat_verification = passerelle.verifier_transaction(donnees_webhook)
        
        # Trouver la transaction correspondante dans la base
        transaction_id_fourni = resultat_verification.get("transaction_id") or donnees_webhook.get("transaction_id")
        if not transaction_id_fourni:
            return {"status": "error", "message": "ID de transaction non trouve dans les donnees"}
            
        transaction = db.query(Transaction).filter(
            Transaction.donnees_passerelle.contains(transaction_id_fourni) # Recherche basique, e ameliorer
        ).first()
        
        if not transaction:
            return {"status": "error", "message": "Transaction non trouvee dans la base"}
            
        # Mettre e jour la transaction
        transaction.statut = resultat_verification["statut"]
        transaction.donnees_passerelle = str({**eval(transaction.donnees_passerelle), **resultat_verification})
        transaction.date_mise_a_jour = datetime.utcnow()
        
        # Mettre e jour la demande associee
        demande = transaction.demande
        if resultat_verification["statut"] == "SUCCES":
            demande.statut_paiement = StatutPaiement.PAYE
            demande.statut = StatutDemande.SOUMISE
        elif resultat_verification["statut"] == "ECHEC":
            demande.statut_paiement = StatutPaiement.ECHEC
            
        db.commit()
        
        return {"status": "success", "message": "Transaction mise e jour"}
        
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Erreur lors du traitement du webhook: {str(e)}"}

# Fonction pour gerer les virements (logique simplifiee)
def traiter_virement(db: Session, demande_id: int) -> DemandeClient:
    """
    Traite une demande de paiement par virement.
    """
    demande = db.query(DemandeClient).filter(DemandeClient.id == demande_id).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvee")
        
    if demande.methode_paiement != MethodePaiement.VIREMENT:
        raise HTTPException(status_code=400, detail="La methode de paiement n'est pas un virement")
        
    # Pour un virement, on peut passer directement e un statut d'attente de confirmation
    # ou la soumettre directement si la logique le permet
    demande.statut = StatutDemande.SOUMISE # ou DOCUMENTS_EN_ATTENTE
    db.commit()
    db.refresh(demande)
    return demande
