import logging
import logging.handlers
import os
from datetime import datetime


def setup_logging(log_level=logging.INFO):
    """Configure le système de logging avec rotation des fichiers."""
    
    # Créer le dossier logs s'il n'existe pas
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configuration du format des logs
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Logger principal
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Handler pour fichier avec rotation (max 10MB, 5 fichiers)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'alphababoon.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(log_format)
    
    # Handler pour la console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    
    # Handler séparé pour les erreurs
    error_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'errors.log'),
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(log_format)
    
    # Handler pour les actions de modération
    moderation_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'moderation.log'),
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    moderation_handler.setLevel(logging.WARNING)
    moderation_handler.setFormatter(log_format)
    
    # Ajouter les handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.addHandler(error_handler)
    logger.addHandler(moderation_handler)
    
    # Logger spécifique pour les statistiques IRC
    irc_logger = logging.getLogger('irc_stats')
    irc_stats_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'irc_stats.log'),
        maxBytes=50 * 1024 * 1024,  # 50MB pour les stats
        backupCount=2,
        encoding='utf-8'
    )
    irc_stats_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    irc_logger.addHandler(irc_stats_handler)
    irc_logger.setLevel(logging.INFO)
    
    return logger


def log_startup_info():
    """Log les informations de démarrage."""
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("AlphaBaboon Bot - Démarrage")
    logger.info(f"Heure de démarrage: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)


def log_shutdown_info():
    """Log les informations d'arrêt."""
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("AlphaBaboon Bot - Arrêt")
    logger.info(f"Heure d'arrêt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)