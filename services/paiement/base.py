# services/paiement/base.py
"""Interface de base pour les passerelles de paiement."""
from abc import ABC, abstractmethod
from typing import Dict, Any
from models import DemandeClient, MethodePaiement

class PasserellePaiement(ABC):
    """Interface abstraite pour une passerelle de paiement."""
    
    @abstractmethod
    def __init__(self, config: Dict[str, Any]):
        """Initialise la passerelle avec sa configuration."""
        pass
    
    @abstractmethod
    def creer_transaction(self, demande: DemandeClient, url_retour_succes: str, url_retour_echec: str) -> Dict[str, Any]:
        """
        Cree une transaction chez la passerelle de paiement.
        Retourne un dictionnaire avec les details necessaires (URL de redirection, ID de transaction, etc.).
        """
        pass
    
    @abstractmethod
    def verifier_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verifie le statut d'une transaction e partir des donnees fournies 
        (generalement via un webhook ou un retour utilisateur).
        Retourne un dictionnaire avec le statut verifie et les details.
        """
        pass

    @abstractmethod
    def nom(self) -> str:
        """Retourne le nom de la passerelle."""
        pass
