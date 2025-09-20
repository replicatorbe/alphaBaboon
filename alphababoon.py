#!/usr/bin/env python3
"""
AlphaBaboon - Bot de modération automatique IRC
Surveille le canal #francophonie et redirige le contenu adulte vers #adultes
"""

import json
import os
import sys
import signal
import time
import threading
import logging
from pathlib import Path

from logger_config import setup_logging, log_startup_info, log_shutdown_info
from irc_client import IRCClient
from advanced_moderation_handler import AdvancedModerationHandler
from healthcheck import HealthChecker
from state_manager import StateManager


class AlphaBaboonBot:
    def __init__(self, config_path='config.json', secret_config_path='config_secret.json'):
        self.config_path = config_path
        self.secret_config_path = secret_config_path
        self.config = None
        self.irc_client = None
        self.moderation_handler = None
        self.health_checker = None
        self.state_manager = None
        self.running = False
        self.logger = None
        
        # Gestion des signaux pour arrêt propre
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Gestion propre des signaux d'arrêt."""
        if self.logger:
            self.logger.info(f"Signal {signum} reçu, arrêt en cours...")
        self.shutdown()

    def load_config(self):
        """Charge la configuration depuis les fichiers JSON."""
        try:
            # Charger la configuration publique
            config_file = Path(self.config_path)
            if not config_file.exists():
                raise FileNotFoundError(f"Fichier de configuration non trouvé: {self.config_path}")
            
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            # Charger la configuration secrète
            secret_config_file = Path(self.secret_config_path)
            if not secret_config_file.exists():
                raise FileNotFoundError(f"Fichier de configuration secrète non trouvé: {self.secret_config_path}")
            
            with open(secret_config_file, 'r', encoding='utf-8') as f:
                secret_config = json.load(f)
            
            # Fusionner les configurations (secret écrase public)
            self._merge_configs(secret_config)
            
            # Validation de la configuration
            self._validate_config()
            
            print(f"Configuration chargée depuis {self.config_path} et {self.secret_config_path}")
            return True
            
        except Exception as e:
            print(f"Erreur lors du chargement de la configuration: {e}")
            return False

    def _merge_configs(self, secret_config):
        """Fusionne la configuration secrète avec la configuration publique."""
        def deep_merge(base, override):
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value
        
        deep_merge(self.config, secret_config)

    def _validate_config(self):
        """Valide que la configuration contient tous les champs requis."""
        required_fields = {
            'irc': ['servers', 'nickname', 'realname', 'channels', 'monitored_channel', 'redirect_channel'],
            'openai': ['api_key'],
            'moderation': ['sensitivity', 'reset_hours', 'cooldown_minutes']
        }
        
        for section, fields in required_fields.items():
            if section not in self.config:
                raise ValueError(f"Section manquante dans la configuration: {section}")
            
            for field in fields:
                if field not in self.config[section]:
                    raise ValueError(f"Champ manquant dans la configuration: {section}.{field}")
        
        # Vérifier que la clé API OpenAI est configurée
        if self.config['openai']['api_key'].startswith('sk-votre-cle') or self.config['openai']['api_key'] == 'VOTRE_CLE_API':
            raise ValueError("Veuillez configurer votre vraie clé API OpenAI dans config_secret.json")
        
        # Vérifier la configuration des serveurs IRC
        if not self.config['irc']['servers']:
            raise ValueError("Au moins un serveur IRC doit être configuré")
        
        for i, server in enumerate(self.config['irc']['servers']):
            if 'hostname' not in server:
                raise ValueError(f"Serveur {i}: hostname manquant")
            if 'port' not in server:
                raise ValueError(f"Serveur {i}: port manquant")
            if not isinstance(server['port'], int) or server['port'] <= 0:
                raise ValueError(f"Serveur {i}: port invalide")

    def initialize(self):
        """Initialise tous les composants du bot."""
        try:
            # Configuration du logging
            setup_logging()
            self.logger = logging.getLogger(__name__)
            log_startup_info()
            
            # Initialisation du gestionnaire de modération
            self.moderation_handler = AdvancedModerationHandler(self.config)
            
            # Initialisation du gestionnaire d'état
            self.state_manager = StateManager(self.config)
            self.state_manager.set_moderation_handler(self.moderation_handler)
            
            # Restaurer l'état si disponible
            self.state_manager.restore_state()
            
            # Initialisation du client IRC
            self.irc_client = IRCClient(self.config, self.moderation_handler)
            
            # Initialisation du healthcheck
            self.health_checker = HealthChecker(
                self.config, 
                self.irc_client, 
                self.moderation_handler.content_analyzer
            )
            
            self.logger.info("Tous les composants initialisés avec succès")
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Erreur lors de l'initialisation: {e}")
            else:
                print(f"Erreur lors de l'initialisation: {e}")
            return False

    def start(self):
        """Démarre le bot IRC."""
        if not self.config:
            print("Configuration non chargée. Appelez load_config() d'abord.")
            return False
        
        if not self.initialize():
            return False
        
        try:
            self.logger.info("Démarrage du bot AlphaBaboon...")
            
            # Afficher les serveurs configurés
            servers = self.config['irc']['servers']
            preferred_idx = self.config['irc'].get('preferred_server_index', 0)
            if preferred_idx < len(servers):
                preferred_server = servers[preferred_idx]
                ssl_status = "SSL" if preferred_server.get('ssl') else "non-SSL"
                self.logger.info(f"Serveur principal: {preferred_server['hostname']}:{preferred_server['port']} ({ssl_status})")
            
            self.logger.info(f"Serveurs de fallback: {len(servers)-1}")
            self.logger.info(f"Canaux rejoints: {', '.join(self.config['irc'].get('channels', []))}")
            self.logger.info(f"Mode IRCop: {'Activé' if self.config['irc'].get('is_ircop') else 'Désactivé'}")
            
            self.running = True
            
            # Démarrer le healthcheck
            self.health_checker.start_monitoring()
            
            # Démarrer la sauvegarde automatique d'état
            self.state_manager.start_auto_save()
            
            # Démarrer le client IRC dans un thread séparé
            irc_thread = threading.Thread(target=self._run_irc_client, daemon=True)
            irc_thread.start()
            
            # Boucle principale de surveillance
            self._main_loop()
            
        except Exception as e:
            self.logger.error(f"Erreur lors du démarrage: {e}")
            return False
        
        return True

    def _run_irc_client(self):
        """Exécute le client IRC dans un thread séparé."""
        try:
            self.irc_client.start()
        except UnicodeDecodeError as e:
            self.logger.error(f"Erreur d'encodage dans le client IRC: {e}")
            self.logger.info("Tentative de redémarrage automatique du client IRC...")
            # Attendre un peu avant de redémarrer
            import time
            time.sleep(10)
            if self.running:
                # Redémarrer le client IRC automatiquement
                try:
                    from irc_client import IRCClient
                    self.irc_client = IRCClient(self.config, self.moderation_handler)
                    self._run_irc_client()
                except Exception as restart_error:
                    self.logger.error(f"Impossible de redémarrer le client IRC: {restart_error}")
                    self.running = False
        except Exception as e:
            self.logger.error(f"Erreur dans le client IRC: {e}")
            import traceback
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
            self.running = False

    def _main_loop(self):
        """Boucle principale de surveillance."""
        last_stats_time = time.time()
        stats_interval = 3600  # Statistiques toutes les heures
        
        while self.running:
            try:
                time.sleep(5)  # Pause de 5 secondes
                
                # Afficher des statistiques périodiquement
                current_time = time.time()
                if current_time - last_stats_time > stats_interval:
                    self._log_statistics()
                    last_stats_time = current_time
                
                # Vérifier que le client IRC est toujours connecté
                if not self.irc_client.connected:
                    self.logger.warning("Client IRC déconnecté, tentative de reconnexion...")
                
            except KeyboardInterrupt:
                self.logger.info("Interruption clavier détectée")
                break
            except Exception as e:
                self.logger.error(f"Erreur dans la boucle principale: {e}")
                time.sleep(10)  # Attendre avant de continuer

    def _log_statistics(self):
        """Log des statistiques de fonctionnement."""
        if self.moderation_handler:
            active_users = len(self.moderation_handler.user_violations)
            total_violations = sum(len(violations) for violations in self.moderation_handler.user_violations.values())
            
            # Statistiques du cache
            cache_stats = self.moderation_handler.content_analyzer.get_cache_stats()
            
            # Statistiques du filtre de mots interdits
            badwords_stats = self.irc_client.get_badwords_stats() if self.irc_client else {}
            badwords_detections = badwords_stats.get('detections_count', 0)
            badwords_bans = badwords_stats.get('banned_users_count', 0)
            
            # Statistiques du filtre de pseudos
            nickname_stats = self.irc_client.get_nickname_stats() if self.irc_client else {}
            nickname_detections = nickname_stats.get('detections_count', 0)
            nickname_redirects = nickname_stats.get('redirected_users_count', 0)
            
            # Rapport de santé
            health_report = self.health_checker.get_health_report() if self.health_checker else {"overall_health": "Unknown"}
            
            self.logger.info(f"Stats: {active_users} users, {total_violations} violations IA, "
                           f"{badwords_detections} détections mots, {badwords_bans} bans mots, "
                           f"{nickname_detections} pseudos inappropriés, {nickname_redirects} redirections, "
                           f"Cache: {cache_stats.get('hit_rate_percent', 0)}% hit rate, "
                           f"Économies: ${cache_stats.get('total_savings_usd', 0)}, "
                           f"Santé: {'OK' if health_report['overall_health'] else 'PROBLÈME'}")

    def shutdown(self):
        """Arrêt propre du bot."""
        if not self.running:
            return
        
        self.running = False
        
        if self.logger:
            self.logger.info("Arrêt du bot en cours...")
        
        # Arrêter le healthcheck
        if self.health_checker:
            self.health_checker.stop_monitoring()
        
        # Arrêter la sauvegarde automatique
        if self.state_manager:
            self.state_manager.stop_auto_save()
        
        if self.irc_client:
            try:
                self.irc_client.disconnect("Bot en arrêt")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Erreur lors de la déconnexion IRC: {e}")
        
        if self.logger:
            log_shutdown_info()
        
        print("AlphaBaboon arrêté.")

    def status(self):
        """Affiche le statut actuel du bot."""
        if not self.running:
            print("Bot: Arrêté")
            return
        
        connected = self.irc_client.connected if self.irc_client else False
        print(f"Bot: En fonctionnement")
        print(f"IRC: {'Connecté' if connected else 'Déconnecté'}")
        
        if self.moderation_handler:
            active_users = len(self.moderation_handler.user_violations)
            print(f"Utilisateurs surveillés: {active_users}")


def main():
    """Point d'entrée principal."""
    print("AlphaBaboon - Bot de modération IRC")
    print("=" * 50)
    
    # Vérifier que le fichier de config existe
    config_path = 'config.json'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    
    # Créer et démarrer le bot
    bot = AlphaBaboonBot(config_path)
    
    if not bot.load_config():
        print("Impossible de charger la configuration. Arrêt.")
        sys.exit(1)
    
    if not bot.start():
        print("Impossible de démarrer le bot. Arrêt.")
        sys.exit(1)


if __name__ == "__main__":
    main()