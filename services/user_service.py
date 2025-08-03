# services/user_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from models import User, Role
from schema import UserCreate, UserUpdate
from auth import get_password_hash
from typing import List, Optional

def get_user(db: Session, user_id: int) -> User:
    """Recupere un utilisateur par son ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouve")
    return user

def get_user_by_email(db: Session, email: str) -> User:
    """recuperer un utilisateur par son email."""
    return db.query(User).filter(User.email == email).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """recuperer une liste d'utilisateurs."""
    return db.query(User).offset(skip).limit(limit).all()

def create_user(db: Session, user: UserCreate) -> User:
    """creer un nouvel utilisateur."""
    # Verifier si l'utilisateur existe deje
    existing_user = db.query(User).filter(
        (User.username == user.username) | (User.email == user.email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Un utilisateur avec ce nom ou email existe deja"
        )
    
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        nom=user.nom,
        prenom=user.prenom,
        numero_etudiant=user.numero_etudiant,
        annee_obtention=user.annee_obtention,
        date_inscription=datetime.utcnow()
    )
    
    # Ajouter les reles selectionnes
    if user.roles:
        roles = db.query(Role).filter(Role.id.in_(user.roles)).all()
        db_user.roles = roles
    else:
        # Par defaut, attribuer le rele 'user'
        user_role = db.query(Role).filter(Role.name == "user").first()
        if user_role:
            db_user.roles = [user_role]
            
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user_update: UserUpdate) -> User:
    """Met e jour un utilisateur."""
    db_user = get_user(db, user_id)
    
    # Mise e jour des champs de base
    if user_update.username is not None:
        db_user.username = user_update.username
    if user_update.email is not None:
        db_user.email = user_update.email
    if user_update.password is not None:
        db_user.hashed_password = get_password_hash(user_update.password)
    if user_update.nom is not None:
        db_user.nom = user_update.nom
    if user_update.prenom is not None:
        db_user.prenom = user_update.prenom
    if user_update.numero_etudiant is not None:
        db_user.numero_etudiant = user_update.numero_etudiant
    if user_update.annee_obtention is not None:
        db_user.annee_obtention = user_update.annee_obtention
        
    # Mise e jour des reles
    if user_update.roles is not None:
        roles = db.query(Role).filter(Role.id.in_(user_update.roles)).all()
        db_user.roles = roles
        
    db_user.date_modification = datetime.utcnow()
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int, current_user_id: int):
    """Supprime un utilisateur."""
    db_user = get_user(db, user_id)
    
    # Empecher la suppression de l'utilisateur actuel
    if db_user.id == current_user_id:
        raise HTTPException(
            status_code=400,
            detail="Vous ne pouvez pas supprimer votre propre compte"
        )
        
    db.delete(db_user)
    db.commit()
    return {"message": "Utilisateur supprime avec succes"}

# Pour les inscriptions etudiantes/partenaire, on pourrait avoir des fonctions specifiques
# mais pour l'instant, elles restent dans les routes.
 
