# enums.py
from enum import Enum

class StatutTransaction(str, Enum):
    INITIE = "INITIE"
    EN_ATTENTE = "EN_ATTENTE"
    SUCCES = "SUCCES"
    ECHEC = "ECHEC"
    ANNULE = "ANNULE"
    REMBOURSE = "REMBOURSE"
 
 
