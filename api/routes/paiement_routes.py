# api/routes/paiement_routes.py
"""Routes pour la gestion des paiements."""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from models import DemandeClient, StatutDemande, StatutPaiement, MethodePaiement
from auth import get_current_user
from services.paiement_service import initier_paiement, traiter_retour_paiement, traiter_webhook_paiement

router = APIRouter(prefix="/paiement", tags=["paiements"])

# Route pour initier le paiement
@router.get("/initier/{demande_id}")
async def initier_paiement_route(
    demande_id: int,
    request: Request,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initie le processus de paiement pour une demande et redirige vers la passerelle.
    """
    # Verifier que la demande appartient e l'utilisateur et est en attente de paiement
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.client_id == user_id,
        DemandeClient.statut == StatutDemande.PAIEMENT_EN_ATTENTE
    ).first()
    
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvee ou non eligible au paiement")
    
    # URL de base pour les retours (e configurer selon votre environnement)
    url_base_retour = str(request.base_url).rstrip('/')
    
    try:
        # Initier le paiement
        details_paiement = initier_paiement(db, demande_id, url_base_retour)
        
        # Rediriger vers la passerelle de paiement
        return RedirectResponse(url=details_paiement["url_redirection"], status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'initiation du paiement: {str(e)}")

# Route de retour en cas de succes
@router.get("/succes", response_class=HTMLResponse)
async def retour_paiement_succes(
    demande_id: int = Query(...),
    # Vous pouvez ajouter d'autres parametres de requete fournis par la passerelle
    request: Request = None,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Page de retour apres un paiement reussi.
    """
    try:
        # Traiter le retour (met e jour la base de donnees)
        demande = traiter_retour_paiement(db, demande_id, "SUCCES")
        
        # Verifier que la demande appartient e l'utilisateur
        if demande.client_id != user_id:
            raise HTTPException(status_code=403, detail="Acces non autorise")
            
        return templates.TemplateResponse(
            "etudiant/paiement_succes.html",
            {
                "request": request,
                "demande": demande,
                "now": datetime.now()
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement du retour: {str(e)}")

# Route de retour en cas d'echec
@router.get("/echec", response_class=HTMLResponse)
async def retour_paiement_echec(
    demande_id: int = Query(...),
    # Vous pouvez ajouter d'autres parametres de requete fournis par la passerelle
    request: Request = None,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Page de retour apres un echec de paiement.
    """
    try:
        # Traiter le retour (met e jour la base de donnees)
        demande = traiter_retour_paiement(db, demande_id, "ECHEC")
        
        # Verifier que la demande appartient e l'utilisateur
        if demande.client_id != user_id:
             raise HTTPException(status_code=403, detail="Acces non autorise")
            
        return templates.TemplateResponse(
            "etudiant/paiement_echec.html",
            {
                "request": request,
                "demande": demande,
                "now": datetime.now()
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement du retour: {str(e)}")

# Webhook pour recevoir les notifications des passerelles
# Note : Ces routes ne necessitent PAS d'authentification utilisateur
# car elles sont appelees par les services de paiement.
@router.post("/webhook/{methode}")
async def webhook_paiement(
    methode: str,
    payload: dict, # Les donnees exactes dependront de la passerelle
    db: Session = Depends(get_db)
):
    """
    Point de terminaison pour recevoir les notifications de paiement 
    des passerelles externes (webhooks).
    """
    try:
        # Convertir la methode en enum
        methode_enum = MethodePaiement(methode.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Methode de paiement non supportee")
    
    # Traiter le webhook
    resultat = traiter_webhook_paiement(db, methode_enum, payload)
    
    # Repondre avec un code HTTP approprie
    if resultat["status"] == "success":
        return {"status": "ok"}
    else:
        # Selon la passerelle, vous pourriez vouloir renvoyer un code d'erreur
        # pour qu'elle retente plus tard
        raise HTTPException(status_code=400, detail=resultat["message"])
