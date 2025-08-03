# test.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import asyncio
from pathlib import Path
import random
import string

# ✅ Importe depuis file_utils (doit être le nom du fichier)
try:
    from file_utils import PDFSecurityProcessor, FileConfig
except ImportError as e:
    messagebox.showerror("Erreur d'Importation", f"Impossible d'importer file_utils.py : {e}\n\nAssurez-vous que 'file_utils.py' (ou un lien vers file_utils_optimized.py) est dans le même dossier.")
    exit()

class SecurityTestApp:
    """
    Interface graphique Tkinter pour tester le module de sécurisation de PDF.
    """
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Testeur de Sécurisation PDF")
        self.root.geometry("550x450")
        self.root.resizable(False, False)

        # Style
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('TButton', padding=6, relief="flat", background="#007bff", foreground="white")
        style.map('TButton', background=[('active', '#0056b3')])
        style.configure('TLabel', padding=5)
        style.configure('TEntry', padding=5)
        style.configure('TCheckbutton', padding=5)
        style.configure('Title.TLabel', font=('Helvetica', 14, 'bold'))
        style.configure('Status.TLabel', font=('Helvetica', 10, 'italic'))

        # Variables
        self.source_file_path = tk.StringVar()
        self.user_id_var = tk.StringVar(value=str(random.randint(100, 999)))
        self.request_id_var = tk.StringVar(value=str(random.randint(1000, 9999)))
        self.verification_code_var = tk.StringVar(value=''.join(random.choices(string.ascii_uppercase + string.digits, k=12)))
        self.add_qr_var = tk.BooleanVar(value=True)
        self.add_watermark_var = tk.BooleanVar(value=True)
        self.add_signature_text_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Prêt. Veuillez sélectionner un fichier.")

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="15 15 15 15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Titre ---
        ttk.Label(main_frame, text="Tester la Sécurisation de PDF", style='Title.TLabel').grid(row=0, column=0, columnspan=3, pady=(0, 20))

        # --- Sélection fichier ---
        ttk.Button(main_frame, text="1. Choisir un fichier PDF...", command=self.select_source_file).grid(row=1, column=0, sticky="ew", padx=(0, 10))
        ttk.Entry(main_frame, textvariable=self.source_file_path, state="readonly", width=45).grid(row=1, column=1, columnspan=2, sticky="ew")

        # --- Paramètres ---
        params_frame = ttk.LabelFrame(main_frame, text="2. Paramètres", padding=10)
        params_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=20)
        params_frame.columnconfigure(1, weight=1)

        ttk.Label(params_frame, text="User ID:").grid(row=0, column=0, sticky="w")
        ttk.Entry(params_frame, textvariable=self.user_id_var).grid(row=0, column=1, sticky="ew")

        ttk.Label(params_frame, text="Request ID:").grid(row=1, column=0, sticky="w")
        ttk.Entry(params_frame, textvariable=self.request_id_var).grid(row=1, column=1, sticky="ew")

        ttk.Label(params_frame, text="Code de Vérification:").grid(row=2, column=0, sticky="w")
        ttk.Entry(params_frame, textvariable=self.verification_code_var).grid(row=2, column=1, sticky="ew")

        # --- Options ---
        options_frame = ttk.LabelFrame(main_frame, text="3. Options de Sécurité", padding=10)
        options_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 20))

        ttk.Checkbutton(options_frame, text="Ajouter un QR Code", variable=self.add_qr_var).pack(anchor="w")
        ttk.Checkbutton(options_frame, text="Ajouter un Filigrane 'Confidentiel'", variable=self.add_watermark_var).pack(anchor="w")
        ttk.Checkbutton(options_frame, text="Ajouter le Texte de Signature (Hash)", variable=self.add_signature_text_var).pack(anchor="w")

        # --- Action ---
        self.process_button = ttk.Button(main_frame, text="🚀 Lancer la Sécurisation", command=self.start_securization_thread)
        self.process_button.grid(row=4, column=0, columnspan=3, sticky="ew", ipady=10)

        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, style='Status.TLabel', wraplength=500)
        self.status_label.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 0))

    def select_source_file(self):
        filepath = filedialog.askopenfilename(
            title="Sélectionnez un fichier PDF",
            filetypes=[("Fichiers PDF", "*.pdf"), ("Tous les fichiers", "*.*")]
        )
        if filepath:
            self.source_file_path.set(filepath)
            self.status_var.set(f"Fichier sélectionné : {Path(filepath).name}")

    def start_securization_thread(self):
        if not self.source_file_path.get():
            messagebox.showwarning("Fichier manquant", "Veuillez d'abord sélectionner un fichier PDF.")
            return

        self.process_button.config(state="disabled", text="Traitement en cours...")
        self.status_var.set("Lancement du processus de sécurisation...")

        thread = threading.Thread(target=self.run_securization)
        thread.daemon = True
        thread.start()

    def run_securization(self):
        try:
            source_path = Path(self.source_file_path.get())
            output_path = source_path.with_name(f"{source_path.stem}_SECURISE.pdf")

            processor = PDFSecurityProcessor()

            # Exécute la méthode asynchrone
            success = asyncio.run(processor.secure_document(
                source_path=source_path,
                output_path=output_path,
                verification_code=self.verification_code_var.get(),
                add_qr_code=self.add_qr_var.get(),
                add_watermark=self.add_watermark_var.get(),
                add_signature_text=self.add_signature_text_var.get()
            ))

            if success:
                self.status_var.set(f"✅ Succès ! Fichier sauvegardé ici : {output_path}")
                messagebox.showinfo("Succès", f"Le fichier a été sécurisé avec succès et enregistré sous :\n{output_path}")
            else:
                raise Exception("Le processus de sécurisation a échoué.")

        except Exception as e:
            self.status_var.set(f"❌ Erreur : {e}")
            messagebox.showerror("Erreur", f"Une erreur est survenue :\n\n{e}")
        finally:
            self.process_button.config(state="normal", text="🚀 Lancer la Sécurisation")


if __name__ == "__main__":
    try:
        FileConfig.initialize()
    except Exception as e:
        messagebox.showerror("Erreur", f"Échec de l'initialisation : {e}")
        exit()

    root = tk.Tk()
    app = SecurityTestApp(root)
    root.mainloop()