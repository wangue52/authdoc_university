# services/demande_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile
from models import (
    DemandeClient, DocumentDemande, FichierDocument, HistoriqueDemande,
    TypeService, TypeDocument, MethodePaiement, StatutDemande, StatutPaiement
)
from schema import DemandeStatusUpdate
from utils.validation_utils import valider_donnees_demande
from utils.calcul_utils import calculer_prix_demande, generer_reference_unique
from utils.file_utils import sauvegarder_fichier_securise
from datetime import datetime
from typing import List, Optional

# Supposons que SERVICE_PRICES est importe d'ailleurs
# from utils.calcul_utils import SERVICE_PRICES

async def creer_demande(
    db: Session,
    user_id: int,
    type_service: TypeService,
    pour_tiers: bool,
    tiers_nom: Optional[str],
    tiers_prenom: Optional[str],
    tiers_email: Optional[str],
    tiers_relation: Optional[str],
    commentaire: Optional[str],
    destination: Optional[str],
    type_document: TypeDocument,
    intitule: str,
    annee_obtention: Optional[str],
    institution: Optional[str],
    nombre_copies: int,
    fichier: UploadFile,
    methode_paiement: MethodePaiement,
    montant_total: float,
    telephone_paiement: Optional[str],
    service_prices: dict # Passer SERVICE_PRICES comme parametre
) -> DemandeClient:
    """Cree une nouvelle demande."""
    try:
        # Validation des donnees
        await valider_donnees_demande(
            type_service, pour_tiers, tiers_nom, tiers_prenom,
            tiers_email, tiers_relation, fichier, methode_paiement,
            telephone_paiement, montant_total, nombre_copies
        )
        
        # Calculer le prix reel et verifier avec le montant soumis
        prix_calcule = calculer_prix_demande(type_service, nombre_copies, service_prices)
        if abs(prix_calcule - montant_total) > 1:  # Tolerance d'1 FCFA
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le montant calcule ne correspond pas au montant soumis"
            )
            
        # Creer la demande avec toutes les nouvelles informations
        reference = generer_reference_unique(db)
        nouvelle_demande = DemandeClient(
            reference=reference,
            client_id=user_id,
            type_service=type_service,
            pour_tiers=pour_tiers,
            tiers_nom=tiers_nom,
            tiers_prenom=tiers_prenom,
            tiers_email=tiers_email,
            tiers_relation=tiers_relation,
            commentaire=commentaire,
            destination=destination,
            montant_total=montant_total,
            methode_paiement=methode_paiement,
            statut_paiement=StatutPaiement.EN_ATTENTE,
            statut=StatutDemande.PAIEMENT_EN_ATTENTE
        )
        db.add(nouvelle_demande)
        db.commit()
        db.refresh(nouvelle_demande)
        
        # Ajouter le document avec les nouvelles informations
        document = DocumentDemande(
            demande_id=nouvelle_demande.id,
            type_document=type_document,
            intitule=intitule,
            nombre_copies=nombre_copies,
            prix_unitaire=service_prices[type_service],
            annee_obtention=annee_obtention,
            institution=institution
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        
        # Gerer l'upload du fichier avec securite
        fichier_path = await sauvegarder_fichier_securise(fichier, user_id, nouvelle_demande.id)
        
        # Ajouter le fichier e la base de donnees
        fichier_document = FichierDocument(
            demande_id=nouvelle_demande.id,
            document_id=document.id,
            nom_fichier=fichier.filename,
            chemin_fichier=fichier_path,
            type_fichier=fichier.content_type,
            taille=fichier.size if hasattr(fichier, 'size') else 0 # os.path.getsize(fichier_path)
        )
        db.add(fichier_document)
        
        # Creer l'historique de la demande
        historique = HistoriqueDemande(
            demande_id=nouvelle_demande.id,
            statut_precedent=None,
            statut_nouveau=StatutDemande.PAIEMENT_EN_ATTENTE.value,
            commentaire="Demande creee, en attente de paiement",
            utilisateur_id=user_id,
            donnees_supplementaires=str({
                "type_service": type_service.value,
                "methode_paiement": methode_paiement.value,
                "montant": montant_total
            })
        )
        db.add(historique)
        db.commit()
        
        return nouvelle_demande
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la creation de la demande: {str(e)}"
        )

def mettre_a_jour_statut_demande(
    db: Session,
    demande_id: int,
    status_update: DemandeStatusUpdate,
    current_user_id: int
) -> DemandeClient:
    """Met e jour le statut d'une demande."""
    demande = db.query(DemandeClient).filter(DemandeClient.id == demande_id).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvee")
        
    # Enregistrer l'ancien statut
    ancien_statut = demande.statut
    
    # Mettre e jour le statut
    demande.statut = status_update.status
    demande.date_modification = datetime.utcnow()
    
    # Si la demande est completee, enregistrer la date de traitement
    if status_update.status == StatutDemande.COMPLETEE:
        demande.date_traitement = datetime.utcnow()
        
    # Ajouter une entree dans l'historique
    historique = HistoriqueDemande(
        demande_id=demande_id,
        utilisateur_id=current_user_id,
        statut_precedent=ancien_statut.value if ancien_statut else None,
        statut_nouveau=status_update.status.value,
        commentaire=status_update.comment,
        date_action=datetime.utcnow()
    )
    db.add(historique)
    db.commit()
    db.refresh(demande)
    return demande

def get_demandes(db: Session, skip: int = 0, limit: int = 100) -> List[DemandeClient]:
    """Recupere une liste de demandes."""
    return db.query(DemandeClient).offset(skip).limit(limit).all()

def get_demande(db: Session, demande_id: int) -> DemandeClient:
    """Recupere une demande par son ID."""
    demande = db.query(DemandeClient).filter(DemandeClient.id == demande_id).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvee")
    return demande

# Ajouter d'autres fonctions de service selon les besoins (receptionner, traiter, etc.)
 
