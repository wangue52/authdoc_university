# api/routes/taux_change_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import TauxChange, Devise
from auth import get_current_user, has_role
from forex_python.converter import CurrencyRates
from datetime import datetime

router = APIRouter(prefix="/api", tags=["taux de change"])

DEVISE_PAR_DEFAUT = Devise.XAF
DEVISES_ACCEPTEES = [Devise.XAF, Devise.EUR, Devise.USD]

@router.get("/taux-change", response_model=List[dict])
async def get_taux_change(db: Session = Depends(get_db)):
    """Recupere les taux de change actuels"""
    taux = db.query(TauxChange).filter(TauxChange.actif == True).all()
    return [{
        "source": t.devise_source.value,
        "cible": t.devise_cible.value,
        "taux": t.taux,
        "date_maj": t.date_maj
    } for t in taux]

@router.post("/update-taux-change")
async def update_taux_change(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user)
):
    """Met e jour les taux de change depuis une API externe"""
    if not has_role(user_id, "admin", db):
        raise HTTPException(status_code=403, detail="Acces refuse")
    try:
        c = CurrencyRates()
        for devise in DEVISES_ACCEPTEES:
            if devise != DEVISE_PAR_DEFAUT:
                taux = c.get_rate(devise.value, DEVISE_PAR_DEFAUT.value)
                # Desactiver les anciens taux
                db.query(TauxChange).filter(
                    TauxChange.devise_source == devise,
                    TauxChange.devise_cible == DEVISE_PAR_DEFAUT
                ).update({"actif": False})
                # Ajouter le nouveau taux
                nouveau_taux = TauxChange(
                    devise_source=devise,
                    devise_cible=DEVISE_PAR_DEFAUT,
                    taux=taux,
                    date_maj=datetime.utcnow()
                )
                db.add(nouveau_taux)
        db.commit()
        return {"message": "Taux de change mis e jour avec succes"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Erreur de mise e jour: {str(e)}")
 
