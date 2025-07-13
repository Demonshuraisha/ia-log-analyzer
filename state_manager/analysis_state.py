import logging
from datetime import datetime, timedelta

from config import settings
from core.elasticsearch_client import ElasticsearchClient 

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) 
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class AnalysisStateManager:
    def __init__(self, es_client: ElasticsearchClient):
        self.es_client = es_client
        # Assurez-vous que l'index d'état existe avec le mappage correct
        self.es_client.create_index_if_not_exists(settings.ANALYSIS_STATE_INDEX, {
            "properties": {
                "analysis_timestamp": {"type": "date"},
                "client_id": {"type": "keyword"},
                "last_processed_timestamp": {"type": "date"},
                "status": {"type": "keyword"}
            }
        })


    def get_last_analysis_timestamp(self, client_id: str) -> str:
        """
        Récupère l'horodatage du dernier journal traité avec succès pour un client spécifique.
        Si aucun état n'est trouvé, renvoie un horodatage légèrement antérieur à l'heure actuelle, basé sur INITIAL_LOOKBACK_SECONDS.
        """
        try:
            res = self.es_client.es.search(index=settings.ANALYSIS_STATE_INDEX, body={
                "size": 1,
                "sort": [{"last_processed_timestamp": {"order": "desc"}}],
                "query": {
                    "term": {"client_id.keyword": client_id} # Filter by client_id
                }
            })
            if res['hits']['hits']:
                timestamp = res['hits']['hits'][0]['_source']['last_processed_timestamp']
                logger.debug(f"Last processed timestamp for client '{client_id}': {timestamp}")
                return timestamp
        except Exception as e:
            logger.warning(f"Failed to retrieve last timestamp for client '{client_id}' from ES: {e}")
        
        # Solution de secours pour les nouveaux clients ou les erreurs
        fallback_timestamp = (datetime.utcnow() - timedelta(seconds=settings.INITIAL_LOOKBACK_SECONDS)).isoformat(timespec='milliseconds') + "Z"
        logger.info(f"Aucun état précédent trouvé pour le client '{client_id}' ou une erreur s'est produite. Démarrage de l'analyse à partir de: {fallback_timestamp}")
        return fallback_timestamp

    def update_last_analysis_timestamp(self, client_id: str, timestamp: str):
        """
        Met à jour l'horodatage du dernier journal traité avec succès pour un client spécifique.
        """
        try:
            doc = {
                "analysis_timestamp": datetime.utcnow().isoformat(timespec='milliseconds') + "Z",
                "client_id": client_id, # Crucially, store the client ID
                "last_processed_timestamp": timestamp,
                "status": "completed"
            }
            # Utilisez « create » avec un ID dérivé de client_id pour éviter les doublons au redémarrage
            # Ou utilisez « index » qui mettra à jour s'il existe, créera s'il n'existe pas
            self.es_client.es.index(index=settings.ANALYSIS_STATE_INDEX, document=doc)
            logger.info(f"État d'analyse mis à jour pour le client '{client_id}': traité jusqu'à {timestamp}")
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de l'état d'analyse pour le client '{client_id}': {e}", exc_info=True)