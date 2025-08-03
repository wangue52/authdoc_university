# api/routes/couriel_routes.py
"""Routes dediees au service COURIEL."""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db
from models import User, DemandeClient, StatutDemande, TypeReponse, NiveauSecurite,ReponseDemande
from auth import get_current_user, has_role
from services.couriel_service import (
    receptionner_demande, preparer_reponse_document_scanne, get_statistiques
)
import os
import uuid
from datetime import datetime
from app_config import templates
router = APIRouter(prefix="/couriel", tags=["couriel"])

# Constante pour le dossier d'upload temporaire des scans
UPLOAD_SCAN_DIR = "uploads/scans_couriel"
os.makedirs(UPLOAD_SCAN_DIR, exist_ok=True)

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dashboard du service COURIEL."""
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=403, detail="Acces reserve au service COURIEL")
        
    user = db.query(User).filter(User.id == user_id).first()
    stats = get_statistiques(db)
    
    # Demandes recentes SOUMISES (e receptionner)
    nouvelles_demandes = db.query(DemandeClient).filter(
        DemandeClient.statut == StatutDemande.SOUMISE
    ).order_by(desc(DemandeClient.date_creation)).limit(5).all()
    
    # Demandes recemment REeUES (e traiter manuellement)
    demandes_recues = db.query(DemandeClient).filter(
        DemandeClient.statut == StatutDemande.RECU
    ).order_by(desc(DemandeClient.date_reception)).limit(5).all()
    
    return templates.TemplateResponse(
        "couriel/dashboard.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
            "nouvelles_demandes": nouvelles_demandes,
            "demandes_recues": demandes_recues,
            "now": datetime.now()
        }
    )

@router.get("/demandes", response_class=HTMLResponse)
async def liste_demandes(
    request: Request,
    statut: str = None,
    page: int = 1,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Liste des demandes pour le service COURIEL."""
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=403, detail="Acces reserve au service COURIEL")
        
    user = db.query(User).filter(User.id == user_id).first()
    
    # Construire la requete
    query = db.query(DemandeClient)
    
    # Filtrer par statut
    if statut:
        try:
            statut_enum = StatutDemande(statut)
            query = query.filter(DemandeClient.statut == statut_enum)
        except ValueError:
            pass # Ignorer un statut invalide
    
    # Pagination
    per_page = 10
    total = query.count()
    total_pages = (total + per_page - 1) // per_page
    demandes = query.order_by(desc(DemandeClient.date_creation)).offset((page - 1) * per_page).limit(per_page).all()
    
    return templates.TemplateResponse(
        "couriel/liste_demandes.html",
        {
            "request": request,
            "user": user,
            "demandes": demandes,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "status_filter": statut,
            "now": datetime.now()
        }
    )

@router.get("/demandes/{demande_id}", response_class=HTMLResponse)
async def details_demande(
    request: Request,
    demande_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Details d'une demande."""
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=403, detail="Acces reserve au service COURIEL")
        
    demande = db.query(DemandeClient).filter(DemandeClient.id == demande_id).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvee")
        
    user = db.query(User).filter(User.id == user_id).first()
    
    return templates.TemplateResponse(
        "couriel/details_demande.html",
        {
            "request": request,
            "user": user,
            "demande": demande,
            "now": datetime.now()
        }
    )

# --- Workflow : Reception ---
@router.get("/demandes/{demande_id}/reception", response_class=HTMLResponse)
async def formulaire_reception(
    request: Request,
    demande_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Affiche le formulaire pour receptionner une demande."""
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=403, detail="Acces reserve au service COURIEL")
        
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.statut == StatutDemande.SOUMISE
    ).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvee ou deje receptionnee")
        
    user = db.query(User).filter(User.id == user_id).first()
    
    return templates.TemplateResponse(
        "couriel/reception_demande.html",
        {
            "request": request,
            "user": user,
            "demande": demande,
            "now": datetime.now()
        }
    )

@router.post("/demandes/{demande_id}/reception")
async def receptionner(
    demande_id: int,
    notes: str = Form(""),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Receptionne une demande."""
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=403, detail="Acces reserve au service COURIEL")
        
    try:
        receptionner_demande(db, demande_id, notes, user_id)
        return RedirectResponse(url=f"/couriel/demandes/{demande_id}", status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

# --- Workflow : Reponse apres traitement manuel et scan ---
@router.get("/demandes/{demande_id}/reponse", response_class=HTMLResponse)
async def formulaire_reponse(
    request: Request,
    demande_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Affiche le formulaire pour preparer la reponse avec le document scanne."""
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=403, detail="Acces reserve au service COURIEL")
        
    # La demande doit etre RECU
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.statut == StatutDemande.RECU
    ).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvee ou pas prete pour la reponse")
        
    user = db.query(User).filter(User.id == user_id).first()
    
    return templates.TemplateResponse(
        "couriel/reponse_demande.html", # Ce template doit permettre d'uploader le scan
        {
            "request": request,
            "user": user,
            "demande": demande,
            "type_reponse_enum": TypeReponse,
            "niveau_securite_enum": NiveauSecurite,
            "now": datetime.now()
        }
    )

@router.post("/demandes/{demande_id}/reponse")
async def preparer_reponse(
    demande_id: int,
    fichier_scan: UploadFile = File(...),
    type_reponse: TypeReponse = Form(...),
    contenu: str = Form(...), # Reference ou description du document
    niveau_securite: NiveauSecurite = Form(NiveauSecurite.STANDARD),
    qr_code: bool = Form(True),
    filigrane: bool = Form(True),
    signature_numerique: bool = Form(False), # Watermark anti-photocopie
    commentaire_public: str = Form(""),
    commentaire_interne: str = Form(""),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Prepare la reponse en securisant le document scanne."""
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=403, detail="Acces reserve au service COURIEL")
        
    # Sauvegarder temporairement le fichier scanne
    try:
        scan_filename = f"scan_{demande_id}_{uuid.uuid4().hex[:8]}_{fichier_scan.filename}"
        scan_path = os.path.join(UPLOAD_SCAN_DIR, scan_filename)
        
        with open(scan_path, "wb") as buffer:
            content = await fichier_scan.read()
            buffer.write(content)
            
        # Utiliser le service pour preparer la reponse
        reponse = preparer_reponse_document_scanne(
            db=db,
            demande_id=demande_id,
            fichier_scanne_path=scan_path,
            type_reponse=type_reponse,
            contenu=contenu,
            niveau_securite=niveau_securite,
            qr_code=qr_code,
            filigrane=filigrane,
            signature_numerique=signature_numerique,
            commentaire_public=commentaire_public,
            commentaire_interne=commentaire_interne,
            user_id=user_id
        )
        
        # Nettoyer le fichier scan temporaire
        if os.path.exists(scan_path):
            os.remove(scan_path)
            
        return RedirectResponse(url=f"/couriel/demandes/{demande_id}/confirmation", status_code=303)
        
    except HTTPException:
        # Nettoyer en cas d'erreur
        if 'scan_path' in locals() and os.path.exists(scan_path):
            os.remove(scan_path)
        raise
    except Exception as e:
        # Nettoyer en cas d'erreur
        if 'scan_path' in locals() and os.path.exists(scan_path):
            os.remove(scan_path)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la preparation de la reponse: {str(e)}")

@router.get("/demandes/{demande_id}/confirmation", response_class=HTMLResponse)
async def confirmation_reponse(
    request: Request,
    demande_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Page de confirmation apres preparation de la reponse."""
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=403, detail="Acces reserve au service COURIEL")
        
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.statut == StatutDemande.COMPLETEE
    ).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvee ou reponse non preparee")
        
    # Recuperer la derniere reponse
    reponse = db.query(ReponseDemande).filter(
        ReponseDemande.demande_id == demande_id
    ).order_by(ReponseDemande.date_creation.desc()).first()
    
    user = db.query(User).filter(User.id == user_id).first()
    
    return templates.TemplateResponse(
        "couriel/confirmation_reponse.html",
        {
            "request": request,
            "user": user,
            "demande": demande,
            "reponse": reponse,
            "now": datetime.now()
        }
    )
