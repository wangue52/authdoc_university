# api/routes/partenaire_routes.py
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import EmailStr
from database import get_db
from models import User, Role, DemandeClient, TypeService, StatutDemande
from auth import get_current_user, has_role, get_password_hash
import os
import shutil
import uuid
from datetime import datetime

router = APIRouter(prefix="/partenaire", tags=["partenaires"])

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Enregistrement partenaire
@router.post("/register")
async def register_partenaire(
    request: Request,
    nom_organisation: str = Form(...),
    email: EmailStr = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    adresse: str = Form(...),
    pays: str = Form(...),
    telephone: str = Form(...),
    site_web: str = Form(None),
    db: Session = Depends(get_db)
):
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Les mots de passe ne correspondent pas")
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Cet email est deje utilise")
    # Creer le rele partenaire s'il n'existe pas
    role = db.query(Role).filter(Role.name == "PARTENAIRE").first()
    if not role:
        role = Role(name="PARTENAIRE")
        db.add(role)
        db.commit()
    hashed_password = get_password_hash(password)
    new_user = User(
        email=email,
        hashed_password=hashed_password,
        est_partenaire=True,
        nom_organisation=nom_organisation,
        adresse_organisation=adresse,
        pays_organisation=pays,
        telephone_organisation=telephone,
        site_web=site_web,
        roles=[role]
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/login", status_code=303)

# Tableau de bord partenaire
@router.get("/dashboard")
async def partenaire_dashboard(
    request: Request,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_role(user_id, "PARTENAIRE", db):
        raise HTTPException(status_code=403, detail="Acces non autorise")
    partenaire = db.query(User).get(user_id)
    demandes = db.query(DemandeClient)\
                .filter(DemandeClient.partenaire_id == user_id)\
                .order_by(DemandeClient.date_creation.desc())\
                .all()
    return templates.TemplateResponse(
        "partenaire/dashboard.html",
        {
            "request": request,
            "partenaire": partenaire,
            "demandes": demandes,
            "now": datetime.now()
        }
    )

# Soumission de demande par partenaire
@router.post("/demandes/nouvelle")
async def partenaire_nouvelle_demande(
    request: Request,
    type_service: TypeService = Form(...),
    etudiant_nom: str = Form(...),
    etudiant_prenom: str = Form(...),
    etudiant_email: EmailStr = Form(...),
    etudiant_date_naissance: str = Form(...),
    diplome_intitule: str = Form(...),
    diplome_annee: str = Form(...),
    fichier: UploadFile = File(...),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_role(user_id, "PARTENAIRE", db):
        raise HTTPException(status_code=403, detail="Acces non autorise")
    # Creer la demande
    reference = f"PART-{uuid.uuid4().hex[:6].upper()}"
    nouvelle_demande = DemandeClient(
        reference=reference,
        type_service=type_service,
        pour_tiers=True,
        tiers_nom=etudiant_nom,
        tiers_prenom=etudiant_prenom,
        tiers_email=etudiant_email,
        statut=StatutDemande.SOUMISE,
        partenaire_id=user_id,
        via_partenaire=True,
        destination="WES"  # Ou autre selon le partenaire
    )
    db.add(nouvelle_demande)
    db.commit()
    # Sauvegarder le fichier
    partenaire_dir = os.path.join(UPLOAD_DIR, f"partenaire_{user_id}")
    os.makedirs(partenaire_dir, exist_ok=True)
    file_path = os.path.join(partenaire_dir, fichier.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(fichier.file, buffer)
    return RedirectResponse(url="/partenaire/demandes", status_code=303)
 
