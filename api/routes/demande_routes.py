# api/routes/demande_routes.py
import asyncio
import shutil
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List
from database import get_db
from models import (
    DemandeClient, DocumentDemande, FichierDocument, HistoriqueDemande,
    TypeDocument, TypeService, StatutDemande, StatutPaiement, MethodePaiement,
    TraitementDemande, ReponseDemande, TypeReponse, NiveauSecurite, User
)
from schema import DemandeStatusUpdate
from auth import get_current_user, has_role
from services.demande_service import creer_demande, mettre_a_jour_statut_demande, get_demandes, get_demande
from utils.validation_utils import valider_donnees_demande
from utils.calcul_utils import calculer_prix_demande, generer_reference_unique

from utils.file_utils import sauvegarder_fichier_securise, creer_dossier_demande, PDFSecurityProcessor
# =============================================================
from utils.email_utils import envoyer_notification_reponse
# Assurez-vous que `templates` est accessible (via app_config ou autre)
# from app_config import templates # Décommentez si nécessaire

import os
# import shutil # Peut être nécessaire si vous utilisez shutil.copyfileobj ailleurs
import uuid
from datetime import datetime, timedelta
# Imports pour la fonction de sécurisation directe (si utilisée dans la route)
# Ces imports sont maintenant cohérents avec ceux de file_utils_optimise
import qrcode
# from reportlab.lib.pagesizes import letter # A4 est utilisé dans file_utils_optimise
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader # Import ajouté comme dans file_utils_optimise
# from PyPDF2 import PdfWriter, PdfReader # Importé dans file_utils_optimise
from app_config import templates
router = APIRouter()

# --- Constante pour les prix des services (à externaliser dans un config/service) ---
# Assurez-vous que SERVICE_PRICES est accessible. Si ce n'est pas le cas, définissez-le ici ou importez-le.
# Pour cet exemple, je le définis ici.
SERVICE_PRICES = {
    TypeService.AUTHENTIFICATION: 5000,
    TypeService.DUPLICATA: 10000,
    TypeService.LEGALISATION: 3000,
    TypeService.TRADUCTION: 15000,
    TypeService.TRANSMISSION_PARTENAIRE: 7500
}

# Routes pour les clients/étudiants
@router.get("/etudiant/demandes")
async def liste_demandes_client(
    request: Request,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = 1,
    status: Optional[str] = None
):
    if not has_role(user_id, "user", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé aux clients")
    user = db.query(User).filter(User.id == user_id).first()
    # Construire la requête de base
    query = db.query(DemandeClient).filter(DemandeClient.client_id == user_id)
    # Filtrer par statut si nécessaire
    if status:
        try:
            statut_enum = StatutDemande(status)
            query = query.filter(DemandeClient.statut == statut_enum)
        except ValueError:
            # Ignorer un statut invalide
            pass
    # Pagination
    per_page = 10
    total = query.count()
    total_pages = (total + per_page - 1) // per_page
    demandes = query.order_by(desc(DemandeClient.date_creation)).offset((page - 1) * per_page).limit(per_page).all()
    return templates.TemplateResponse(
        "etudiant/liste_demandes.html",
        {
            "request": request,
            "user": user,
            "demandes": demandes,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "status_filter": status,
            "now": datetime.now()
        }
    )

@router.get("/etudiant/demandes/nouvelle", response_class=HTMLResponse)
async def afficher_formulaire_nouvelle_demande(
    request: Request,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_role(user_id, "user", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé aux étudiants")
    user = db.query(User).filter(User.id == user_id).first()
    return templates.TemplateResponse(
        "etudiant/nouvelle_demande.html",
        {
            "request": request,
            "user": user,
            "now": datetime.now(),
            "service_prices": SERVICE_PRICES # Passer les prix au template si besoin
        }
    )

@router.post("/etudiant/demandes/nouvelle")
async def soumettre_demande(
    request: Request,
    # Informations sur le service
    type_service: TypeService = Form(...),
    pour_tiers: bool = Form(False),
    # Informations sur le tiers (conditionnelles)
    tiers_nom: Optional[str] = Form(None),
    tiers_prenom: Optional[str] = Form(None),
    tiers_email: Optional[str] = Form(None), # Changé de EmailStr à str pour éviter les erreurs de validation
    tiers_relation: Optional[str] = Form(None),
    # Informations générales
    commentaire: Optional[str] = Form(None),
    destination: Optional[str] = Form(None),
    # Informations sur le document
    type_document: TypeDocument = Form(...),
    intitule: str = Form(...),
    annee_obtention: Optional[str] = Form(None),
    institution: Optional[str] = Form(None),
    nombre_copies: int = Form(1),
    fichier: UploadFile = File(...),
    # Informations de paiement
    methode_paiement: MethodePaiement = Form(...),
    montant_total: float = Form(...),
    telephone_paiement: Optional[str] = Form(None),
    # Utilisateur connecté
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_role(user_id, "user", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé aux clients")
    try:
        # Validation des données
        await valider_donnees_demande(
            type_service, pour_tiers, tiers_nom, tiers_prenom,
            tiers_email, tiers_relation, fichier, methode_paiement,
            telephone_paiement, montant_total, nombre_copies
        )
        # Calculer le prix réel et vérifier avec le montant soumis
        prix_calcule = calculer_prix_demande(type_service, nombre_copies, SERVICE_PRICES)
        if abs(prix_calcule - montant_total) > 1: # Tolérance d'1 FCFA
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le montant calculé ne correspond pas au montant soumis"
            )
        # Créer la demande avec toutes les nouvelles informations
        reference = generer_reference_unique(db)
        nouvelle_demande = DemandeClient(
            reference=reference,
            client_id=user_id,
            type_service=type_service,
            pour_tiers=pour_tiers,
            tiers_nom=tiers_nom,
            tiers_prenom=tiers_prenom,
            tiers_email=tiers_email,
            tiers_relation=tiers_relation,
            commentaire=commentaire,
            destination=destination,
            montant_total=montant_total,
            methode_paiement=methode_paiement,
            statut_paiement=StatutPaiement.EN_ATTENTE,
            statut=StatutDemande.PAIEMENT_EN_ATTENTE
        )
        db.add(nouvelle_demande)
        db.commit()
        db.refresh(nouvelle_demande)
        # Ajouter le document avec les nouvelles informations
        document = DocumentDemande(
            demande_id=nouvelle_demande.id,
            type_document=type_document,
            intitule=intitule,
            nombre_copies=nombre_copies,
            prix_unitaire=SERVICE_PRICES[type_service],
            annee_obtention=annee_obtention,
            institution=institution
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        # === Gérer l'upload du fichier avec sécurité (fonction async) ===
        # Ancien: fichier_path = await sauvegarder_fichier_securise(fichier, user_id, nouvelle_demande.id)
        # Nouveau: Utiliser la fonction importée depuis le module optimisé
        fichier_path = await sauvegarder_fichier_securise(fichier, user_id, nouvelle_demande.id)
        # =============================================================
        # Ajouter le fichier à la base de données
        fichier_document = FichierDocument(
            demande_id=nouvelle_demande.id,
            document_id=document.id,
            nom_fichier=fichier.filename,
            chemin_fichier=fichier_path,
            type_fichier=fichier.content_type,
            taille=fichier.size if hasattr(fichier, 'size') else os.path.getsize(fichier_path)
        )
        db.add(fichier_document)
        # Créer l'historique de la demande
        historique = HistoriqueDemande(
            demande_id=nouvelle_demande.id,
            statut_precedent=None,
            statut_nouveau=StatutDemande.PAIEMENT_EN_ATTENTE.value,
            commentaire="Demande créée, en attente de paiement",
            utilisateur_id=user_id,
            donnees_supplementaires=str({
                "type_service": type_service.value,
                "methode_paiement": methode_paiement.value,
                "montant": montant_total
            })
        )
        db.add(historique)
        db.commit()
        # Initier le processus de paiement selon la méthode choisie
        if methode_paiement in [MethodePaiement.ORANGE_MONEY, MethodePaiement.MOBILE_MONEY,
                               MethodePaiement.VISA, MethodePaiement.PAYPAL]:
            # Rediriger vers la page de paiement
            return RedirectResponse(
                url=f"/etudiant/demandes/{nouvelle_demande.id}/paiement",
                status_code=303
            )
        else:
            # Pour virement, passer directement à l'attente de documents
            nouvelle_demande.statut = StatutDemande.DOCUMENTS_EN_ATTENTE
            db.commit()
            return RedirectResponse(
                url=f"/etudiant/demandes/{nouvelle_demande.id}/virement",
                status_code=303
            )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création de la demande: {str(e)}"
        )

@router.get("/etudiant/demandes/{demande_id}/paiement", response_class=HTMLResponse)
async def afficher_page_paiement(
    request: Request,
    demande_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Affiche la page de paiement pour une demande"""
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.client_id == user_id
    ).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvée")
    if demande.statut != StatutDemande.PAIEMENT_EN_ATTENTE:
        return RedirectResponse(url="/etudiant/demandes", status_code=303)
    return templates.TemplateResponse(
        "etudiant/paiement.html",
        {
            "request": request,
            "demande": demande,
            "user": db.query(User).filter(User.id == user_id).first()
        }
    )

@router.get("/etudiant/demandes/{demande_id}/virement", response_class=HTMLResponse)
async def afficher_instructions_virement(
    request: Request,
    demande_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Affiche les instructions pour le virement bancaire"""
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.client_id == user_id
    ).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvée")
    return templates.TemplateResponse(
        "etudiant/instructions_virement.html",
        {
            "request": request,
            "demande": demande,
            "user": db.query(User).filter(User.id == user_id).first()
        }
    )

# Routes pour l'administration
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
            "now": datetime.now()
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
    demande.documents # Charge les documents associés
    demande.fichiers # Charge les fichiers associés
    demande.historique # Charge l'historique
    return templates.TemplateResponse(
        "admin_demande_detail.html", # Vérifiez le nom exact du template
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
    return mettre_a_jour_statut_demande(db, demande_id, status_update, current_user_id)

# Routes pour le service COURIEL (réception et traitement)
@router.get("/couriel/dashboard")
async def couriel_dashboard(request: Request, user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé au service courrier")
    user = db.query(User).filter(User.id == user_id).first()
    # Récupérer les statistiques des demandes
    stats = {
        "total_demandes": db.query(DemandeClient).count(),
        "nouvelles": db.query(DemandeClient).filter(DemandeClient.statut == StatutDemande.SOUMISE).count(),
        "en_traitement": db.query(DemandeClient).filter(DemandeClient.statut == StatutDemande.EN_TRAITEMENT).count(),
        "traitees": db.query(DemandeClient).filter(DemandeClient.statut == StatutDemande.COMPLETEE).count(), # Vérifiez l'orthographe COMPLETEE/COMPLETE
    }
    # Récupérer les demandes récentes à traiter
    nouvelles_demandes = db.query(DemandeClient).filter(
        DemandeClient.statut == StatutDemande.SOUMISE
    ).order_by(desc(DemandeClient.date_creation)).limit(5).all()
    # Récupérer les demandes en cours de traitement
    demandes_en_traitement = db.query(DemandeClient).filter(
        DemandeClient.statut == StatutDemande.EN_TRAITEMENT
    ).order_by(desc(DemandeClient.date_creation)).limit(5).all()
    # Récupérer les activités récentes
    activites = []
    # Exemple d'activités récentes (à remplacer par des données réelles)
    activites = [
        {
            "type": "reception",
            "titre": "Demande réceptionnée",
            "description": "Demande d'authentification REF-12345 réceptionnée",
            "date": datetime.now() - timedelta(hours=2),
            "utilisateur": "Jean Dupont"
        },
        {
            "type": "traitement",
            "titre": "Traitement commencé",
            "description": "Traitement de la demande REF-23456 démarré",
            "date": datetime.now() - timedelta(hours=4),
            "utilisateur": "Marie Martin"
        },
        {
            "type": "reponse",
            "titre": "Réponse envoyée",
            "description": "Authentification complétée pour REF-34567",
            "date": datetime.now() - timedelta(hours=6),
            "utilisateur": "Paul Durand"
        }
    ]
    return templates.TemplateResponse(
        "couriel/dashboard.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
            "nouvelles_demandes": nouvelles_demandes,
            "demandes_en_traitement": demandes_en_traitement,
            "activites": activites,
            "now": datetime.now()
        }
    )

@router.get("/couriel/demandes")
async def liste_demandes_couriel(
    request: Request,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    statut: Optional[str] = None,
    service: Optional[str] = None,
    date_debut: Optional[str] = None,
    date_fin: Optional[str] = None,
    page: int = 1
):
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé au service courrier")
    user = db.query(User).filter(User.id == user_id).first()
    # Construire la requête de base
    query = db.query(DemandeClient)
    # Appliquer les filtres
    if statut:
        try:
            statut_enum = StatutDemande(statut)
            query = query.filter(DemandeClient.statut == statut_enum)
        except ValueError:
            pass
    if service:
        try:
            service_enum = TypeService(service)
            query = query.filter(DemandeClient.type_service == service_enum)
        except ValueError:
            pass
    if date_debut:
        try:
            date_debut_obj = datetime.strptime(date_debut, "%Y-%m-%d")
            query = query.filter(DemandeClient.date_creation >= date_debut_obj)
        except ValueError:
            pass
    if date_fin:
        try:
            date_fin_obj = datetime.strptime(date_fin, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(DemandeClient.date_creation < date_fin_obj)
        except ValueError:
            pass
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
            "service_filter": service,
            "date_debut": date_debut,
            "date_fin": date_fin,
            "now": datetime.now()
        }
    )

@router.get("/couriel/demandes/{demande_id}")
async def details_demande_couriel(
    request: Request,
    demande_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé au service courrier")
    # Récupérer la demande
    demande = db.query(DemandeClient).filter(DemandeClient.id == demande_id).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvée")
    # Récupérer l'historique
    historique = db.query(HistoriqueDemande).filter(
        HistoriqueDemande.demande_id == demande_id
    ).order_by(HistoriqueDemande.date_action.desc()).all()
    # Récupérer les traitements et réponses
    traitements = db.query(TraitementDemande).filter(
        TraitementDemande.demande_id == demande_id
    ).order_by(TraitementDemande.date_debut.desc()).all()
    reponses = db.query(ReponseDemande).filter(
        ReponseDemande.demande_id == demande_id
    ).order_by(ReponseDemande.date_creation.desc()).all()
    user = db.query(User).filter(User.id == user_id).first()
    return templates.TemplateResponse(
        "couriel/details_demande.html",
        {
            "request": request,
            "user": user,
            "demande": demande,
            "historique": historique,
            "traitements": traitements,
            "reponses": reponses,
            "now": datetime.now()
        }
    )

# Réceptionner une demande
@router.get("/couriel/demandes/{demande_id}/reception")
async def reception_demande_form(
    request: Request,
    demande_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé au service courrier")
    # Vérifier que la demande existe et est en statut SOUMISE
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.statut == StatutDemande.SOUMISE
    ).first()
    if not demande:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande non trouvée ou ne peut pas être réceptionnée"
        )
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

# === Route mise à jour pour utiliser les fonctions du nouveau file_utils_optimise ===
@router.post("/couriel/demandes/{demande_id}/upload-document")
async def upload_document_traite(
    demande_id: int,
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    demande = db.query(DemandeClient).get(demande_id)
    if not demande:
        raise HTTPException(status_code=404, detail="Demande introuvable")

    # Créer un code de vérification unique
    code_verification = f"VERIF-{uuid.uuid4().hex[:8].upper()}"
    demande.code_verification = code_verification

    # Sauvegarder le fichier original
    # Utiliser la fonction `creer_dossier_demande` de file_utils_optimise
    dossier_demande = creer_dossier_demande(demande_id) # Cette fonction crée le dossier ET le retourne
    original_filename = f"document_original_{demande_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    original_path = os.path.join(dossier_demande, original_filename)

    # Sauvegarder le fichier uploadé
    # Utiliser aiofiles ou shutil.copyfileobj
    with open(original_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer) # ou await file.read() et write() si vous préférez

    # === Utiliser la fonction `securiser_document` de file_utils_optimise ===
    secure_filename = f"document_securise_{demande_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    secure_path = os.path.join(dossier_demande, secure_filename)
    # Appel de la fonction importée depuis utils.file_utils_optimise
    try:
        # Passer les arguments nécessaires. Ajustez selon la signature exacte de votre fonction.
        # Exemple basé sur le fichier fourni et l'utilisation antérieure:
        processor = PDFSecurityProcessor()
        success = asyncio.run(processor.secure_document(
            chemin_original=original_path,
            chemin_sortie=secure_path,
            code_verification=code_verification,
            qr_code=True, # Options par défaut, ajustez si nécessaire
            filigrane=True, # Options par défaut, ajustez si nécessaire
            signature_numerique=True # Options par défaut (watermark), ajustez si nécessaire
            # Vous pouvez avoir d'autres arguments comme 'niveau_securite'

        ))
        if success:
                print(f"✅ Succès ! Fichier sauvegardé ici : {secure_path}")
                print(f"✅ Succès ! Fichier sauvegardé ici : {secure_path}")
        else:
                raise Exception("Le processus de sécurisation a échoué.")
                

    except Exception as e:
        # Gérer l'erreur de sécurisation
        print(f"Erreur lors de la sécurisation du document: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la sécurisation du document: {str(e)}")
    # =============================================================

    # Mettre à jour la réponse
    reponse = ReponseDemande(
        demande_id=demande_id,
        type_reponse=TypeReponse.DOCUMENT_TRAITE,
        contenu=f"Document traité et sécurisé - {secure_filename}",
        chemin_fichier_securise=secure_path
    )
    db.add(reponse)
    # Mettre à jour le statut de la demande
    demande.statut = StatutDemande.COMPLETEE # Vérifiez l'orthographe COMPLETEE/COMPLETE
    demande.date_reponse = datetime.now()
    db.commit()
    # Envoyer la notification
    try:
        envoyer_notification_reponse(demande, reponse)
    except Exception as e:
        # Log l'erreur mais ne bloque pas la réponse
        print(f"Erreur lors de l'envoi de la notification: {e}")
    return RedirectResponse(
        url=f"/couriel/demandes/{demande_id}/confirmation",
        status_code=303
    )
# ================================================================

@router.post("/couriel/demandes/{demande_id}/reception")
async def receptionner_demande(
    demande_id: int,
    notes: str = Form(""),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé au service courrier")
    # Vérifier que la demande existe et est en statut SOUMISE
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.statut == StatutDemande.SOUMISE
    ).first()
    if not demande:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande non trouvée ou ne peut pas être réceptionnée"
        )
    # Mettre à jour le statut de la demande
    statut_precedent = demande.statut
    demande.statut = StatutDemande.RECU
    demande.date_reception = datetime.now()
    db.commit()
    # Ajouter un événement dans l'historique
    historique = HistoriqueDemande(
        demande_id=demande.id,
        statut_precedent=statut_precedent.value,
        statut_nouveau=StatutDemande.RECU.value,
        commentaire=f"Demande réceptionnée par le service COURIEL. {notes}",
        utilisateur_id=user_id
    )
    db.add(historique)
    db.commit()
    # Notifier l'étudiant
    # (fonction à implémenter pour envoyer un email)
    return RedirectResponse(
        url=f"/couriel/demandes/{demande_id}",
        status_code=303
    )

# Traitement d'une demande
@router.get("/couriel/demandes/{demande_id}/traitement")
async def traitement_demande_form(
    request: Request,
    demande_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé au service courrier")
    # Vérifier que la demande existe et est en statut RECU
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.statut.in_([StatutDemande.RECU, StatutDemande.EN_TRAITEMENT])
    ).first()
    if not demande:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande non trouvée ou ne peut pas être traitée"
        )
    user = db.query(User).filter(User.id == user_id).first()
    # Récupérer le traitement en cours s'il existe
    traitement = db.query(TraitementDemande).filter(
        TraitementDemande.demande_id == demande_id,
        TraitementDemande.date_fin == None
    ).first()
    # Récupérer les documents de la demande
    documents = db.query(DocumentDemande).filter(
        DocumentDemande.demande_id == demande_id
    ).all()
    # Récupérer les fichiers
    fichiers = db.query(FichierDocument).filter(
        FichierDocument.demande_id == demande_id
    ).all()
    return templates.TemplateResponse(
        "couriel/traitement_demande.html",
        {
            "request": request,
            "user": user,
            "demande": demande,
            "traitement": traitement,
            "documents": documents,
            "fichiers": fichiers,
            "now": datetime.now()
        }
    )

@router.post("/couriel/demandes/{demande_id}/traitement/commencer")
async def commencer_traitement(
    demande_id: int,
    notes_internes: str = Form(""),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé au service courrier")
    # Vérifier que la demande existe et est en statut RECU
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.statut == StatutDemande.RECU
    ).first()
    if not demande:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande non trouvée ou ne peut pas être traitée"
        )
    # Vérifier qu'il n'y a pas déjà un traitement en cours
    traitement_existant = db.query(TraitementDemande).filter(
        TraitementDemande.demande_id == demande_id,
        TraitementDemande.date_fin == None
    ).first()
    if traitement_existant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un traitement est déjà en cours pour cette demande"
        )
    # Créer un nouveau traitement
    nouveau_traitement = TraitementDemande(
        demande_id=demande_id,
        agent_couriel_id=user_id,
        notes_internes=notes_internes,
        verification_effectuee=False
    )
    db.add(nouveau_traitement)
    # Mettre à jour le statut de la demande
    statut_precedent = demande.statut
    demande.statut = StatutDemande.EN_TRAITEMENT
    demande.date_traitement = datetime.now()
    db.commit()
    # Ajouter un événement dans l'historique
    historique = HistoriqueDemande(
        demande_id=demande.id,
        statut_precedent=statut_precedent.value,
        statut_nouveau=StatutDemande.EN_TRAITEMENT.value,
        commentaire=f"Début du traitement par le service COURIEL.",
        utilisateur_id=user_id
    )
    db.add(historique)
    db.commit()
    return RedirectResponse(
        url=f"/couriel/demandes/{demande_id}/traitement",
        status_code=303
    )

@router.post("/couriel/demandes/{demande_id}/traitement/verification")
async def verifier_documents(
    demande_id: int,
    traitement_id: int = Form(...),
    resultat_verification: bool = Form(...),
    details_verification: str = Form(""),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé au service courrier")
    # Vérifier que le traitement existe et appartient à la demande
    traitement = db.query(TraitementDemande).filter(
        TraitementDemande.id == traitement_id,
        TraitementDemande.demande_id == demande_id,
        TraitementDemande.date_fin == None
    ).first()
    if not traitement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Traitement non trouvé ou terminé"
        )
    # Mettre à jour le traitement
    traitement.verification_effectuee = True
    traitement.resultat_verification = resultat_verification
    traitement.details_verification = details_verification
    db.commit()
    # Marquer les fichiers comme vérifiés
    fichiers = db.query(FichierDocument).filter(
        FichierDocument.demande_id == demande_id,
        FichierDocument.est_original == True
    ).all()
    for fichier in fichiers:
        fichier.est_verifie = True
    db.commit()
    # Ajouter un événement dans l'historique
    historique = HistoriqueDemande(
        demande_id=demande_id,
        statut_precedent=StatutDemande.EN_TRAITEMENT.value,
        statut_nouveau=StatutDemande.EN_TRAITEMENT.value,
        commentaire=f"Vérification des documents {'réussie' if resultat_verification else 'échouée'}. {details_verification}",
        utilisateur_id=user_id
    )
    db.add(historique)
    db.commit()
    return RedirectResponse(
        url=f"/couriel/demandes/{demande_id}/traitement",
        status_code=303
    )

# Génération de la réponse
@router.get("/couriel/demandes/{demande_id}/reponse")
async def reponse_demande_form(
    request: Request,
    demande_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé au service courrier")
    # Vérifier que la demande existe et est en traitement
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.statut == StatutDemande.EN_TRAITEMENT
    ).first()
    if not demande:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande non trouvée ou ne peut pas recevoir de réponse"
        )
    user = db.query(User).filter(User.id == user_id).first()
    # Vérifier qu'il y a un traitement en cours
    traitement = db.query(TraitementDemande).filter(
        TraitementDemande.demande_id == demande_id,
        TraitementDemande.date_fin == None
    ).first()
    if not traitement or not traitement.verification_effectuee:
        return RedirectResponse(
            url=f"/couriel/demandes/{demande_id}/traitement",
            status_code=303
        )
    return templates.TemplateResponse(
        "couriel/reponse_demande.html",
        {
            "request": request,
            "user": user,
            "demande": demande,
            "traitement": traitement,
            "now": datetime.now()
        }
    )

@router.post("/couriel/demandes/{demande_id}/reponse")
async def soumettre_reponse(
    demande_id: int,
    traitement_id: int = Form(...),
    type_reponse: TypeReponse = Form(...),
    contenu: str = Form(...),
    niveau_securite: NiveauSecurite = Form(NiveauSecurite.STANDARD),
    qr_code: bool = Form(True),
    filigrane: bool = Form(True),
    signature_numerique: bool = Form(True),
    commentaire_public: str = Form(""),
    commentaire_interne: str = Form(""),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé au service courrier")
    # Vérifier que la demande existe et est en traitement
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.statut == StatutDemande.EN_TRAITEMENT
    ).first()
    if not demande:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande non trouvée ou ne peut pas recevoir de réponse"
        )
    # Vérifier que le traitement existe et est en cours
    traitement = db.query(TraitementDemande).filter(
        TraitementDemande.id == traitement_id,
        TraitementDemande.demande_id == demande_id,
        TraitementDemande.date_fin == None
    ).first()
    if not traitement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Traitement non trouvé ou terminé"
        )
    # Créer un code de vérification unique pour le QR code
    code_verification = f"VERIF-{uuid.uuid4().hex[:12].upper()}"
    demande.code_verification = code_verification
    # Créer la réponse
    reponse = ReponseDemande(
        demande_id=demande_id,
        type_reponse=type_reponse,
        contenu=contenu,
        niveau_securite=niveau_securite,
        qr_code=qr_code,
        filigrane=filigrane,
        signature_numerique=signature_numerique,
        commentaire_public=commentaire_public,
        commentaire_interne=commentaire_interne
    )
    db.add(reponse)
    db.commit()
    db.refresh(reponse)
    # Générer le document sécurisé
    # === Utiliser la fonction `securiser_document` de file_utils_optimise ici aussi ===
    # (Exemple simplifié, vous pouvez vouloir un processus plus complexe)
    # Supposons que le document à sécuriser est un fichier temporaire uploadé ou généré
    # Pour cet exemple, je simule l'utilisation. Adaptez selon votre logique exacte.
    # fichier_securise = document_securise(demande, reponse, code_verification)
    # reponse.chemin_fichier_securise = fichier_securise
    # =============================================================
    # Terminer le traitement
    traitement.date_fin = datetime.now()
    # Mettre à jour le statut de la demande
    statut_precedent = demande.statut
    demande.statut = StatutDemande.COMPLETEE # Vérifiez l'orthographe COMPLETEE/COMPLETE
    demande.date_reponse = datetime.now()
    db.commit()
    # Ajouter un événement dans l'historique
    historique = HistoriqueDemande(
        demande_id=demande.id,
        statut_precedent=statut_precedent.value,
        statut_nouveau=StatutDemande.COMPLETEE.value, # Vérifiez l'orthographe
        commentaire=f"Réponse de type '{type_reponse.value}' créée par le service COURIEL.",
        utilisateur_id=user_id
    )
    db.add(historique)
    db.commit()
    # Notifier l'étudiant/partenaire par email
    try:
        envoyer_notification_reponse(demande, reponse)
    except Exception as e:
        # Log l'erreur mais ne bloque pas la réponse
        print(f"Erreur lors de l'envoi de la notification: {e}")
    return RedirectResponse(
        url=f"/couriel/demandes/{demande_id}/confirmation",
        status_code=303
    )

@router.get("/couriel/demandes/{demande_id}/confirmation")
async def confirmation_reponse(
    request: Request,
    demande_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_role(user_id, "COURIEL", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé au service courrier")
    # Vérifier que la demande existe et est complétée
    demande = db.query(DemandeClient).filter(
        DemandeClient.id == demande_id,
        DemandeClient.statut == StatutDemande.COMPLETEE # Vérifiez l'orthographe
    ).first()
    if not demande:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande non trouvée ou non complétée"
        )
    user = db.query(User).filter(User.id == user_id).first()
    # Récupérer la dernière réponse
    reponse = db.query(ReponseDemande).filter(
        ReponseDemande.demande_id == demande_id
    ).order_by(ReponseDemande.date_creation.desc()).first()
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

# Page de vérification publique des documents (accessible sans authentification)
@router.get("/verification/{code}")
async def verifier_document(
    request: Request,
    code: str,
    db: Session = Depends(get_db)
):
    """Vérification publique d'un document"""
    demande = db.query(DemandeClient)\
               .filter(DemandeClient.code_verification == code)\
               .first()
    if not demande:
        return templates.TemplateResponse(
            "verification_echec.html", # Vérifiez le nom exact du template
            {"request": request}
        )
    reponse = db.query(ReponseDemande)\
               .filter(ReponseDemande.demande_id == demande.id)\
               .order_by(ReponseDemande.date_creation.desc())\
               .first()
    return templates.TemplateResponse(
        "verification_succes.html", # Vérifiez le nom exact du template
        {
            "request": request,
            "demande": demande,
            "reponse": reponse,
            "date_verification": datetime.now()
        }
    )


 
