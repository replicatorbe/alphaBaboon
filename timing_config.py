#!/usr/bin/env python3
"""
Configuration centralisée des timings pour AlphaBaboon.
Rend configurables toutes les constantes de temps hardcodées.
"""

from typing import Dict, Any, List
import logging


class TimingConfig:
    """
    Gestionnaire centralisé des configurations de timing.
    Permet de rendre configurables toutes les constantes magiques de temps.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Valeurs par défaut pour tous les timings
        self.defaults = {
            # IRC Connection & Reconnection
            'irc_connect_timeout': 30,              # Timeout connexion IRC
            'irc_retry_delay': 60,                  # Délai entre tentatives reconnexion
            'irc_max_retry_delay': 300,             # Délai max entre tentatives (5 min)
            'irc_ping_interval': 300,               # Intervalle ping keepalive (5 min)
            'irc_cycle_reset_delay': 900,           # Reset cycle reconnexion (15 min)
            
            # Moderation Actions
            'moderation_cooldown_minutes': 2,       # Cooldown entre actions modération
            'moderation_reset_hours': 24,           # Reset historique violations
            'moderation_move_delay': 3,             # Délai avant déplacer utilisateur
            'moderation_welcome_delay': 5,          # Délai avant message bienvenue
            'moderation_kick_delay': 2,             # Délai avant kick
            'moderation_ban_delay': 2,              # Délai avant ban
            'moderation_phone_ban_delay': 3,        # Délai avant ban téléphone
            
            # Temporary Bans
            'temp_ban_badwords_minutes': 10,        # Ban temporaire mots interdits
            'temp_ban_nickname_seconds': 30,        # Ban temporaire pseudo
            'temp_ban_phone_hours': 24,             # Ban temporaire téléphone
            
            # Health Monitoring
            'health_check_interval_minutes': 5,     # Intervalle checks santé
            'health_openai_timeout': 10,            # Timeout test OpenAI
            'health_error_sleep': 30,               # Pause si erreur monitoring
            
            # Content Analysis
            'content_behavior_window_hours': 1,     # Fenêtre analyse comportement
            'content_min_request_interval': 0.1,    # Délai min entre requêtes OpenAI
            'content_cache_timeout_minutes': 60,    # Timeout cache admin commands
            
            # State Management
            'state_save_interval': 300,             # Intervalle sauvegarde état (5 min)
            'state_shutdown_timeout': 5,            # Timeout arrêt threads
            
            # Cache Management
            'cache_cleanup_ratio': 0.8,             # Ratio nettoyage cache (80%)
            
            # Main Loop
            'main_loop_sleep': 5,                   # Pause boucle principale
            'main_error_sleep': 10,                 # Pause si erreur boucle
            'main_restart_delay': 10,               # Délai avant redémarrage IRC
            
            # Drug Detection
            'drug_sensitivity_threshold': 4.0,      # Seuil détection drogues
            'drug_max_score': 10.0,                 # Score max drogue
            
            # Phone Moderation
            'phone_violation_reset_hours': 48,      # Reset violations téléphone
            'phone_warning_threshold': 1,           # Seuil avant ban téléphone
        }
        
        # Charger les valeurs depuis la config
        self._load_from_config()
    
    def _load_from_config(self):
        """Charge les valeurs depuis la configuration principale."""
        timing_config = self.config.get('timing', {})
        
        # Merger avec les defaults
        for key, default_value in self.defaults.items():
            value = timing_config.get(key, default_value)
            setattr(self, key, value)
            self.logger.debug(f"Timing {key}: {value}")
    
    def get_irc_settings(self) -> Dict[str, Any]:
        """Retourne les settings IRC."""
        return {
            'connect_timeout': self.irc_connect_timeout,
            'retry_delay': self.irc_retry_delay,
            'max_retry_delay': self.irc_max_retry_delay,
            'ping_interval_seconds': self.irc_ping_interval,
            'cycle_reset_delay': self.irc_cycle_reset_delay
        }
    
    def get_moderation_settings(self) -> Dict[str, Any]:
        """Retourne les settings de modération."""
        return {
            'cooldown_minutes': self.moderation_cooldown_minutes,
            'reset_hours': self.moderation_reset_hours,
            'move_delay_seconds': self.moderation_move_delay,
            'welcome_delay_seconds': self.moderation_welcome_delay,
            'kick_delay': self.moderation_kick_delay,
            'ban_delay': self.moderation_ban_delay,
            'phone_ban_delay': self.moderation_phone_ban_delay
        }
    
    def get_temp_ban_settings(self) -> Dict[str, Any]:
        """Retourne les settings des bans temporaires."""
        return {
            'badwords_minutes': self.temp_ban_badwords_minutes,
            'nickname_seconds': self.temp_ban_nickname_seconds,
            'phone_hours': self.temp_ban_phone_hours
        }
    
    def get_health_settings(self) -> Dict[str, Any]:
        """Retourne les settings de monitoring santé."""
        return {
            'interval_minutes': self.health_check_interval_minutes,
            'openai_timeout_seconds': self.health_openai_timeout,
            'error_sleep_seconds': self.health_error_sleep
        }
    
    def get_content_analysis_settings(self) -> Dict[str, Any]:
        """Retourne les settings d'analyse contenu."""
        return {
            'behavior_window_seconds': self.content_behavior_window_hours * 3600,
            'min_request_interval': self.content_min_request_interval,
            'cache_timeout_seconds': self.content_cache_timeout_minutes * 60
        }
    
    def get_state_settings(self) -> Dict[str, Any]:
        """Retourne les settings de gestion d'état."""
        return {
            'save_interval': self.state_save_interval,
            'shutdown_timeout': self.state_shutdown_timeout
        }
    
    def get_phone_moderation_settings(self) -> Dict[str, Any]:
        """Retourne les settings spécifiques à la modération téléphone."""
        return {
            'violation_reset_hours': self.phone_violation_reset_hours,
            'warning_threshold': self.phone_warning_threshold,
            'ban_duration_hours': self.temp_ban_phone_hours
        }
    
    def get_drug_detection_settings(self) -> Dict[str, Any]:
        """Retourne les settings de détection de drogues."""
        return {
            'sensitivity': self.drug_sensitivity_threshold,
            'max_score': self.drug_max_score
        }
    
    def reload_from_config(self, new_config: Dict[str, Any]):
        """Recharge la configuration depuis un nouveau dict."""
        self.config = new_config
        self._load_from_config()
        self.logger.info("Configuration timing rechargée")
    
    def validate_config(self) -> List[str]:
        """Valide la configuration et retourne les erreurs trouvées."""
        errors = []
        
        # Vérifications basiques
        if self.irc_connect_timeout <= 0:
            errors.append("irc_connect_timeout doit être > 0")
        
        if self.moderation_cooldown_minutes < 0:
            errors.append("moderation_cooldown_minutes doit être >= 0")
        
        if self.health_check_interval_minutes <= 0:
            errors.append("health_check_interval_minutes doit être > 0")
        
        if not (0 < self.cache_cleanup_ratio <= 1):
            errors.append("cache_cleanup_ratio doit être entre 0 et 1")
        
        if self.drug_sensitivity_threshold < 0 or self.drug_sensitivity_threshold > 10:
            errors.append("drug_sensitivity_threshold doit être entre 0 et 10")
        
        return errors
    
    def get_all_timings(self) -> Dict[str, Any]:
        """Retourne toutes les configurations de timing."""
        result = {}
        for key in self.defaults.keys():
            result[key] = getattr(self, key)
        return result
    
    def __str__(self) -> str:
        """Représentation string de la config."""
        return f"TimingConfig({len(self.defaults)} settings)"


# Fonction utilitaire pour créer une instance
def create_timing_config(main_config: Dict[str, Any]) -> TimingConfig:
    """Crée une instance TimingConfig depuis la config principale."""
    return TimingConfig(main_config)


if __name__ == "__main__":
    # Test basique
    test_config = {
        'timing': {
            'irc_connect_timeout': 45,
            'moderation_cooldown_minutes': 3
        }
    }
    
    timing = TimingConfig(test_config)
    print(f"IRC timeout: {timing.irc_connect_timeout}")
    print(f"Moderation cooldown: {timing.moderation_cooldown_minutes}")
    print(f"Errors: {timing.validate_config()}")
    print("TimingConfig test OK")