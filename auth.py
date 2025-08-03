from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from models import User, Role
from session import settings
from typing import  Optional
import logging

# Configuration du logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Création d'un handler pour écrire dans un fichier
file_handler = logging.FileHandler('api.log')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Optionnel : Ajouter un handler pour la console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
logger.addHandler(console_handler)
from database import get_db
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
         expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token", auto_error=False)

class RedirectToHomeException(Exception):
    pass

async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> int:
    # Exception pour la redirection
    redirect_exception = RedirectToHomeException()

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentification requise",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        token = request.cookies.get("access_token")
        if token:
            token = token.replace("Bearer ", "").replace("bearer ", "")

    if not token:
        raise redirect_exception  # Lève l'exception de redirection

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")
        if not user_id:
            raise redirect_exception  # Lève l'exception de redirection

        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise redirect_exception  # Lève l'exception de redirection

        return int(user_id)

    except JWTError as e:
        logging.error(f"Erreur JWT : {str(e)}")
        raise redirect_exception  # Lève l'exception de redirection
def has_role(user_id: int, role_name: str, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    return any(role.name == role_name for role in user.roles)  # role.name au lieu de Role.name
# Vérifier plusieurs rôles
def has_any_role(user_id: int, roles: list, db: Session) -> bool:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    user_roles = {role.name for role in user.roles}
    return bool(user_roles & set(roles))
def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Vérifie les identifiants et retourne l'utilisateur si valide"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
# # Utilisation
#     if not has_any_role(user_id, ["admin", "superadmin"], db):
#     raise HTTPException(status_code=403, detail="Permission denied")