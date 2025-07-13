import os
from datetime import timedelta

# --- Paramètre Elasticsearch ---
ES_HOST = os.getenv("ES_HOST", "")
ES_USER = os.getenv("ES_USER", "") 
ES_PASSWORD = os.getenv("ES_PASSWORD", "") 
LOG_INDEX_PATTERN = os.getenv("LOG_INDEX_PATTERN", "filebeat-*")
ANALYSIS_STATE_INDEX = os.getenv("ANALYSIS_STATE_INDEX", "ia-analysis-state")
IA_RESULTS_INDEX = os.getenv("IA_RESULTS_INDEX", "ia-analysis-results")

# --- Parametre d'idientification du clients ---
CLIENT_ID_FIELD = os.getenv("CLIENT_ID_FIELD", "host.name.keyword")


# --- Paramétre de l'API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


# Prompt pour l'analyse IA
DEFAULT_IA_PROMPT = """
Analysez les entrées de journal fournies pour détecter d'éventuels problèmes de sécurité (par exemple, accès non autorisé, tentatives d'attaque par force brute), des problèmes de performances (par exemple, dépassements de délai, latence élevée) et des erreurs système critiques (par exemple, pannes de service, disque plein).
Pour chaque problème identifié, fournissez:
1. Un résumé concis du problème;
2. Son niveau de gravité (critique, élevé, moyen, faible, informatif).
3. Des suggestions d'actions correctives.

Si aucun problème significatif n'est détecté, indiquez «Aucun problème significatif détecté».
Formalisez votre réponse sous forme de texte clair et lisible, en priorisant les problèmes critiques.

Journaux à analyser:
"""

# --- Paramètres de comportement du script ---
# Fréquence d'exécution de la boucle principale pour vérifier les nouveaux journaux
ANALYSIS_INTERVAL_SECONDS = int(os.getenv("ANALYSIS_INTERVAL_SECONDS", 300)) # 5 minutes

# Nombre maximal de messages de journal individuels à envoyer à l'IA en un seul lot
MAX_LOGS_PER_BATCH = int(os.getenv("MAX_LOGS_PER_BATCH", 50)) 

# Différence horaire par rapport à l'heure UTC actuelle pour la récupération initiale du journal
# Utilisé si aucun état précédent n'est trouvé pour un client 
INITIAL_LOOKBACK_SECONDS = int(os.getenv("INITIAL_LOOKBACK_SECONDS", 3600)) # 1 hour

# Période de temps pour rechercher les clients actifs 
ACTIVE_CLIENTS_LOOKBACK_TIME = os.getenv("ACTIVE_CLIENTS_LOOKBACK_TIME", "24h")


# --- Paramètres de notification par e-mail ---
ENABLE_EMAIL_NOTIFICATIONS = os.getenv("ENABLE_EMAIL_NOTIFICATIONS", "False").lower() == "true"
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.example.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", None)
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", None)
EMAIL_FROM = os.getenv("EMAIL_FROM", "ia-analyzer@yourdomain.com")
EMAIL_TO = os.getenv("EMAIL_TO", "admin@yourdomain.com").split(',') 
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "[IA Log Analyzer Alert]")

# Niveaux de gravité qui déclenchent une alerte par e-mail
ALERT_SEVERITIES = [s.strip().lower() for s in os.getenv("ALERT_SEVERITIES", "critical,high").split(',')]