# utils/validation_utils.py
from fastapi import HTTPException, status, UploadFile
from models import TypeService, MethodePaiement
from typing import Optional

async def valider_donnees_demande(
    type_service: TypeService,
    pour_tiers: bool,
    tiers_nom: Optional[str],
    tiers_prenom: Optional[str],
    tiers_email: Optional[str],
    tiers_relation: Optional[str],
    fichier: UploadFile,
    methode_paiement: MethodePaiement,
    telephone_paiement: Optional[str],
    montant_total: float,
    nombre_copies: int
):
    """Valide les donnees de la demande"""
    # Validation des informations tiers
    if pour_tiers:
        if not all([tiers_nom, tiers_prenom, tiers_email, tiers_relation]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Toutes les informations du tiers sont requises"
            )
        # Validation basique de l'email
        if tiers_email and '@' not in tiers_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email du tiers invalide"
            )
            
    # Validation du fichier
    if not fichier.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier fourni"
        )
    # Verifier la taille du fichier (max 5MB)
    if hasattr(fichier, 'size') and fichier.size > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier est trop volumineux (max 5MB)"
        )
    # Verifier le type de fichier
    types_autorises = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
    if fichier.content_type not in types_autorises:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Type de fichier non autorise. Utilisez PDF, JPG ou PNG"
        )
        
    # Validation des informations de paiement
    if methode_paiement in [MethodePaiement.ORANGE_MONEY, MethodePaiement.MOBILE_MONEY]:
        if not telephone_paiement:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Numero de telephone requis pour les paiements mobiles"
            )
        # Validation basique du numero (Cameroun)
        if not telephone_paiement.replace(' ', '').replace('+', '').isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Numero de telephone invalide"
            )
            
    # Validation du montant
    if montant_total <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Montant invalide"
        )
        
    # Validation du nombre de copies
    if nombre_copies < 1 or nombre_copies > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nombre de copies invalide (1-10)"
        )
 
