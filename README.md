
**Nom de l'Application :** Service d'Authentification de Documents

**Objectif :**
Fournir une plateforme numérique sécurisée et centralisée permettant aux étudiants, partenaires et services internes de l'université de gérer efficacement les demandes de services liés aux documents académiques (authentification, légalisation, duplicata, traduction, transmission).

**Architecture :**
L'application suit une architecture modulaire en couches :
*   **Backend :** FastAPI (Python) pour la logique métier et les API.
*   **Base de Données :** PostgreSQL (ou SQLite) avec SQLAlchemy ORM.
*   **Frontend :** Templates HTML rendus côté serveur avec Jinja2, stylisés avec Bootstrap 5, Font Awesome, Bootstrap Icons.
*   **Stockage :** Système de fichiers local pour les documents uploadés et générés.
*   **Gestion des États :** Alembic pour la migration du schéma de base de données.

---

### **Fonctionnalités Principales :**

**1. Gestion des Utilisateurs et des Rôles :**
*   **Inscription/Connexion :**
    *   Inscription pour les étudiants/clients avec validation des données.
    *   Connexion sécurisée avec JWT (JSON Web Tokens).
    *   Déconnexion.
*   **Rôles et Permissions :**
    *   **Étudiant/Client (`user`) :** Soumettre des demandes, suivre leur statut, effectuer des paiements.
    *   **Partenaire (`PARTENAIRE`) :** Soumettre des demandes au nom d'étudiants tiers.
    *   **Service COURIEL (`COURIEL`) :** Réceptionner les demandes physiques, les traiter, générer des réponses sécurisées, notifier les demandeurs.
    *   **Administrateur (`admin`) :** Gérer les utilisateurs, les rôles, les permissions, visualiser toutes les demandes, accéder aux statistiques.
*   **Tableau de Bord Personnalisé :** Chaque rôle dispose d'un tableau de bord adapté (statistiques, listes de demandes, raccourcis).

**2. Gestion des Demandes :**
*   **Création de Demande (Étudiant/Partenaire) :**
    *   Formulaire intuitif en étapes (Service, Bénéficiaire, Document, Paiement).
    *   Choix du type de service (Authentification, Duplicata, etc.).
    *   Possibilité de demander pour soi-même ou pour un tiers.
    *   Spécification du document concerné (type, intitulé, année, etc.).
    *   Upload sécurisé du fichier du document.
    *   Calcul automatique du prix basé sur le service et le nombre de copies.
    *   Choix de la méthode de paiement (Mobile Money, Carte, Virement).
*   **Workflow de Demande :**
    *   `BROUILLON` -> `PAIEMENT_EN_ATTENTE` -> `SOUMISE` -> `RECU` -> `EN_TRAITEMENT` -> `COMPLETEE` (ou `REJETEE`, `ANNULEE`).
    *   Suivi détaillé de l'état de chaque demande.
*   **Historique :** Tracabilité complète des changements de statut et actions effectuées sur chaque demande.

**3. Gestion des Paiements :**
*   **Intégration :** Interface pour simuler ou intégrer des passerelles de paiement (Orange Money, PayPal, etc.).
*   **Suivi :** Statut du paiement (`EN_ATTENTE`, `PAYE`, `ECHEC`) lié au statut de la demande.
*   **Validation :** Vérification du montant payé avant de soumettre la demande au service COURIEL.

**4. Traitement par le Service COURIEL :**
*   **Réception :**
    *   Interface pour marquer une demande comme "Reçue".
    *   Création automatique d'un dossier physique dans `downloads/couriel/demande_<ID>`.
*   **Traitement Manuel :**
    *   Interface pour gérer le traitement physique (vérification, authentification).
*   **Réponse et Sécurisation :**
    *   Upload du document scanné final.
    *   **Sécurisation Automatique :** Application de transformations de sécurité avancées sur le document scanné :
        *   **QR Code :** Contenant un lien de vérification unique (`/verification/<code>`).
        *   **Filigrane Visible :** Texte "DOCUMENT AUTHENTIFIE" ou similaire.
        *   **Filigrane Invisible :** Texte très clair ou points microscopiques pour une sécurité supplémentaire.
        *   **Signature Numérique (Simulation/Watermark) :** Ajout d'un motif complexe ou d'un texte "Signé numériquement".
    *   Génération d'un document PDF sécurisé.
    *   Mise à jour du statut de la demande à `COMPLETEE`.
    *   Envoi automatique d'une notification par email au demandeur avec le document sécurisé en pièce jointe.

**5. Vérification Publique :**
*   **Page Dédiée :** Accès public via un lien unique (`/verification/<code_unique>`).
*   **Authentification :** Permet à toute personne de vérifier l'authenticité d'un document traité en scannant le QR code ou en saisissant le code de vérification.
*   **Informations Affichées :** Détails de la demande et de la réponse associée.

**6. Gestion Administrative :**
*   **Utilisateurs :** CRUD (Créer, Lire, Mettre à jour, Supprimer) des utilisateurs et gestion de leurs rôles.
*   **Demandes :** Visualisation, filtrage et mise à jour du statut de toutes les demandes.
*   **Rôles & Permissions :** Gestion fine des accès via un système de rôles et permissions.
*   **Statistiques :** Tableau de bord avec indicateurs clés (nombre total de demandes, demandes par statut, etc.).
*   **Journaux d'Activité :** Suivi des actions importantes effectuées par les utilisateurs.

**7. Pages Publiques :**
*   **Accueil :** Présentation du service, accès à la connexion/inscription.
*   **À Propos :** Informations sur l'institut et le service.
*   **Contact :** Formulaire de contact pour les demandes d'assistance ou d'information.

**8. Sécurité :**
*   **Authentification :** Mots de passe hachés (bcrypt), tokens JWT.
*   **Autorisation :** Contrôle d'accès basé sur les rôles (RBAC).
*   **Validation :** Validation stricte des données d'entrée côté serveur.
*   **Sécurité des Documents :** Fonctions de sécurisation avancées (QR code, filigranes, watermark) appliquées aux documents finaux.
*   **Stockage :** Organisation sécurisée des fichiers uploadés et générés.

---

**En Résumé :**
Cette application rationalise et sécurise le processus complexe de gestion des documents académiques. Elle connecte efficacement les demandeurs (étudiants, partenaires) avec le service de traitement interne (COURIEL) et les administrateurs, en offrant une traçabilité complète, une interface utilisateur adaptée à chaque rôle et des documents finaux authentifiés numériquement.