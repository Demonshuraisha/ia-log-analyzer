import logging
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from datetime import datetime, timedelta

from config import settings

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) 

if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class ElasticsearchClient:
    def __init__(self):
        self.es = self._connect_elasticsearch()

    def _connect_elasticsearch(self):
        """Établit et renvoie une connexion client Elasticsearch."""
        try:
            if settings.ES_USER and settings.ES_PASSWORD:
                es_client = Elasticsearch(
                    settings.ES_HOST,
                    http_auth=(settings.ES_USER, settings.ES_PASSWORD),
                    request_timeout=60, # Délai d'expiration pour les requêtes potentiellement lourdes
                    verify_certs=False,  
                    ssl_show_warn=False
                )
            else:
                es_client = Elasticsearch(settings.ES_HOST, request_timeout=60)
                verify_certs=False,  
                ssl_show_warn=False
            
            if not es_client.ping():
                raise ValueError("La connexion à Elasticsearch a échoué!")
            logger.info("Connexion réussie à Elasticsearch.")
            return es_client
        except Exception as e:
            logger.critical(f"Impossible de se connecter à Elasticsearch: {e}")
            raise

    def get_active_clients(self, lookback_time: str = settings.ACTIVE_CLIENTS_LOOKBACK_TIME) -> list:
        """
        Récupère une liste d'identifiants clients uniques à partir des journaux
        au cours d'une période spécifiée.
        """
        query_body = {
            "aggs": {
                "unique_clients": {
                    "terms": {
                        "field": settings.CLIENT_ID_FIELD,
                        "size": 1000 # Ajustez la taille en fonction du nombre maximum de clients attendus
                    }
                }
            },
            "size": 0, # Nous n’avons besoin que d’agrégations, pas de documents réels
            "query": {
                "range": {
                    "@timestamp": {
                        "gte": f"now-{lookback_time}",
                        "lte": "now"
                    }
                }
            }
        }
        try:
            res = self.es.search(index=settings.LOG_INDEX_PATTERN, body=query_body)
            clients = [bucket['key'] for bucket in res['aggregations']['unique_clients']['buckets']]
            logger.info(f"{len(clients)} clients actifs dans les journaux au cours des dernières {lookback_time}.")
            return clients
        except Exception as e:
            logger.error(f"Nous n’avons besoin que d’agrégations, pas de documents réels {e}", exc_info=True)
            return []

    def fetch_logs_for_client(self, client_id: str, start_timestamp: str) -> list:
        """
        Récupère un lot de journaux pertinents pour un client spécifique, filtrés par 
        horodatage et mots-clés potentiellement erronés/suspects.
        """
        query_body = {
            "size": settings.MAX_LOGS_PER_BATCH,
            "sort": [{"@timestamp": {"order": "asc"}}], 
            "query": {
                "bool": {
                    "must": [
                        {"term": {settings.CLIENT_ID_FIELD: client_id}}, # Filtrer par ID client spécifique
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": start_timestamp,
                                    "lt": "now/s", # Obtenir les journaux jusqu'à la seconde actuelle
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ],
                    "should": [
                        {"match": {"log.level": "error"}},
                        {"match": {"log.level": "warn"}},
                        {"match": {"message": "*fail*"}},
                        {"match": {"message": "*denied*"}},
                        {"match": {"message": "*refused*"}},
                        {"match": {"message": "*authentication*"}},
                        {"match": {"message": "*permission*"}},
                        {"match": {"message": "*timeout*"}}, # Délai d'attente ajouté
                        {"range": {"http.response.status_code": {"gte": 500}}}, # Plus de générique pour HTTP 5xx
                        {"match": {"tags": "security"}},
                        {"match": {"tags": "error"}},
                        {"match": {"tags": "performance"}} # Balise de performance ajoutée
                    ],
                    "minimum_should_match": 1 # Au moins une condition « devrait » doit correspondre
                }
            }
        }

        try:
            res = self.es.search(index=settings.LOG_INDEX_PATTERN, body=query_body)
            logs = [hit['_source'] for hit in res['hits']['hits']]
            if logs:
                logger.info(f"Récupéré {len(logs)} journaux pour le client '{client_id}' depuis {logs[0].get('@timestamp')} à {logs[-1].get('@timestamp')}.")
            else:
                logger.debug(f"Aucun nouveau journal pertinent pour le client '{client_id}' depuis {start_timestamp}.")
            return logs
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des journaux pour le client '{client_id}' depuis Elasticsearch: {e}", exc_info=True)
            return []

    def send_ia_results(self, ia_result_doc: dict):
        """
        Envoie le document de résultat d'analyse AI à un index Elasticsearch dédié.
        """
        try:
            self.es.index(index=settings.IA_RESULTS_INDEX, document=ia_result_doc)
            logger.info(f"Résultat de l'analyse IA envoyé à l'index Elasticsearch '{settings.IA_RESULTS_INDEX}' pour le client '{ia_result_doc.get('client_id', 'N/A')}'.")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du résultat de l'analyse AI à Elasticsearch: {e}", exc_info=True)

    def create_index_if_not_exists(self, index_name: str, mappings: dict = None):
        """
        Crée un index Elasticsearch avec des mappages facultatifs s'il n'existe pas déjà.
        """
        try:
            if not self.es.indices.exists(index=index_name):
                self.es.indices.create(index=index_name, mappings=mappings if mappings else {})
                logger.info(f"Index '{index_name}' créé avec succès.")
            else:
                logger.debug(f"Index '{index_name}' existe déjà.")
        except Exception as e:
            logger.error(f"Erreur lors de la création de l'index '{index_name}': {e}", exc_info=True)

# Exemple de mappage pour l'index des résultats d'analyse d'IA (ia-analysis-results)
# Ce mappage améliore les performances d'indexation et de recherche pour des champs spécifiques
IA_RESULTS_MAPPING = {
    "properties": {
        "@timestamp": {"type": "date"},
        "analysis_start_time": {"type": "date"},
        "analysis_end_time": {"type": "date"},
        "client_id": {"type": "keyword"}, # Utilisez un mot-clé pour une correspondance exacte et des agrégations
        "ia_analysis_summary": {"type": "text"},
        "analyzed_log_count": {"type": "integer"},
        "source_hosts": {"type": "keyword"},
        "source_log_types": {"type": "keyword"},
        "script_name": {"type": "keyword"},
        "status": {"type": "keyword"},
        # Ajoutez ici tous les autres champs que vous attendez de la sortie de l'analyse IA
        "severity": {"type": "keyword"}, 
        "suggested_action": {"type": "text"}
    }
}

#Exemple de mappage pour l'index d'état d'analyse (ia-analysis-state)
ANALYSIS_STATE_MAPPING = {
    "properties": {
        "analysis_timestamp": {"type": "date"},
        "client_id": {"type": "keyword"},
        "last_processed_timestamp": {"type": "date"},
        "status": {"type": "keyword"}
    }
}