# api/routes/role_routes.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Role, Permission
from schema import RoleCreate, RoleUpdate, RoleResponse
from auth import get_current_user, has_role
from datetime import datetime
from app_config import templates
router = APIRouter(prefix="/admin/roles", tags=["roles"])

router.get("/", response_class=HTMLResponse)
def list_roles_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    roles = db.query(Role).all()
    permissions = db.query(Permission).all()
    
    return templates.TemplateResponse(
        "admin/admin_roles.html",
        {
            "request": request,
            "roles": roles,
            "permissions": permissions,
            "now":datetime.now()
        }
    )

@router.post("/", response_model=RoleResponse)
def create_role(
    role: RoleCreate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    # Vérifier si le rôle existe déjà
    existing_role = db.query(Role).filter(Role.name == role.name).first()
    if existing_role:
        raise HTTPException(
            status_code=400,
            detail="Un rôle avec ce nom existe déjà"
        )
    
    new_role = Role(name=role.name)
    
    # Ajouter les permissions sélectionnées
    if role.permissions:
        permissions = db.query(Permission).filter(Permission.id.in_(role.permissions)).all()
        new_role.permissions = permissions
    
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    
    return RoleResponse(
        id=new_role.id,
        name=new_role.name,
        permissions=[perm.name for perm in new_role.permissions]
    )

@router.put("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: int,
    role_update: RoleUpdate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rôle non trouvé")
    
    # Mise à jour du nom si fourni
    if role_update.name:
        role.name = role_update.name
    
    # Mise à jour des permissions si fournies
    if role_update.permissions is not None:
        permissions = db.query(Permission).filter(Permission.id.in_(role_update.permissions)).all()
        role.permissions = permissions
    
    db.commit()
    db.refresh(role)
    
    return RoleResponse(
        id=role.id,
        name=role.name,
        permissions=[perm.name for perm in role.permissions]
    )

@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rôle non trouvé")
    
    # Vérifier si le rôle est utilisé par des utilisateurs
    if role.users:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer un rôle associé à des utilisateurs"
        )
    
    db.delete(role)
    db.commit()
    
    return {"message": "Rôle supprimé avec succès"}

# Routes pour la gestion des permissions
