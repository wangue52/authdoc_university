# services/paiement/passerelles.py
"""Implementations concretes des passerelles de paiement."""
import uuid
from typing import Dict, Any
from models import DemandeClient, MethodePaiement
from services.paiement.base import PasserellePaiement
import random # Pour la simulation

# Configuration simulee - e remplacer par de vraies configurations
CONFIG_PASSERELLES = {
    "VISA": {
        "api_key": "sim_visa_key_12345",
        "endpoint": "https://api.visa-sim.com/pay"
    },
    "PAYPAL": {
        "client_id": "sim_paypal_client_id",
        "secret": "sim_paypal_secret",
        "endpoint": "https://api.sandbox.paypal.com/v1/payments/payment"
    },
    "ORANGE_MONEY": {
        "merchant_key": "sim_orange_key",
        "endpoint": "https://api.orange.com/payment/v1/webpayment"
    },
    "MOBILE_MONEY": {
        "operator_id": "sim_operator_id",
        "endpoint": "https://api.mobilemoney.com/charge"
    }
}

class PasserelleVisa(PasserellePaiement):
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("VISA", {})
        self.nom_passerelle = "VISA"
        
    def creer_transaction(self, demande: DemandeClient, url_retour_succes: str, url_retour_echec: str) -> Dict[str, Any]:
        # Simulation de la creation d'une transaction
        transaction_id = f"visa_txn_{uuid.uuid4().hex[:12]}"
        # Dans une vraie implementation, vous feriez un appel API ici
        # et obtiendriez une URL de redirection
        url_redirection = f"{self.config.get('endpoint')}?txn_id={transaction_id}&amount={demande.montant_total}"
        return {
            "transaction_id": transaction_id,
            "url_redirection": url_redirection,
            "passerelle": self.nom_passerelle
        }
        
    def verifier_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        # Simulation de la verification
        # Dans une vraie implementation, vous feriez un appel API pour verifier le statut
        # Ici, nous simulons un succes la plupart du temps
        statut = "SUCCES" if random.random() > 0.1 else "ECHEC" # 90% de succes
        return {
            "statut": statut,
            "transaction_id": transaction_data.get("transaction_id"),
            "details": f"Transaction verifiee via {self.nom_passerelle}"
        }
        
    def nom(self) -> str:
        return self.nom_passerelle

class PasserellePayPal(PasserellePaiement):
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("PAYPAL", {})
        self.nom_passerelle = "PAYPAL"
        
    def creer_transaction(self, demande: DemandeClient, url_retour_succes: str, url_retour_echec: str) -> Dict[str, Any]:
        transaction_id = f"paypal_txn_{uuid.uuid4().hex[:12]}"
        url_redirection = f"{self.config.get('endpoint')}?paymentId={transaction_id}&amount={demande.montant_total}"
        return {
            "transaction_id": transaction_id,
            "url_redirection": url_redirection,
            "passerelle": self.nom_passerelle
        }
        
    def verifier_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        statut = "SUCCES" if random.random() > 0.15 else "ECHEC" # 85% de succes
        return {
            "statut": statut,
            "transaction_id": transaction_data.get("transaction_id"),
            "details": f"Transaction verifiee via {self.nom_passerelle}"
        }
        
    def nom(self) -> str:
        return self.nom_passerelle

class PasserelleOrangeMoney(PasserellePaiement):
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("ORANGE_MONEY", {})
        self.nom_passerelle = "ORANGE_MONEY"
        
    def creer_transaction(self, demande: DemandeClient, url_retour_succes: str, url_retour_echec: str) -> Dict[str, Any]:
        transaction_id = f"om_txn_{uuid.uuid4().hex[:12]}"
        # Pour Orange Money, le numero de telephone est souvent necessaire
        numero_telephone = getattr(demande, 'telephone_paiement', '')
        url_redirection = f"{self.config.get('endpoint')}?token={transaction_id}&tel={numero_telephone}&montant={demande.montant_total}"
        return {
            "transaction_id": transaction_id,
            "url_redirection": url_redirection,
            "passerelle": self.nom_passerelle
        }
        
    def verifier_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        statut = "SUCCES" if random.random() > 0.05 else "ECHEC" # 95% de succes
        return {
            "statut": statut,
            "transaction_id": transaction_data.get("transaction_id"),
            "details": f"Transaction verifiee via {self.nom_passerelle}"
        }
        
    def nom(self) -> str:
        return self.nom_passerelle

class PasserelleMobileMoney(PasserellePaiement):
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("MOBILE_MONEY", {})
        self.nom_passerelle = "MOBILE_MONEY"
        
    def creer_transaction(self, demande: DemandeClient, url_retour_succes: str, url_retour_echec: str) -> Dict[str, Any]:
        transaction_id = f"mm_txn_{uuid.uuid4().hex[:12]}"
        numero_telephone = getattr(demande, 'telephone_paiement', '')
        url_redirection = f"{self.config.get('endpoint')}?ref={transaction_id}&msisdn={numero_telephone}&amount={demande.montant_total}"
        return {
            "transaction_id": transaction_id,
            "url_redirection": url_redirection,
            "passerelle": self.nom_passerelle
        }
        
    def verifier_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        statut = "SUCCES" if random.random() > 0.1 else "ECHEC" # 90% de succes
        return {
            "statut": statut,
            "transaction_id": transaction_data.get("transaction_id"),
            "details": f"Transaction verifiee via {self.nom_passerelle}"
        }
        
    def nom(self) -> str:
        return self.nom_passerelle

# Fabrique pour obtenir la bonne passerelle
def obtenir_passerelle(methode_paiement: MethodePaiement, config: Dict[str, Any]) -> PasserellePaiement:
    """Fabrique pour obtenir une instance de passerelle de paiement."""
    passerelles = {
        MethodePaiement.VISA: PasserelleVisa,
        MethodePaiement.PAYPAL: PasserellePayPal,
        MethodePaiement.ORANGE_MONEY: PasserelleOrangeMoney,
        MethodePaiement.MOBILE_MONEY: PasserelleMobileMoney,
    }
    
    passerelle_classe = passerelles.get(methode_paiement)
    if not passerelle_classe:
        raise ValueError(f"Passerelle non supportee pour la methode {methode_paiement}")
        
    return passerelle_classe(config)
