# models.py
# models.py
from sqlalchemy import Boolean, Table, Column, ForeignKey, Integer, String, DateTime, Float, Text, Enum as SQLEnum, UniqueConstraint, JSON
#                                                                                                                       
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import enum

Base = declarative_base()

# Tables existantes
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("role.id")),
    Column("permission_id", Integer, ForeignKey("permission.id")),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("user.id")),
    Column("role_id", Integer, ForeignKey("role.id")),
)

# Nouvelles énumérations pour les demandes clients
class TypeDocument(enum.Enum):
    DIPLOME = "DIPLOME"
    RELEVE_NOTES = "RELEVE_NOTES"
    ATTESTATION = "ATTESTATION"
    CERTIFICAT = "CERTIFICAT"
    AUTRE = "AUTRE"

class TypeService(enum.Enum):
    AUTHENTIFICATION = "AUTHENTIFICATION"
    DUPLICATA = "DUPLICATA"
    LEGALISATION = "LEGALISATION"
    TRADUCTION = "TRADUCTION"
    TRANSMISSION_PARTENAIRE = "TRANSMISSION_PARTENAIRE"

class StatutPaiement(enum.Enum):
    EN_ATTENTE = "EN_ATTENTE"
    PAYE = "PAYE"
    ECHOUE = "ECHOUE"
    REMBOURSE = "REMBOURSE"

class MethodePaiement(enum.Enum):
    ORANGE_MONEY = "ORANGE_MONEY"
    MOBILE_MONEY = "MOBILE_MONEY"
    VISA = "VISA"
    PAYPAL = "PAYPAL"
    VIREMENT = "VIREMENT"

class StatutDemande(enum.Enum):
    BROUILLON = "BROUILLON"
    PAIEMENT_EN_ATTENTE = "PAIEMENT_EN_ATTENTE"
    DOCUMENTS_EN_ATTENTE = "DOCUMENTS_EN_ATTENTE"
    SOUMISE = "SOUMISE"
    RECU = "RECU"  # Nouveau statut: Documents reçus par le service COURIEL
    EN_TRAITEMENT = "EN_TRAITEMENT"
    COMPLETEE = "COMPLETEE"
    REJETEE = "REJETEE"
    ANNULEE = "ANNULEE"

class TypeReponse(enum.Enum):
    AUTHENTIFICATION_POSITIVE = "AUTHENTIFICATION_POSITIVE"
    AUTHENTIFICATION_NEGATIVE = "AUTHENTIFICATION_NEGATIVE"
    DUPLICATA_DELIVRE = "DUPLICATA_DELIVRE"
    DOCUMENT_LEGALISE = "DOCUMENT_LEGALISE"
    DOCUMENT_TRADUIT = "DOCUMENT_TRADUIT"
    DOCUMENT_TRANSMIS = "DOCUMENT_TRANSMIS"
    DEMANDE_REJETEE = "DEMANDE_REJETEE"
    INFORMATION_ADDITIONNELLE = "INFORMATION_ADDITIONNELLE"

class NiveauSecurite(enum.Enum):
    STANDARD = "STANDARD"
    ELEVE = "ELEVE"
    TRES_ELEVE = "TRES_ELEVE"

# Modèles existants
class Permission(Base):
    __tablename__ = "permission"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")

class Role(Base):
    __tablename__ = "role"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    users = relationship("User", secondary="user_roles", back_populates="roles")

class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    nom = Column(String, nullable=True)
    prenom = Column(String, nullable=True)
    telephone = Column(String, nullable=True)
    date_inscription = Column(DateTime, default=datetime.utcnow)
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    # Définir explicitement la relation avec les demandes du client
    demandes = relationship("DemandeClient", foreign_keys="[DemandeClient.client_id]", back_populates="client")
    # Définir explicitement la relation avec les demandes traitées
    demandes_traitees = relationship("TraitementDemande", back_populates="agent_couriel")
    # Définir explicitement la relation avec les demandes pour partenaires
    demandes_partenaire = relationship("DemandeClient", foreign_keys="[DemandeClient.partenaire_id]", back_populates="partenaire")
    
    # Pour les partenaires    organisation = Column(String, nullable=True)
    pays = Column(String, nullable=True)
    est_verifie = Column(Boolean, default=False)
    numero_etudiant = Column(String, nullable=True)  # Ajouté pour les étudiants
    annee_obtention = Column(String, nullable=True)  # Ajouté pour les étudiants
    est_partenaire = Column(Boolean, default=False)
    nom_organisation = Column(String, nullable=True)
    adresse_organisation = Column(String, nullable=True)
    pays_organisation = Column(String, nullable=True)
    telephone_organisation = Column(String, nullable=True)
    site_web = Column(String, nullable=True)
    accreditations = Column(String, nullable=True)
# Modèle existant
class StatutEnvoi(enum.Enum):
    EN_ATTENTE = "EN_ATTENTE"
    ENVOYE = "ENVOYE"
    RECU = "RECU"
    TRAITER = "TRAITER"

# Nouveaux modèles pour les demandes clients
class DemandeClient(Base):
    __tablename__ = "demande_client"
    id = Column(Integer, primary_key=True, index=True)
    reference = Column(String, unique=True, index=True, nullable=False)
    client_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    # Relation avec le client - utiliser foreign_keys explicitement
    client = relationship("User", foreign_keys=[client_id], back_populates="demandes")
    dossier_path = Column(String, nullable=True)  # Chemin du dossier physique
    # Informations sur la demande
    type_service = Column(SQLEnum(TypeService), nullable=False)
    date_creation = Column(DateTime, default=datetime.utcnow)
    date_modification = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    statut = Column(SQLEnum(StatutDemande), default=StatutDemande.BROUILLON)
    
    # Informations sur le demandeur (si différent du client)
    pour_tiers = Column(Boolean, default=False)
    tiers_nom = Column(String, nullable=True)
    tiers_prenom = Column(String, nullable=True)
    tiers_email = Column(String, nullable=True)
    tiers_relation = Column(String, nullable=True)
    
    # Informations de paiement
    montant_total = Column(Float, nullable=True)
    methode_paiement = Column(SQLEnum(MethodePaiement), nullable=True)
    statut_paiement = Column(SQLEnum(StatutPaiement), default=StatutPaiement.EN_ATTENTE)
    reference_paiement = Column(String, nullable=True)
    date_paiement = Column(DateTime, nullable=True)
    
    # Détails de la demande
    commentaire = Column(Text, nullable=True)
    destination = Column(String, nullable=True)  # Destination finale des documents
    # Pas de relation inverse pour partenaire (utilisez backref dans User)
    # Nouvelles informations pour le suivi COURIEL
    date_reception = Column(DateTime, nullable=True)  # Date à laquelle le COURIEL a reçu la demande
    date_traitement = Column(DateTime, nullable=True)  # Date à laquelle la demande a été traitée
    date_reponse = Column(DateTime, nullable=True)  # Date à laquelle la réponse a été envoyée
    code_verification = Column(String, nullable=True)  # Code unique pour vérifier l'authenticité (pour QR code)
    transactions = relationship("Transaction", back_populates="demande", cascade="all, delete-orphan")
    # Relations
    documents = relationship("DocumentDemande", back_populates="demande", cascade="all, delete-orphan")
    fichiers = relationship("FichierDocument", back_populates="demande", cascade="all, delete-orphan")
    historique = relationship("HistoriqueDemande", back_populates="demande", cascade="all, delete-orphan")
    traitements = relationship("TraitementDemande", back_populates="demande", cascade="all, delete-orphan")
    reponses = relationship("ReponseDemande", back_populates="demande", cascade="all, delete-orphan")
    partenaire_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    partenaire = relationship("User", foreign_keys=[partenaire_id], back_populates="demandes_partenaire")
    via_partenaire = Column(Boolean, default=False)
class DocumentDemande(Base):
    __tablename__ = "document_demande"
    id = Column(Integer, primary_key=True, index=True)
    demande_id = Column(Integer, ForeignKey("demande_client.id"), nullable=False)
    demande = relationship("DemandeClient", back_populates="documents")
    
    type_document = Column(SQLEnum(TypeDocument), nullable=False)
    intitule = Column(String, nullable=False)  # Nom spécifique du document
    nombre_copies = Column(Integer, default=1)
    prix_unitaire = Column(Float, nullable=False)
    annee_obtention = Column(String, nullable=True)
    institution = Column(String, nullable=True)  # Institution qui a délivré le document original
    commentaire = Column(Text, nullable=True)

class FichierDocument(Base):
    __tablename__ = "fichier_document"
    id = Column(Integer, primary_key=True, index=True)
    demande_id = Column(Integer, ForeignKey("demande_client.id"), nullable=False)
    demande = relationship("DemandeClient", back_populates="fichiers")
    document_id = Column(Integer, ForeignKey("document_demande.id"), nullable=True)
    
    nom_fichier = Column(String, nullable=False)
    chemin_fichier = Column(String, nullable=False)
    type_fichier = Column(String, nullable=False)  # MIME type
    taille = Column(Integer, nullable=False)  # En octets
    date_upload = Column(DateTime, default=datetime.utcnow)
    est_original = Column(Boolean, default=True)  # S'il s'agit d'un document original ou généré par le système
    est_verifie = Column(Boolean, default=False)  # Si le document a été vérifié par un administrateur

class HistoriqueDemande(Base):
    __tablename__ = "historique_demande"
    id = Column(Integer, primary_key=True, index=True)
    demande_id = Column(Integer, ForeignKey("demande_client.id"), nullable=False)
    demande = relationship("DemandeClient", back_populates="historique")
    
    date_action = Column(DateTime, default=datetime.utcnow)
    statut_precedent = Column(String, nullable=True)
    statut_nouveau = Column(String, nullable=False)
    commentaire = Column(Text, nullable=True)
    utilisateur_id = Column(Integer, ForeignKey("user.id"), nullable=True)  # ID de l'utilisateur qui a fait l'action
    donnees_supplementaires = Column(JSON, nullable=True)  # Données supplémentaires au format JSON

# Nouveaux modèles pour le traitement COURIEL
class TraitementDemande(Base):
    __tablename__ = "traitement_demande"
    id = Column(Integer, primary_key=True, index=True)
    demande_id = Column(Integer, ForeignKey("demande_client.id"), nullable=False)
    demande = relationship("DemandeClient", back_populates="traitements")
    agent_couriel_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    agent_couriel = relationship("User", back_populates="demandes_traitees")
    
    date_debut = Column(DateTime, default=datetime.utcnow)
    date_fin = Column(DateTime, nullable=True)
    notes_internes = Column(Text, nullable=True)  # Notes visibles uniquement par le service COURIEL
    verification_effectuee = Column(Boolean, default=False)
    resultat_verification = Column(Boolean, nullable=True)
    details_verification = Column(Text, nullable=True)

class ReponseDemande(Base):
    __tablename__ = "reponse_demande"
    id = Column(Integer, primary_key=True, index=True)
    demande_id = Column(Integer, ForeignKey("demande_client.id"), nullable=False)
    demande = relationship("DemandeClient", back_populates="reponses")
    
    date_creation = Column(DateTime, default=datetime.utcnow)
    type_reponse = Column(SQLEnum(TypeReponse), nullable=False)
    contenu = Column(Text, nullable=False)  # Contenu de la réponse
    
    # Sécurité du document
    niveau_securite = Column(SQLEnum(NiveauSecurite), default=NiveauSecurite.STANDARD)
    qr_code = Column(Boolean, default=True)  # Si un QR code est généré
    filigrane = Column(Boolean, default=True)  # Si un filigrane est appliqué
    signature_numerique = Column(Boolean, default=True)  # Si une signature numérique est appliquée
    
    # Fichiers générés
    chemin_fichier_securise = Column(String, nullable=True)  # Chemin vers le fichier sécurisé
    document_original = Column(String, nullable=True)  # Chemin du document original
    # Informations d'envoi
    date_envoi = Column(DateTime, nullable=True)
    email_envoi = Column(String, nullable=True)  # Email auquel la réponse a été envoyée
    notification_envoyee = Column(Boolean, default=False)
    
    # Autres informations
    commentaire_public = Column(Text, nullable=True)  # Commentaire visible par le demandeur
    commentaire_interne = Column(Text, nullable=True)  # Commentaire visible uniquement par le service COURIEL
class Devise(enum.Enum):
    XAF = "FCFA"  # Francs CFA (par défaut)
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"
    XOF = "XOF"  # Franc CFA Ouest Africain

class TauxChange(Base):
    __tablename__ = "taux_change"
    
    id = Column(Integer, primary_key=True)
    devise_source = Column(SQLEnum(Devise), nullable=False)
    devise_cible = Column(SQLEnum(Devise), nullable=False)
    taux = Column(Float, nullable=False)
    date_maj = Column(DateTime, default=datetime.utcnow)
    actif = Column(Boolean, default=True)
# Modèles Pydantic pour l'API
class EnvoiCreate(BaseModel):
    numero_dossier: str
    commentaire: Optional[str] = None

class EnvoiUpdate(BaseModel):
    statut: StatutEnvoi
    commentaire: Optional[str] = None

class EnvoiResponse(BaseModel):
    id: int
    numero_dossier: str
    date_envoi: datetime
    statut: StatutEnvoi
    commentaire: Optional[str]
    file_path: Optional[str]
    service_technique_id: int

    class Config:
        from_attributes = True

# Nouveaux modèles Pydantic pour les demandes clients
class DocumentDemandeCreate(BaseModel):
    type_document: TypeDocument
    intitule: str
    nombre_copies: int = 1
    annee_obtention: Optional[str] = None
    institution: Optional[str] = None
    commentaire: Optional[str] = None

class DemandeClientCreate(BaseModel):
    type_service: TypeService
    pour_tiers: bool = False
    tiers_nom: Optional[str] = None
    tiers_prenom: Optional[str] = None
    tiers_email: Optional[EmailStr] = None
    tiers_relation: Optional[str] = None
    commentaire: Optional[str] = None
    destination: Optional[str] = None
    documents: List[DocumentDemandeCreate]
    
    @validator('tiers_nom', 'tiers_prenom', 'tiers_email', 'tiers_relation')
    def validate_tiers_info(cls, v, values, **kwargs):
        if values.get('pour_tiers', False) and not v:
            field_name = kwargs.get('field').name
            raise ValueError(f"{field_name} est requis lorsque la demande est pour un tiers")
        return v

class PaiementCreate(BaseModel):
    demande_id: int
    methode_paiement: MethodePaiement

# Nouveaux modèles Pydantic pour le service COURIEL
class TraitementDemandeCreate(BaseModel):
    notes_internes: Optional[str] = None
    verification_effectuee: bool = False
    resultat_verification: Optional[bool] = None
    details_verification: Optional[str] = None

class TraitementDemandeUpdate(BaseModel):
    notes_internes: Optional[str] = None
    verification_effectuee: Optional[bool] = None
    resultat_verification: Optional[bool] = None
    details_verification: Optional[str] = None
    date_fin: Optional[datetime] = None

class ReponseDemandeCreate(BaseModel):
    type_reponse: TypeReponse
    contenu: str
    niveau_securite: NiveauSecurite = NiveauSecurite.STANDARD
    qr_code: bool = True
    filigrane: bool = True
    signature_numerique: bool = True
    commentaire_public: Optional[str] = None
    commentaire_interne: Optional[str] = None

class DocumentDemandeResponse(BaseModel):
    id: int
    type_document: TypeDocument
    intitule: str
    nombre_copies: int
    prix_unitaire: float
    annee_obtention: Optional[str]
    institution: Optional[str]
    commentaire: Optional[str]

    class Config:
        from_attributes = True

class FichierDocumentResponse(BaseModel):
    id: int
    nom_fichier: str
    type_fichier: str
    taille: int
    date_upload: datetime
    est_verifie: bool

    class Config:
        from_attributes = True

class TraitementDemandeResponse(BaseModel):
    id: int
    demande_id: int
    agent_couriel_id: int
    date_debut: datetime
    date_fin: Optional[datetime]
    verification_effectuee: bool
    resultat_verification: Optional[bool]
    details_verification: Optional[str]

    class Config:
        from_attributes = True

class ReponseDemandeResponse(BaseModel):
    id: int
    demande_id: int
    date_creation: datetime
    type_reponse: TypeReponse
    contenu: str
    niveau_securite: NiveauSecurite
    qr_code: bool
    filigrane: bool
    signature_numerique: bool
    chemin_fichier_securise: Optional[str]
    date_envoi: Optional[datetime]
    notification_envoyee: bool
    commentaire_public: Optional[str]

    class Config:
        from_attributes = True

class DemandeClientResponse(BaseModel):
    id: int
    reference: str
    type_service: TypeService
    date_creation: datetime
    statut: StatutDemande
    pour_tiers: bool
    tiers_nom: Optional[str]
    tiers_prenom: Optional[str]
    montant_total: Optional[float]
    methode_paiement: Optional[MethodePaiement]
    statut_paiement: StatutPaiement
    commentaire: Optional[str]
    documents: List[DocumentDemandeResponse]
    fichiers: List[FichierDocumentResponse]
    date_reception: Optional[datetime]
    date_traitement: Optional[datetime]
    date_reponse: Optional[datetime]
    code_verification: Optional[str]

    class Config:
        from_attributes = True

class DemandeClientDetailResponse(DemandeClientResponse):
    traitements: List[TraitementDemandeResponse]
    reponses: List[ReponseDemandeResponse]

    class Config:
        from_attributes = True

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    demande_id = Column(Integer, ForeignKey("demande_client.id"), nullable=False)
    reference = Column(String, unique=True, index=True) # Référence unique pour la transaction
    methode_paiement = Column(SQLEnum(MethodePaiement), nullable=False)
    montant = Column(Float, nullable=False)
    devise = Column(SQLEnum(Devise), default=Devise.XAF)
    statut = Column(String, default="INITIE") # INITIE, SUCCES, ECHEC, ANNULE, etc.
    date_creation = Column(DateTime, default=datetime.utcnow)
    date_mise_a_jour = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Champs pour stocker les données spécifiques à la passerelle
    donnees_passerelle = Column(Text) # JSON ou texte pour les détails de la transaction chez le fournisseur
    # URL de retour/callback
    url_retour_succes = Column(String)
    url_retour_echec = Column(String)
    url_notification = Column(String) # Webhook
    
    # Relation
    demande = relationship("DemandeClient", back_populates="transactions")