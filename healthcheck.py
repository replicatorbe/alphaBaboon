import logging
import time
import threading
import openai
from datetime import datetime, timedelta
from typing import Optional


class HealthChecker:
    def __init__(self, config, irc_client=None, content_analyzer=None):
        self.config = config
        self.irc_client = irc_client
        self.content_analyzer = content_analyzer
        self.logger = logging.getLogger(__name__)
        
        # Configuration du healthcheck
        self.check_interval = config['healthcheck'].get('interval_minutes', 5) * 60
        self.openai_timeout = config['healthcheck'].get('openai_timeout_seconds', 10)
        self.max_consecutive_failures = config['healthcheck'].get('max_failures', 3)
        
        # État du healthcheck
        self.is_running = False
        self.last_check_time = None
        self.consecutive_failures = {
            'irc': 0,
            'openai': 0
        }
        self.health_status = {
            'irc': True,
            'openai': True,
            'overall': True
        }
        
        # Thread de monitoring
        self.health_thread = None

    def start_monitoring(self):
        """Démarre le monitoring de santé."""
        if self.is_running:
            return
        
        self.is_running = True
        self.health_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.health_thread.start()
        self.logger.info("Monitoring de santé démarré")

    def stop_monitoring(self):
        """Arrête le monitoring de santé."""
        self.is_running = False
        if self.health_thread:
            self.health_thread.join(timeout=5)
        self.logger.info("Monitoring de santé arrêté")

    def _monitoring_loop(self):
        """Boucle principale de monitoring."""
        while self.is_running:
            try:
                self._perform_health_checks()
                self.last_check_time = datetime.now()
                
                # Attendre avant le prochain check
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Erreur dans la boucle de healthcheck: {e}")
                time.sleep(30)  # Attendre 30s en cas d'erreur

    def _perform_health_checks(self):
        """Effectue tous les checks de santé."""
        # Check IRC
        irc_healthy = self._check_irc_health()
        self._update_health_status('irc', irc_healthy)
        
        # Check OpenAI
        openai_healthy = self._check_openai_health()
        self._update_health_status('openai', openai_healthy)
        
        # Évaluer l'état général
        overall_health = irc_healthy and openai_healthy
        self.health_status['overall'] = overall_health
        
        # Log du statut
        if overall_health:
            self.logger.debug("Healthcheck: Tous les services sont opérationnels")
        else:
            services_down = [
                service for service, status in self.health_status.items() 
                if not status and service != 'overall'
            ]
            self.logger.warning(f"Healthcheck: Services en panne: {', '.join(services_down)}")

    def _check_irc_health(self) -> bool:
        """Vérifie l'état de la connexion IRC."""
        if not self.irc_client:
            return False
        
        try:
            # Vérifier la connexion de base
            if not self.irc_client.connected:
                self.logger.warning("IRC: Connexion fermée")
                return False
            
            # Vérifier que les canaux sont rejoints
            expected_channels = set(self.config['irc']['channels'])
            joined_channels = self.irc_client.joined_channels
            
            if not expected_channels.issubset(joined_channels):
                missing = expected_channels - joined_channels
                self.logger.warning(f"IRC: Canaux manquants: {', '.join(missing)}")
                return False
            
            # Test de ping si possible (optionnel)
            # Note: Certains serveurs IRC ne répondent pas aux PING des bots
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors du check IRC: {e}")
            return False

    def _check_openai_health(self) -> bool:
        """Vérifie l'état de l'API OpenAI."""
        if not self.content_analyzer:
            return False
        
        try:
            # Test avec l'API Moderation (gratuite et plus rapide)
            test_message = "test de santé du bot"
            start_time = time.time()
            
            # Utiliser l'API Moderation pour tester
            response = self.content_analyzer.client.moderations.create(
                input=test_message,
                model="omni-moderation-latest"
            )
            
            elapsed_time = time.time() - start_time
            
            if elapsed_time > self.openai_timeout:
                self.logger.warning(f"OpenAI Moderation: Réponse trop lente ({elapsed_time:.2f}s)")
                return False
            
            # Vérifier que la réponse est valide
            if not response.results or len(response.results) == 0:
                self.logger.warning("OpenAI Moderation: Réponse vide")
                return False
            
            result = response.results[0]
            if not hasattr(result, 'categories'):
                self.logger.warning("OpenAI Moderation: Structure de réponse invalide")
                return False
            
            self.logger.debug(f"OpenAI Moderation: Check réussi en {elapsed_time:.2f}s")
            return True
            
        except openai.RateLimitError:
            self.logger.warning("OpenAI: Limite de taux atteinte")
            return False
        except openai.APIError as e:
            self.logger.error(f"OpenAI: Erreur API: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Erreur lors du check OpenAI: {e}")
            return False

    def _update_health_status(self, service: str, is_healthy: bool):
        """Met à jour le statut de santé d'un service."""
        if service not in self.consecutive_failures:
            self.consecutive_failures[service] = 0
            
        previous_status = self.health_status.get(service, True)
        self.health_status[service] = is_healthy
        
        if is_healthy:
            if self.consecutive_failures[service] > 0:
                self.logger.info(f"{service.upper()}: Service rétabli après {self.consecutive_failures[service]} échecs")
            self.consecutive_failures[service] = 0
        else:
            self.consecutive_failures[service] += 1
            
            if self.consecutive_failures[service] >= self.max_consecutive_failures:
                if previous_status:  # Première fois qu'on passe en panne
                    self.logger.error(f"{service.upper()}: Service déclaré en panne ({self.consecutive_failures[service]} échecs consécutifs)")
                    self._handle_service_failure(service)

    def _handle_service_failure(self, service: str):
        """Gère la panne d'un service."""
        if service == 'irc' and self.irc_client:
            self.logger.info("Tentative de reconnexion IRC...")
            try:
                # Forcer une reconnexion IRC
                self.irc_client._schedule_reconnect()
            except Exception as e:
                self.logger.error(f"Erreur lors de la reconnexion IRC: {e}")
        
        elif service == 'openai':
            self.logger.warning("Service OpenAI en panne - mode dégradé activé")
            # En mode dégradé, seuls les mots-clés seront utilisés

    def get_health_report(self) -> dict:
        """Retourne un rapport détaillé de l'état de santé."""
        return {
            'timestamp': datetime.now().isoformat(),
            'last_check': self.last_check_time.isoformat() if self.last_check_time else None,
            'overall_health': self.health_status['overall'],
            'services': {
                'irc': {
                    'healthy': self.health_status['irc'],
                    'consecutive_failures': self.consecutive_failures['irc'],
                    'connected': self.irc_client.connected if self.irc_client else False,
                    'joined_channels': list(self.irc_client.joined_channels) if self.irc_client else []
                },
                'openai': {
                    'healthy': self.health_status['openai'],
                    'consecutive_failures': self.consecutive_failures['openai'],
                    'cache_stats': self.content_analyzer.get_cache_stats() if self.content_analyzer else {}
                }
            }
        }

    def is_healthy(self) -> bool:
        """Retourne True si tous les services sont sains."""
        return self.health_status['overall']