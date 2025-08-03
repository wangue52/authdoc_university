from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Modèles pour les utilisateurs
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    roles: List[int] = []

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    roles: Optional[List[int]] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    roles: List[str]
    date_inscription: datetime

# Modèles pour les rôles
class RoleCreate(BaseModel):
    name: str
    permissions: List[int] = []

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    permissions: Optional[List[int]] = None

class RoleResponse(BaseModel):
    id: int
    name: str
    permissions: List[str]

# Modèles pour les permissions
class PermissionCreate(BaseModel):
    name: str

class PermissionUpdate(BaseModel):
    name: str

class PermissionResponse(BaseModel):
    id: int
    name: str

# Modèles pour les demandes
class DemandeStatusUpdate(BaseModel):
    status: str
    comment: Optional[str] = None

class DocumentDemandeResponse(BaseModel):
    id: int
    type_document: str
    intitule: str
    nombre_copies: int
    prix_unitaire: float
    annee_obtention: Optional[str]
    institution: Optional[str]
    commentaire: Optional[str]

class FichierDocumentResponse(BaseModel):
    id: int
    nom_fichier: str
    chemin_fichier: str
    type_fichier: str
    taille: int
    date_upload: datetime
    est_verifie: bool

class HistoriqueDemandeResponse(BaseModel):
    id: int
    date_action: datetime
    statut_precedent: Optional[str]
    statut_nouveau: str
    commentaire: Optional[str]
    utilisateur_id: Optional[int]

class DemandeClientResponse(BaseModel):
    id: int
    reference: str
    type_service: str
    date_creation: datetime
    statut: str
    pour_tiers: bool
    tiers_nom: Optional[str]
    tiers_prenom: Optional[str]
    montant_total: Optional[float]
    methode_paiement: Optional[str]
    statut_paiement: str
    commentaire: Optional[str]
    documents: List[DocumentDemandeResponse]
    fichiers: List[FichierDocumentResponse]
    date_reception: Optional[datetime]
    date_traitement: Optional[datetime]
    date_reponse: Optional[datetime]
    code_verification: Optional[str]
    historique: List[HistoriqueDemandeResponse]
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    roles: List[str]

    class Config:
        from_attributes = True

class RoleCreate(BaseModel):
    name: str

class RoleResponse(BaseModel):
    id: int
    name: str
    permissions: List[str]

    class Config:
        from_attributes = True

class PermissionCreate(BaseModel):
    name: str

class PermissionResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class TokenRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class acceuil(BaseModel):
    pass