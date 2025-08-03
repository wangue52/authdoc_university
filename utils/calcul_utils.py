# utils/calcul_utils.py
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from models import DemandeClient, TypeService

# Deplacer SERVICE_PRICES ici si necessaire, ou le garder dans models.py
# Pour l'instant, on suppose qu'il est defini dans models.py ou un autre fichier de configuration
# Si on le deplace ici :
# SERVICE_PRICES = {
#     TypeService.AUTHENTIFICATION: 5000,
#     TypeService.DUPLICATA: 10000,
#     TypeService.LEGALISATION: 3000,
#     TypeService.TRADUCTION: 15000,
#     TypeService.TRANSMISSION_PARTENAIRE: 7500
# }

def calculer_prix_demande(type_service: TypeService, nombre_copies: int, service_prices: dict) -> float:
    """Calcule le prix total d'une demande"""
    prix_base = service_prices.get(type_service, 0)
    copies_supplementaires = nombre_copies - 1
    prix_copies = copies_supplementaires * (prix_base * 0.5)
    return prix_base + prix_copies

def generer_reference_unique(db: Session) -> str:
    """Genere une reference unique pour la demande"""
    while True:
        reference = f"REF-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        if not db.query(DemandeClient).filter(DemandeClient.reference == reference).first():
            return reference

# Si SERVICE_PRICES est deplace ici, exporter aussi
# __all__ = ['calculer_prix_demande', 'generer_reference_unique', 'SERVICE_PRICES']
 
