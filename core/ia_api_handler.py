import logging
import google.generativeai as genai
import json 

from config import settings

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) 
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class IAApiHandler:
    def __init__(self):
        self.ia_service = self._initialize_ia_service()

    def _initialize_ia_service(self):
        """Initialise le client API AI sélectionné."""
        if settings.GEMINI_API_KEY:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-2.0-flash')
                logger.info("API Google Gemini initialisée.")
                return model
            except Exception as e:
                logger.critical(f"Échec de l'initialisation de l'API Google Gemini: {e}")
                raise
        else:
            logger.critical("Aucune clé API IA trouvée (GEMINI_API_KEY). Veuillez en configurer une.")
            raise ValueError("Aucune clé API AI configurée.")

    def analyze_logs(self, logs_data: list, prompt: str) -> str:
        """
        Envoie les journaux formatés à l'IA pour analyse et renvoie le résumé..
        """
        if not self.ia_service:
            logger.error("Service d'IA non initialisé. Impossible d'analyser les journaux.")
            return "Échec de l'analyse de l'IA: service non initialisé."
        full_prompt_content = f"{prompt}\n\n```logs\n{logs_data}\n```"

        try:
            if isinstance(self.ia_service, genai.GenerativeModel): 
                response = self.ia_service.generate_content(full_prompt_content)
                return response.text 
            else:
                logger.error("Type de service IA inconnu.")
                return "Échec de l'analyse de l'IA: type de service inconnu."
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de l'IA: {e}", exc_info=True)
            return f"L'analyse de l'IA a échoué: {e}"