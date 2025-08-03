# api/routes/user_routes.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db
from typing import  Optional
from models import User, Role,DemandeClient,StatutDemande, HistoriqueDemande
from schema import UserCreate, UserUpdate, UserResponse, DemandeStatusUpdate
from auth import get_current_user, has_role, get_password_hash
from datetime import datetime
import secrets
import string
from app_config import templates
router = APIRouter(prefix="/admin/users", tags=["users"])
@router.post("/{user_id}/reset-password", response_class=JSONResponse)
def reset_user_password(
    user_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    """
    Resets a user's password. Only accessible by admins.
    Returns the new plaintext password (3 letters + 2 digits + 1 special character).
    """
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    # Define character sets
    letters = string.ascii_letters
    digits = string.digits
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    # Generate password: 3 letters + 2 digits + 1 special character
    new_password_plaintext = (
        ''.join(secrets.choice(letters) for _ in range(3)) +
        ''.join(secrets.choice(digits) for _ in range(2)) +
        secrets.choice(special_chars)
    )

    # Shuffle the password to make it less predictable
    new_password_plaintext = ''.join(secrets.SystemRandom().sample(new_password_plaintext, len(new_password_plaintext)))

    # Hash and store the new password
    user.hashed_password = get_password_hash(new_password_plaintext)
    user.date_modification = datetime.utcnow()  # Update modification date
    db.commit()

    # Return the new plaintext password in JSON
    return JSONResponse(content={"new_password": new_password_plaintext})

@router.get("/users", response_class=HTMLResponse)
def list_users_page(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    users = db.query(User).all()
    all_roles = db.query(Role).all()
    
    return templates.TemplateResponse(
        "admin/admin_users.html",
        {
            "request": request,
            "users": users,
            "all_roles": all_roles,
            "now": datetime.now()
        }
    )

@router.get("/{user_id}", response_class=HTMLResponse)
def get_user_detail_page(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    all_roles = db.query(Role).all()
    
    return templates.TemplateResponse(
        "admin/admin_users.html",  # Réutilise le même template pour l'édition
        {
            "request": request,
            "users": [user],  # Pour la compatibilité avec le template
            "all_roles": all_roles,
            "editing_user": user,
            "now": datetime.now()
        }
    )

@router.post("/", response_model=UserResponse)
def create_user(
    user: UserCreate, 
    db: Session = Depends(get_db), 
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    # Vérifier si l'utilisateur existe déjà
    existing_user = db.query(User).filter(
        (User.username == user.username) | (User.email == user.email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Un utilisateur avec ce nom ou email existe déjà"
        )
    
    hashed_password = get_password_hash(user.password)
    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        date_inscription=datetime.utcnow()
    )
    
    # Ajouter les rôles sélectionnés
    if user.roles:
        roles = db.query(Role).filter(Role.id.in_(user.roles)).all()
        new_user.roles = roles
    else:
        # Par défaut, attribuer le rôle 'user'
        user_role = db.query(Role).filter(Role.name == "user").first()
        if user_role:
            new_user.roles = [user_role]
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        roles=[role.name for role in new_user.roles],
        date_inscription=new_user.date_inscription
    )

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int, 
    user_update: UserUpdate, 
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    # Mise à jour des champs de base
    if user_update.username:
        user.username = user_update.username
    if user_update.email:
        user.email = user_update.email
    if user_update.password:
        user.hashed_password = get_password_hash(user_update.password)
    
    # Mise à jour des rôles
    if user_update.roles is not None:
        roles = db.query(Role).filter(Role.id.in_(user_update.roles)).all()
        user.roles = roles
    
    user.date_modification = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        roles=[role.name for role in user.roles],
        date_inscription=user.date_inscription
    )

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    # Empêcher la suppression de l'utilisateur actuel
    if user.id == current_user_id:
        raise HTTPException(
            status_code=400,
            detail="Vous ne pouvez pas supprimer votre propre compte"
        )
    
    db.delete(user)
    db.commit()
    
    return {"message": "Utilisateur supprimé avec succès"}

# Routes pour la gestion des demandes
@router.get("/admin/demandes", response_class=HTMLResponse)
def list_demandes_page(
    request: Request,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    query = db.query(DemandeClient)
    
    if status and status != "all":
        query = query.filter(DemandeClient.statut == status)
    
    demandes = query.order_by(desc(DemandeClient.date_creation)).all()
    
    return templates.TemplateResponse(
        "admin/admin_demandes.html",
        {
            "request": request,
            "demandes": demandes,
            "statuts_possibles": StatutDemande,
            "now":datetime.now()
        }
    )

@router.get("/admin/demandes/{demande_id}", response_class=HTMLResponse)
def get_demande_detail_page(
    request: Request,
    demande_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    demande = db.query(DemandeClient).filter(DemandeClient.id == demande_id).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvée")
    
    # Charger les relations nécessaires
    demande.documents  # Charge les documents associés
    demande.fichiers  # Charge les fichiers associés
    demande.historique  # Charge l'historique
    
    return templates.TemplateResponse(
        "admin_demande_detail.html",
        {
            "request": request,
            "demande": demande,
            "statuts_possibles": StatutDemande
        }
    )

@router.put("/admin/demandes/{demande_id}/status")
def update_demande_status(
    demande_id: int,
    status_update: DemandeStatusUpdate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    demande = db.query(DemandeClient).filter(DemandeClient.id == demande_id).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvée")
    
    # Enregistrer l'ancien statut
    ancien_statut = demande.statut
    
    # Mettre à jour le statut
    demande.statut = status_update.status
    demande.date_modification = datetime.utcnow()
    
    # Si la demande est complétée, enregistrer la date de traitement
    if status_update.status == StatutDemande.COMPLETEE:
        demande.date_traitement = datetime.utcnow()
    
    # Ajouter une entrée dans l'historique
    historique = HistoriqueDemande(
        demande_id=demande_id,
        utilisateur_id=current_user_id,
        statut_precedent=ancien_statut.value,
        statut_nouveau=status_update.status.value,
        commentaire=status_update.comment,
        date_action=datetime.utcnow()
    )
    db.add(historique)
    
    db.commit()
    db.refresh(demande)
    
    return {"message": "Statut mis à jour avec succès"}
 
@router.get("/admin/dashboard")
def admin_dashboard(request: Request, user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    if not has_role(user_id, "admin", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé aux admins")

    # Récupérer les statistiques
    total_users = db.query(User).count()
    total_demandes = db.query(DemandeClient).count()
    demandes_en_cours = db.query(DemandeClient).filter(DemandeClient.statut == StatutDemande.EN_TRAITEMENT).count()
    demandes_completees = db.query(DemandeClient).filter(DemandeClient.statut == StatutDemande.COMPLETEE).count()
    current_user = db.query(User).filter(User.id == user_id).first()
    # Dernières demandes
    recent_demandes = db.query(DemandeClient).order_by(desc(DemandeClient.date_creation)).limit(5).all()

    # Derniers utilisateurs
    recent_users = db.query(User).order_by(desc(User.date_inscription)).limit(5).all()

    # Initialize empty chart data if not using the chart
    chart_data = {
        "counts": [],
        "months": []
    }

    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "user": db.query(User).filter(User.id == user_id).first(),
            "total_users": total_users,
            "total_demandes": total_demandes,
            "demandes_en_cours": demandes_en_cours,
            "demandes_completees": demandes_completees,
            "current_user": current_user,
            "recent_demandes": recent_demandes,
            "recent_users": recent_users,
            "now": datetime.now(),
            "chart_data": chart_data  # Make sure this is defined
        }
    )