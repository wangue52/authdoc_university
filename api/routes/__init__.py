# api/routes/__init__.py
# Importation de tous les routeurs pour un accès simplifié
from . import (
    auth_routes,
    user_routes,
    demande_routes,
    role_routes,
    permission_routes,
    taux_change_routes,
    partenaire_routes,
    # Ajoutez ici les autres routeurs
)

# Optionnel: définir __all__ pour expliciter ce qui est exporté
__all__ = [
    "auth_routes",
    "user_routes",
    "demande_routes",
    "role_routes",
    "permission_routes",
    "taux_change_routes",
    "partenaire_routes",
    # Ajoutez ici les autres routeurs
]
 
