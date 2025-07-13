import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) 
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class LogProcessor:
    def format_logs_for_ia(self, logs_data: list) -> str:
        """
        Formate une liste de dictionnaires de journaux bruts en une seule chaîne adaptée à l'analyse par IA.
        Chaque message de journal est préfixé par son horodatage pour une meilleure contextualisation.
        """
        formatted_logs = []
        for log in logs_data:
            timestamp = log.get('@timestamp', 'N/A')
            message = log.get('message', 'No message found').strip()
            if message:
                formatted_logs.append(f"[{timestamp}] {message}")
        
        if not formatted_logs:
            return "No log messages provided."
            
        return "\n".join(formatted_logs)

    def extract_metadata_from_logs(self, logs_data: list) -> dict:
        """
        Extrait les métadonnées pertinentes d'un lot de journaux pour enrichir les résultats d'analyse de l'IA.
        Cela facilite la corrélation et le filtrage ultérieurs dans Kibana.
        """
        source_hosts = set()
        source_log_types = set()
        raw_logs_sample = []

        for log in logs_data:
            # Extraire les noms d'hôtes
            if 'host' in log and 'name' in log['host']:
                source_hosts.add(log['host']['name'])
            
            # Extraire les types de journaux (par exemple, à partir de « event.module » ou « fileset.name »)
            if 'event' in log and 'module' in log['event']:
                source_log_types.add(log['event']['module'])
            elif 'fileset' in log and 'name' in log['fileset']:
                source_log_types.add(log['fileset']['name'])
            elif 'agent' in log and 'type' in log['agent']: # par exemple, pour les journaux système
                source_log_types.add(log['agent']['type'])


            # Ajoutez un petit échantillon de messages bruts pour le contexte dans Kibana
            if len(raw_logs_sample) < 5:# Limiter la taille de l'échantillon pour éviter les documents volumineux
                raw_logs_sample.append(log.get('message', ''))
        
        return {
            "source_hosts": list(source_hosts),
            "source_log_types": list(source_log_types),
            "raw_logs_sample": raw_logs_sample,
            "analyzed_log_count": len(logs_data)
        }