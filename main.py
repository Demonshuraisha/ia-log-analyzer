import time
import logging
from datetime import datetime, timedelta

from config import settings
from core.elasticsearch_client import ElasticsearchClient, IA_RESULTS_MAPPING, ANALYSIS_STATE_MAPPING
from core.ia_api_handler import IAApiHandler
from processors.log_processor import LogProcessor
from state_manager.analysis_state import AnalysisStateManager
from utils.notifier import Notifier

# Configure root logger
logging.basicConfig(level=logging.INFO, # Global log level
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.StreamHandler() # Output to console
                        # Optional: logging.FileHandler("ia-log-analyzer.log") # Output to file
                    ])
logger = logging.getLogger(__name__)

def main_analysis_loop():
    logger.info("Démarrage du script IA Log Analyzer...")

    es_client = ElasticsearchClient()
    ia_handler = IAApiHandler()
    log_processor = LogProcessor()
    state_manager = AnalysisStateManager(es_client)
    notifier = Notifier()

    # Assurez-vous que les index Elasticsearch nécessaires existent
    es_client.create_index_if_not_exists(settings.IA_RESULTS_INDEX, IA_RESULTS_MAPPING)
    es_client.create_index_if_not_exists(settings.ANALYSIS_STATE_INDEX, ANALYSIS_STATE_MAPPING)


    while True:
        try:
            current_time_utc = datetime.utcnow()
            global_analysis_end_time = current_time_utc.isoformat(timespec='milliseconds') + "Z"
            
            logger.info(f"\n--- Démarrage d'un nouveau cycle d'analyse pour tous les clients actifs jusqu'à {global_analysis_end_time} ---")

            # Étape 1 : Obtenir la liste des clients actifs
            active_clients = es_client.get_active_clients(lookback_time=settings.ACTIVE_CLIENTS_LOOKBACK_TIME)

            if not active_clients:
                logger.info("Aucun client actif trouvé dans les journaux récents. En attente du prochain cycle.")
                time.sleep(settings.ANALYSIS_INTERVAL_SECONDS)
                continue # Passer à l'itération suivante de la boucle principale

            for client_id in active_clients:
                logger.info(f"\n--- Traitement des journaux pour le client: '{client_id}' ---")
                
                # Étape 2 : Obtenir l’horodatage du dernier traitement pour ce client
                analysis_start_time_client = state_manager.get_last_analysis_timestamp(client_id)

                # Étape 3 : Récupérer les journaux pertinents pour ce client
                logs_to_analyze = es_client.fetch_logs_for_client(client_id, analysis_start_time_client)

                if logs_to_analyze:
                    logger.info(f"Préparation de {len(logs_to_analyze)} journaux pour l'analyse IA pour le client '{client_id}'.")
                    
                    # Étape 4 : Préparer les journaux pour l’IA (concaténer et extraire les métadonnées)
                    formatted_logs_for_ia = log_processor.format_logs_for_ia(logs_to_analyze)
                    extracted_metadata = log_processor.extract_metadata_from_logs(logs_to_analyze)

                    # Étape 5 : Analyser les journaux avec l’API AI
                    ia_analysis_summary = ia_handler.analyze_logs(formatted_logs_for_ia, settings.DEFAULT_IA_PROMPT)
                    
                    logger.info(f"Analyse de l'IA pour le client '{client_id}' terminé. Résultat (aperçu): {ia_analysis_summary[:200]}...")

                    # Étape 6 : Envoyer les résultats de l’analyse IA à Elasticsearch
                    ia_result_doc = {
                        "@timestamp": current_time_utc.isoformat(timespec='milliseconds') + "Z", # Horodatage du moment où l'analyse a été effectuée
                        "analysis_start_time": analysis_start_time_client,
                        "analysis_end_time": global_analysis_end_time,
                        "client_id": client_id, # **CRITIQUE : Associer les résultats au client**
                        "ia_analysis_summary": ia_analysis_summary,
                        "script_name": "ia_log_analyzer_main",
                        "status": "completed",
                        **extracted_metadata, # Inclure des métadonnées telles que source_hosts, log_types, analyzed_log_count
                    }
                    es_client.send_ia_results(ia_result_doc)

                    # # Étape 7 (facultative) : envoyer des alertes par e-mail si des problèmes critiques sont détectés
                    # Cela nécessite d'analyser le résumé de l'IA pour trouver la gravité
                    for severity_level in settings.ALERT_SEVERITIES:
                        if severity_level in ia_analysis_summary.lower():
                            logger.warning(f"'{severity_level.upper()}' problème détecté par l'IA pour le client '{client_id}'. Envoi d'alerte par e-mail.")
                            notifier.send_email_alert(
                                subject=f"ALERTE IA - Client {client_id}: {severity_level.upper()} Problème détecté !",
                                body=f"L'IA a détecté un {severity_level} problème pour le client '{client_id}' dans les journaux récents.\n\nRésumé de l'IA:\n{ia_analysis_summary}\n\nConsultez Kibana pour plus de détails, filtrez par client_id: '{client_id}'."
                            )
                            break # Envoyer une seule alerte par lot pour la gravité détectée la plus élevée
                else:
                    logger.info(f"Aucun nouveau journal pertinent à analyser pour le client '{client_id}' pour cette période.")
                
                # Étape 8 : Mettre à jour l’horodatage du dernier journal traité pour ce client
                # Cela garantit la continuité même si un client n’a pas de nouveaux journaux pertinents pour un cycle.
                state_manager.update_last_analysis_timestamp(client_id, global_analysis_end_time)

            logger.info("Tous les clients actifs traités pour ce cycle.")

        except Exception as e:
            logger.critical(f"Une erreur inattendue s'est produite dans la boucle d'analyse principale : {e}", exc_info=True)
            notifier.send_email_alert(
                subject="ERREUR CRITIQUE - Analyseur de journaux IA",
                body=f"Le script IA Log Analyzer a rencontré une erreur critique : {e}\n"
                     "Veuillez consulter les journaux de script pour plus de détails."
            )
        
        logger.info(f"En attente de {settings.ANALYSIS_INTERVAL_SECONDS} secondes avant le prochain cycle d'analyse globale...")
        time.sleep(settings.ANALYSIS_INTERVAL_SECONDS)

# Point d'entrée du script
if __name__ == "__main__":
    main_analysis_loop()