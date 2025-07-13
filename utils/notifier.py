import smtplib
from email.mime.text import MIMEText
import logging

from config import settings

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) 
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class Notifier:
    def send_email_alert(self, subject: str, body: str):
        """
        Envoie une alerte par e-mail si les notifications par e-mail sont activées dans les paramètres.
        """
        if not settings.ENABLE_EMAIL_NOTIFICATIONS:
            logger.debug("Les notifications par e-mail sont désactivées.")
            return

        msg = MIMEText(body)
        msg['Subject'] = f"{settings.EMAIL_SUBJECT_PREFIX} {subject}"
        msg['From'] = settings.EMAIL_FROM
        msg['To'] = ", ".join(settings.EMAIL_TO) 
        try:
            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.starttls() # Enable TLS encryption
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            logger.info(f"Alerte par e-mail envoyée: '{msg['Subject']}' to {msg['To']}")
        except Exception as e:
            logger.error(f"Échec de l'envoi de l'alerte par e-mail: {e}", exc_info=True)