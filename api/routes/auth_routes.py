# api/routes/auth_routes.py
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
from jose import JWTError, jwt
from datetime import timedelta, datetime

# Importation de la configuration centralisée
from app_config import templates

# === Importation des modèles, schémas, services, etc. ===
from models import User, Role
from auth import authenticate_user, create_access_token, get_password_hash
from database import get_db
from session import Settings

# Création du routeur
router = APIRouter(prefix="/auth", tags=["auth"])

# Page d'inscription
@router.get("/register", name="register_page")
def register_page(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "now": datetime.now(), "error": None}
    )

# Traitement de l'inscription
@router.post("/register")
async def register_user(
    request: Request,
    nom: str = Form(...),
    prenom: str = Form(...),
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    type_compte: str = Form(...),
    numero_etudiant: Optional[str] = Form(None),
    annee_obtention: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    # Vérifier si les mots de passe correspondent
    if password != confirm_password:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Les mots de passe ne correspondent pas",
                "now": datetime.now()
            }
        )
    
    # Vérifier si l'utilisateur existe déjà
    existing_user = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()
    
    if existing_user:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Ce nom d'utilisateur ou cette adresse email est déjà utilisé",
                "now": datetime.now()
            }
        )
    
    # Vérifier que le type de compte est bien "etudiant"
    if type_compte != "etudiant": 
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Seule l'inscription en tant qu'étudiant/client est autorisée",
                "now": datetime.now()
            }
        )
    
    # Récupérer le rôle étudiant/client (user)
    role = db.query(Role).filter(Role.name == "user").first()
    if not role:
        # Créer le rôle s'il n'existe pas
        role = Role(name="user")
        db.add(role)
        db.commit()
        db.refresh(role)
    
    # Créer l'utilisateur
    hashed_password = get_password_hash(password)
    new_user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        nom=nom,
        prenom=prenom,
        date_inscription=datetime.now(),
        numero_etudiant=numero_etudiant,
        annee_obtention=annee_obtention
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Associer le rôle
    new_user.roles = [role]
    db.commit()
    db.refresh(new_user)
    
    # --- Authentification automatique après inscription ---
    settings = Settings()
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(new_user.id)}, expires_delta=access_token_expires
    )
    
    # CORRECTION: Rediriger vers la bonne URL avec préfixe
    response = RedirectResponse(url="/auth/redirect-after-login", status_code=303)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        # secure=True, # A décommenter en production avec HTTPS
    )
    
    return response

# Route d'accueil accessible à tous
@router.get("/", name="auth_index")
def auth_home(request: Request, db: Session = Depends(get_db)):
    user = None
    user_role = None

    # Récupérer le token depuis le cookie ou l'en-tête
    token_from_cookie = request.cookies.get("access_token")
    token_from_header = request.headers.get("Authorization")
    
    token = token_from_cookie or token_from_header

    if token:
        # Nettoyer le token
        if token.startswith("Bearer "):
            token = token[7:]
        elif token.startswith("bearer "):
            token = token[7:]

        try:
            settings = Settings()
            # CORRECTION: Utiliser les mêmes noms de propriétés partout
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            user_id = int(payload.get("sub"))
            user = db.query(User).filter(User.id == user_id).first()

            # Déterminer le rôle principal de l'utilisateur
            if user and user.roles:
                role_names = {role.name for role in user.roles}
                if "admin" in role_names:
                    user_role = "admin"
                elif "COURIEL" in role_names:
                    user_role = "fournisseur"
                elif "user" in role_names:
                    user_role = "client"
                else:
                    user_role = "user"
        except (JWTError, ValueError, Exception) as e:
            # Token invalide, continuer comme utilisateur non connecté
            pass

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
            "user_role": user_role,
            "now": datetime.now()
        }
    )

# Page de connexion
@router.get("/login", name="login_page")
def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "now": datetime.now(), "error": None}
    )

# Route de redirection post-connexion
@router.get("/redirect-after-login")
async def redirect_after_login(
    request: Request,
    db: Session = Depends(get_db)
):
    # Récupération du token
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            response = RedirectResponse(url="/auth/login")
            response.delete_cookie("access_token")
            return response

    # Nettoyage du token
    if token.startswith("Bearer "):
        token = token[7:]
    elif token.startswith("bearer "):
        token = token[7:]

    try:
        settings = Settings()
        # CORRECTION: Utiliser les mêmes noms de propriétés
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM] # Au lieu de JWT_ALGORITHM
        )
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError) as e:
        response = RedirectResponse(url="/auth/login")
        response.delete_cookie("access_token")
        return response

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        response = RedirectResponse(url="/auth/login")
        response.delete_cookie("access_token")
        return response

    # Détermination de la redirection en fonction des rôles
    role_names = {role.name for role in user.roles}
    
    if "admin" in role_names:
        return RedirectResponse(url="/admin/dashboard")
    elif "COURIEL" in role_names:
        return RedirectResponse(url="/couriel/dashboard")
    elif "user" in role_names:
        return RedirectResponse(url="/etudiant/dashboard")
    
    # Redirection par défaut
    return RedirectResponse(url="/auth/")

# Authentification (endpoint pour le formulaire de login)
@router.post("/token")
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Identifiants invalides"},
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    # Créer le token d'accès
    access_token = create_access_token(data={"sub": str(user.id)})
    
    # OPTION 1: Redirection directe (recommandée)
    response = RedirectResponse(url="/auth/redirect-after-login", status_code=303)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        samesite="lax"
        # secure=True, # A décommenter en production avec HTTPS
    )
    return response
    
    # OPTION 2: Utiliser redirector.html (commenté)
    # return templates.TemplateResponse(
    #     "redirector.html",
    #     {"request": request, "redirect_url": "/auth/redirect-after-login"},
    #     headers={"Set-Cookie": f"access_token=Bearer {access_token}; Path=/; HttpOnly; SameSite=Lax"}
    # )

# Route de déconnexion
@router.get("/logout")
def logout():
    response = RedirectResponse(url="/auth/", status_code=303)
    response.delete_cookie(key="access_token")
    return response
