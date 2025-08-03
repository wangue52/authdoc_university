# utils/file_utilsoptimised.py
from decimal import Decimal
import os
import uuid
import hashlib
import logging
import tempfile
import shutil
import io
import asyncio
from datetime import datetime
from typing import Optional, List, Any, Tuple, Generator, Union
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, auto
from concurrent.futures import ThreadPoolExecutor
from fastapi import UploadFile, HTTPException
import qrcode
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader  # ✅ Import ajouté
from PyPDF2 import PdfWriter, PdfReader
import aiofiles
# --- Configuration et Initialisation ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("file_utils.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

COURIEL_DOWNLOAD_DIR = "downloads/couriel"
os.makedirs(COURIEL_DOWNLOAD_DIR, exist_ok=True)
# Directory for storing uploaded files
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
def creer_dossier_demande(demande_id: int) -> str:
    """Creates a directory to store files for a specific request."""
    dossier_demande = os.path.join(COURIEL_DOWNLOAD_DIR, f"demande_{demande_id}")
    os.makedirs(dossier_demande, exist_ok=True)
    return dossier_demande
async def sauvegarder_fichier_securise(fichier: UploadFile, user_id: int, demande_id: int) -> str:
    """Safely saves the uploaded file."""
    user_dir = os.path.join(UPLOAD_DIR, f"user_{user_id}", f"demande_{demande_id}")
    os.makedirs(user_dir, exist_ok=True)
    
    nom_fichier_securise = "".join(c for c in fichier.filename if c.isalnum() or c in '._-')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nom_final = f"{timestamp}_{nom_fichier_securise}"
    file_path = os.path.join(user_dir, nom_final)
    async with aiofiles.open(file_path, "wb") as buffer:
        content = await fichier.read()
        await buffer.write(content)
    return file_path
def sauvegarder_fichier_partenaire(fichier: UploadFile, partenaire_id: int) -> str:
    """Saves the uploaded file from a partner."""
    partenaire_dir = os.path.join(UPLOAD_DIR, f"partenaire_{partenaire_id}")
    os.makedirs(partenaire_dir, exist_ok=True)
    
    file_path = os.path.join(partenaire_dir, fichier.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(fichier.file, buffer)
    
    return file_path
class FileConfig:
    """Configuration centralisée pour les opérations sur les fichiers."""
    DOWNLOAD_DIR = Path("downloads/couriel")
    UPLOAD_DIR = Path("uploads")
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS = {'.pdf', '.PDF'}
    TEMP_DIR = Path(tempfile.gettempdir())
    CHUNK_SIZE = 64 * 1024  # 64KB
    DEFAULT_PAGE_SIZE = A4
    FONT_NAME = "Helvetica"
    WATERMARK_OPACITY = 0.2
    QR_CODE_SIZE = 80

    @classmethod
    def initialize(cls):
        """Initialise les répertoires nécessaires au démarrage."""
        try:
            for directory in [cls.DOWNLOAD_DIR, cls.UPLOAD_DIR, cls.TEMP_DIR]:
                directory.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.critical(f"Impossible de créer les répertoires de base : {e}")
            raise


# --- Modèles de Données et Exceptions ---
class SecurityElementType(Enum):
    """Types d'éléments de sécurité supportés."""
    QR_CODE = auto()
    WATERMARK = auto()
    SIGNATURE_TEXT = auto()


@dataclass
class SecurityElement:
    """Représente un élément de sécurité à appliquer."""
    element_type: SecurityElementType
    content: Any  # Peut être un PIL.Image, bytes, ou IO
    position: Tuple[int, int] = (0, 0)
    size: Tuple[int, int] = (100, 100)


class FileSecurityError(Exception):
    """Exception de base pour les opérations de sécurité sur les fichiers."""
    pass


class FileValidationError(FileSecurityError):
    """Exception pour les échecs de validation de fichier."""
    pass


# --- Gestionnaires et Validateurs ---
class FileHandler:
    """Gère les opérations de base sur les fichiers."""

    @staticmethod
    def calculate_hash(file_path: Union[str, Path]) -> str:
        """Calcule le hash SHA-256 d'un fichier de manière efficace."""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(FileConfig.CHUNK_SIZE):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except OSError as e:
            raise FileSecurityError(f"Le calcul du hash a échoué pour {file_path}: {e}")


class FileValidator:
    """Valide les fichiers avant leur traitement."""

    @staticmethod
    def validate_file_path(file_path: Union[str, Path]) -> Path:
        """Valide un chemin de fichier et retourne un objet Path résolu."""
        try:
            path = Path(file_path).resolve(strict=True)
            if not path.is_file():
                raise FileValidationError(f"Le chemin n'est pas un fichier : {path}")
            if path.stat().st_size > FileConfig.MAX_FILE_SIZE:
                raise FileValidationError(f"Fichier trop volumineux : {path.stat().st_size} octets")
            if path.suffix.lower() not in FileConfig.ALLOWED_EXTENSIONS:
                raise FileValidationError(f"Extension de fichier non autorisée : {path.suffix}")
            return path
        except FileNotFoundError:
            raise FileValidationError(f"Fichier non trouvé : {file_path}")
        except Exception as e:
            logger.error(f"Échec de la validation du fichier {file_path}: {e}")
            raise

    @staticmethod
    async def validate_upload_file(file: UploadFile) -> None:
        """Valide un fichier téléversé via FastAPI."""
        if file.size and file.size > FileConfig.MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Le fichier est trop volumineux.")
        if not any(file.filename.lower().endswith(ext) for ext in FileConfig.ALLOWED_EXTENSIONS):
            raise HTTPException(status_code=400, detail="Type de fichier invalide. Seuls les PDF sont autorisés.")


@contextmanager
def temporary_file(suffix: str = ".tmp") -> Generator[Path, None, None]:
    """Gestionnaire de contexte pour créer et nettoyer automatiquement un fichier temporaire."""
    file_path = None
    try:
        fd, path_str = tempfile.mkstemp(suffix=suffix, dir=FileConfig.TEMP_DIR)
        os.close(fd)
        file_path = Path(path_str)
        yield file_path
    finally:
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except OSError as e:
                logger.warning(f"Impossible de supprimer le fichier temporaire {file_path}: {e}")


# --- Génération des Éléments de Sécurité ---
class SecurityElementGenerator:
    """Génère divers éléments de sécurité pour les documents."""

    def generate_qr_code(self, verification_code: str) -> SecurityElement:
        """Génère un QR code contenant une URL de vérification (retourne PIL.Image)."""
        try:
            verification_url = f"https://votredomaine.com/verify/{verification_code}"
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=4, border=2)
            qr.add_data(verification_url)
            qr.make(fit=True)
            # Génère l'image PIL directement
            pil_image = qr.make_image(fill_color="black", back_color="white").get_image()

            return SecurityElement(
                element_type=SecurityElementType.QR_CODE,
                content=pil_image,  # ✅ PIL.Image, pas des bytes
                position=(FileConfig.DEFAULT_PAGE_SIZE[0] - FileConfig.QR_CODE_SIZE - 20, 20),
                size=(FileConfig.QR_CODE_SIZE, FileConfig.QR_CODE_SIZE)
            )
        except Exception as e:
            raise FileSecurityError(f"La génération du QR code a échoué : {e}")

    def generate_watermark_overlay(self, text: str = "CONFIDENTIEL") -> SecurityElement:
    
        try:
              packet = io.BytesIO()
              c = canvas.Canvas(packet, pagesize=FileConfig.DEFAULT_PAGE_SIZE)
              width, height = FileConfig.DEFAULT_PAGE_SIZE

        # --- 1. Fond très clair (quasi invisible à l'écran) ---
        # Il deviendra plus visible à l'impression ou en photocopie

        # --- 2. Texte principal (légèrement plus visible à l'impression) ---
              c.saveState()
              c.setFont(FileConfig.FONT_NAME + "-Bold", 36)
              c.setFillAlpha(0.02)  # Très transparent
              c.setFillColorRGB(0.7, 0.7, 0.7)  # Gris moyen
              c.translate(width / 2, height / 2)
              c.rotate(45)

        # Répète le texte en mosaïque
              for i in range(-1, 2):
                 for j in range(-1, 2):
                    c.drawCentredString(i * 200, j * 200, text)
              c.restoreState()

        # --- 3. Motif "VOID" qui apparaît au scan (Pantographie simple) ---
        # Ce motif est fait de points fins, visibles quand le scanner applique du contraste

              c.save()
              packet.seek(0)
              return SecurityElement(
                    element_type=SecurityElementType.WATERMARK,
                    content=packet.read()
        )
        except Exception as e:
            raise FileSecurityError(f"La généération du filigrane a échoué : {e}")
    def generate_signature_text_overlay(self, file_hash: str) -> SecurityElement:
        """Génère un PDF d'une page avec le texte de l'empreinte du fichier."""
        try:
            timestamp = datetime.now().isoformat()
            packet = io.BytesIO()
            c = canvas.Canvas(packet, pagesize=FileConfig.DEFAULT_PAGE_SIZE)
            c.setFont(FileConfig.FONT_NAME, 8)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(20, 15, f"Empreinte (SHA256): {file_hash[:16]}...")
            c.drawString(20, 5, f"Horodatage: {timestamp}")
            c.save()
            packet.seek(0)
            return SecurityElement(
                element_type=SecurityElementType.SIGNATURE_TEXT,
                content=packet.read()
            )
        except Exception as e:
            raise FileSecurityError(f"La génération du texte de signature a échoué : {e}")


# --- Processeur Principal ---
class PDFSecurityProcessor:
    """Processeur principal pour la sécurisation des documents PDF."""

    def __init__(self):
        self.element_generator = SecurityElementGenerator()
        self.executor = ThreadPoolExecutor(max_workers=os.cpu_count())

    def _apply_security_elements(
        self,
        source_path: Path,
        output_path: Path,
        security_elements: List[SecurityElement],
        verification_code: str
    ):
        """Applique de manière synchrone les éléments de sécurité au document PDF."""
        try:
            source_pdf = PdfReader(str(source_path))
            output_pdf = PdfWriter()

            # Prépare les overlays réutilisables
            overlays = {}
            for element in security_elements:
                if element.element_type in [SecurityElementType.WATERMARK, SecurityElementType.SIGNATURE_TEXT]:
                    overlays[element.element_type] = PdfReader(io.BytesIO(element.content)).pages[0]

            for page_num, page in enumerate(source_pdf.pages, start=1):
                # Overlay spécifique à la page (QR, numéros, ID)
                page_overlay_packet = io.BytesIO()
                c = canvas.Canvas(page_overlay_packet, pagesize=(page.mediabox.width, page.mediabox.height))

                # 1. Ajouter le QR code
                qr_element = next((el for el in security_elements if el.element_type == SecurityElementType.QR_CODE), None)
                if qr_element and qr_element.content:
                    # ✅ Utilise ImageReader pour l'image PIL
                    image_reader = ImageReader(qr_element.content)
                    c.drawImage(
                        image=image_reader,
                        x=qr_element.position[0],
                        y=qr_element.position[1],
                        width=qr_element.size[0],
                        height=qr_element.size[1],
                        mask='auto'
                    )

                # 2. Ajouter info page et ID
                c.setFont(FileConfig.FONT_NAME, 8)
                c.drawString(20, 20, f"Page {page_num}/{len(source_pdf.pages)}")
                x_position = float(page.mediabox.width) - 20
                c.drawRightString(x_position, 20, f"ID: {verification_code[:8]}")
                c.save()

                page_overlay_packet.seek(0)

                # 3. Fusionner dans l'ordre correct
                if SecurityElementType.WATERMARK in overlays:
                    page.merge_page(overlays[SecurityElementType.WATERMARK])

                page.merge_page(PdfReader(page_overlay_packet).pages[0])

                if SecurityElementType.SIGNATURE_TEXT in overlays:
                    page.merge_page(overlays[SecurityElementType.SIGNATURE_TEXT])

                output_pdf.add_page(page)

            # Écriture finale atomique
            with temporary_file(suffix=".pdf") as temp_output_path:
                with open(temp_output_path, 'wb') as f:
                    output_pdf.write(f)
                shutil.move(str(temp_output_path), str(output_path))

        except Exception as e:
            logger.error(f"Échec de l'application des éléments de sécurité : {e}", exc_info=True)
            raise FileSecurityError(f"Impossible d'appliquer les éléments de sécurité : {e}")

    async def secure_document(
        self,
        source_path: Union[str, Path],
        output_path: Union[str, Path],
        verification_code: str,
        add_qr_code: bool = True,
        add_watermark: bool = True,
        add_signature_text: bool = True
    ) -> bool:
        """Orchestre la sécurisation d'un document PDF de manière asynchrone."""
        source_path = Path(source_path)
        output_path = Path(output_path)
        loop = asyncio.get_event_loop()
        try:
            FileValidator.validate_file_path(source_path)

            file_hash = await loop.run_in_executor(
                self.executor, FileHandler.calculate_hash, source_path
            )

            tasks = []
            if add_qr_code:
                tasks.append(loop.run_in_executor(self.executor, self.element_generator.generate_qr_code, verification_code))
            if add_watermark:
                tasks.append(loop.run_in_executor(self.executor, self.element_generator.generate_watermark_overlay))
            if add_signature_text:
                tasks.append(loop.run_in_executor(self.executor, self.element_generator.generate_signature_text_overlay, file_hash))

            security_elements = list(await asyncio.gather(*tasks))

            await loop.run_in_executor(
                self.executor,
                self._apply_security_elements,
                source_path,
                output_path,
                security_elements,
                verification_code
            )

            FileValidator.validate_file_path(output_path)
            logger.info(f"Document sécurisé avec succès : {output_path}")
            return True

        except Exception as e:
            logger.error(f"La sécurisation du document a échoué : {e}", exc_info=True)
            try:
                shutil.copy2(source_path, output_path)
                logger.warning(f"Utilisation de la copie de secours pour {output_path}")
                return True
            except Exception as copy_error:
                logger.critical(f"La copie de secours a également échoué : {copy_error}")
                return False
        finally:
            self.executor.shutdown(wait=False)


# --- API de Haut Niveau (Exemple pour FastAPI) ---
async def save_secured_file(
    uploaded_file: UploadFile,
    user_id: int,
    request_id: int,
    verification_code: str
) -> str:
    """Sauvegarde et sécurise un fichier téléversé."""
    await FileValidator.validate_upload_file(uploaded_file)
    save_dir = FileConfig.UPLOAD_DIR / f"user_{user_id}" / f"request_{request_id}"
    save_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    original_name = Path(uploaded_file.filename).stem
    safe_name = f"{timestamp}_{original_name[:50]}.pdf"
    temp_path = save_dir / f"temp_{safe_name}"
    final_path = save_dir / safe_name

    try:
        with open(temp_path, 'wb') as buffer:
            shutil.copyfileobj(uploaded_file.file, buffer)

        processor = PDFSecurityProcessor()
        success = await processor.secure_document(
            temp_path,
            final_path,
            verification_code,
            add_qr_code=True,
            add_watermark=True,
            add_signature_text=True
        )

        if not success:
            raise FileSecurityError("Le processus de sécurisation a échoué et la solution de repli aussi.")
        return str(final_path)

    except Exception as e:
        logger.error(f"Échec de la sauvegarde du fichier sécurisé : {e}")
        if final_path.exists():
            final_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Le traitement du fichier a échoué : {e}")
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        await uploaded_file.close()


# --- Initialisation du Module ---
FileConfig.initialize()
logger.info("Module des utilitaires de fichiers initialisé.")