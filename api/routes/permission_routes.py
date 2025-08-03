# api/routes/permission_routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Permission
from schema import PermissionCreate, PermissionUpdate, PermissionResponse
from auth import get_current_user, has_role

router = APIRouter(prefix="/admin/permissions", tags=["permissions"])

@router.post("/", response_model=PermissionResponse)
def create_permission(
    permission: PermissionCreate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    # Vérifier si la permission existe déjà
    existing_perm = db.query(Permission).filter(Permission.name == permission.name).first()
    if existing_perm:
        raise HTTPException(
            status_code=400,
            detail="Une permission avec ce nom existe déjà"
        )
    
    new_permission = Permission(name=permission.name)
    db.add(new_permission)
    db.commit()
    db.refresh(new_permission)
    
    return PermissionResponse(
        id=new_permission.id,
        name=new_permission.name
    )

@router.put("/{permission_id}", response_model=PermissionResponse)
def update_permission(
    permission_id: int,
    permission_update: PermissionUpdate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Permission non trouvée")
    
    permission.name = permission_update.name
    db.commit()
    db.refresh(permission)
    
    return PermissionResponse(
        id=permission.id,
        name=permission.name
    )

@router.delete("/{permission_id}")
def delete_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    if not has_role(current_user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Permission non trouvée")
    
    # Vérifier si la permission est utilisée par des rôles
    if permission.roles:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer une permission associée à des rôles"
        )
    
    db.delete(permission)
    db.commit()
    
    return {"message": "Permission supprimée avec succès"}
 
