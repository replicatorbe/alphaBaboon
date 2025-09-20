import irc.bot
import irc.strings
import irc.connection
import ssl
import logging
import time
from threading import Timer
from badwords_filter import BadWordsFilter
from nickname_filter import NicknameFilter

# Configure encoding error handling for IRC
import irc.client
import jaraco.stream.buffer

# Global configuration to handle encoding errors more gracefully
def patch_irc_encoding():
    """Patch IRC library to handle encoding errors more gracefully."""
    try:
        # Simple and safe approach: just catch UnicodeDecodeError in the reactor
        if hasattr(irc.client, 'Reactor'):
            original_process_data = irc.client.Reactor.process_data
            
            def robust_process_data(self, sockets):
                """Process data with UTF-8 error handling."""
                try:
                    return original_process_data(self, sockets)
                except UnicodeDecodeError as e:
                    # Log the error and continue
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Erreur d'encodage UTF-8 gérée automatiquement: {e}")
                    # Return empty to continue processing
                    return
                    
            irc.client.Reactor.process_data = robust_process_data
            print("✅ Encodage IRC: Patch Reactor.process_data pour gestion des erreurs UTF-8")
            
        # Note: ServerConnection.process_data patch removed - causes signature mismatch
        # The Reactor.process_data patch above is sufficient for UTF-8 error handling
            
    except Exception as e:
        print(f"Avertissement: Impossible de patcher l'encodage IRC: {e}")

# Apply the patch immediately when module is imported
patch_irc_encoding()


class IRCClient(irc.bot.SingleServerIRCBot):
    def __init__(self, config, moderation_handler):
        self.config = config
        self.moderation_handler = moderation_handler
        self.logger = logging.getLogger(__name__)
        
        # Préparer la liste des serveurs avec SSL support
        servers = self._prepare_server_list(config['irc']['servers'])
        nickname = config['irc']['nickname']
        realname = config['irc']['realname']
        
        super().__init__(servers, nickname, realname)
        
        # Configure encoding error handling to be more tolerant
        self._configure_encoding_handling()
        
        # Initialiser le filtre de mots interdits
        self.badwords_filter = BadWordsFilter(config)
        
        # Initialiser le filtre de pseudos inappropriés
        self.nickname_filter = NicknameFilter(config)
        
        # Récupérer les canaux depuis la config fusionnée (renommer pour éviter conflit avec IRC lib)
        self.bot_channels = config['irc'].get('channels', ['#francophonie', '#adultes'])
        self.monitored_channel = config['irc'].get('monitored_channel', '#francophonie')  
        self.redirect_channel = config['irc'].get('redirect_channel', '#adultes')
        self.is_ircop = config['irc'].get('is_ircop', False)
        self.ircop_login = config['irc'].get('ircop_login')
        self.ircop_password = config['irc'].get('ircop_password')
        self.preferred_server_index = config['irc'].get('preferred_server_index', 0)
        self.connect_timeout = config['irc'].get('connect_timeout', 30)
        self.retry_delay = config['irc'].get('retry_delay', 60)
        
        self.connected = False
        self.joined_channels = set()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.current_server_index = self.preferred_server_index
        
        # Système de keepalive
        self.last_ping_time = 0
        self.ping_interval = config['irc'].get('ping_interval_seconds', 300)  # 5 minutes
        self.keepalive_timer = None

    def _prepare_server_list(self, server_configs):
        """Prépare la liste des serveurs (SSL simplifié)."""
        servers = []
        for server_config in server_configs:
            hostname = server_config['hostname']
            port = server_config['port']
            use_ssl = server_config.get('ssl', False)
            
            # Format simple tuple (hostname, port) - SSL sera géré plus tard si besoin
            servers.append((hostname, port))
            
            ssl_status = "SSL" if use_ssl else "non-SSL"
            self.logger.info(f"Serveur configuré: {hostname}:{port} ({ssl_status})")
        
        return servers

    def _configure_encoding_handling(self):
        """Configure more robust encoding handling for IRC connections."""
        try:
            # The global patches handle UnicodeDecodeError at the reactor and connection level
            self.logger.info("Configuration d'encodage: Patches de gestion des erreurs UTF-8 actifs")
            
            # Additional safety: try to set connection-level encoding if possible
            if hasattr(self, 'connection') and self.connection:
                try:
                    if hasattr(self.connection, 'buffer') and hasattr(self.connection.buffer, 'errors'):
                        self.connection.buffer.errors = 'replace'
                        self.logger.debug("Configuration d'encodage: mode 'replace' appliqué à la connexion")
                except:
                    pass  # Ignore if not possible
                    
        except Exception as e:
            self.logger.debug(f"Configuration d'encodage additionnelle ignorée: {e}")

    def on_welcome(self, connection, event):
        server_info = f"{connection.server}:{connection.port}"
        self.logger.info(f"Connecté au serveur IRC {server_info}")
        
        # S'identifier comme IRCop si configuré
        if self.is_ircop and self.ircop_login and self.ircop_password:
            connection.send_raw(f"OPER {self.ircop_login} {self.ircop_password}")
            self.logger.info("Identification IRCop envoyée")
        
        # Rejoindre tous les canaux configurés
        self.logger.info(f"Tentative de rejoindre les canaux: {self.bot_channels}")
        for channel in self.bot_channels:
            self.logger.info(f"Rejoindre le canal: {channel}")
            connection.join(channel)
            
        self.connected = True
        self.reconnect_attempts = 0
        
        # Vider les banlists au démarrage
        if hasattr(self, 'moderation_handler') and self.moderation_handler:
            for channel in self.bot_channels:
                self.moderation_handler.clear_bans_on_startup(self, channel)
        
        # Démarrer le keepalive
        self._start_keepalive()

    def on_join(self, connection, event):
        try:
            channel = event.target
            user = event.source.nick if hasattr(event.source, 'nick') else str(event.source)
            
            # Si c'est notre bot qui rejoint
            if user == self.config['irc']['nickname']:
                self.joined_channels.add(channel)
                self.logger.info(f"Bot rejoint le canal {channel}")
                
                # Se donner les privilèges d'opérateur sur les canaux de modération
                if self.is_ircop and channel in [self.monitored_channel, self.redirect_channel]:
                    connection.send_raw(f"samode {channel} +o {self.config['irc']['nickname']}")
                    self.logger.info(f"Privilèges OP demandés sur {channel} avec samode")
            else:
                self.logger.info(f"Utilisateur {user} rejoint {channel}")
                
                # Vérifier le pseudo si c'est sur #francophonie
                if self.nickname_filter.is_enabled_for_channel(channel):
                    is_inappropriate, detected_pattern = self.nickname_filter.check_nickname(user)
                    if is_inappropriate:
                        self.logger.warning(f"Pseudo inapproprié détecté: {user} sur {channel} ({detected_pattern})")
                        # Rediriger l'utilisateur vers #adultes
                        self.nickname_filter.handle_inappropriate_nickname(self, user, channel, detected_pattern)
                        return  # Arrêter le traitement pour cet utilisateur
                
        except Exception as e:
            self.logger.error(f"Erreur dans on_join: {e}")
            import traceback
            self.logger.error(f"Stack trace on_join: {traceback.format_exc()}")

    def on_pubmsg(self, connection, event):
        try:
            channel = event.target
            message = event.arguments[0] if event.arguments else ""
            sender = event.source.nick if hasattr(event.source, 'nick') else str(event.source)
            
            # Ignorer les messages du bot lui-même
            if sender == self.config['irc']['nickname']:
                return
            
            # Analyser les messages des canaux de modération
            if channel in [self.monitored_channel, self.redirect_channel]:
                self.logger.info(f"[{channel}] <{sender}> {message}")
                
                # 1. D'abord vérifier avec le filtre de mots interdits (plus rapide)
                if self.badwords_filter.is_enabled_for_channel(channel):
                    is_badword, detected_pattern = self.badwords_filter.check_message(message, sender)
                    if is_badword:
                        # Gestion progressive pour mot interdit
                        self.logger.warning(f"Mot interdit détecté de {sender} sur {channel}: {detected_pattern}")
                        self.badwords_filter.handle_violation(self, sender, channel, detected_pattern)
                        return  # Ne pas passer à l'analyse IA si violation traitée
                
                # 2. Ensuite passer à l'analyse IA si pas de mot interdit détecté
                self.moderation_handler.analyze_message(sender, message, channel, self)
            else:
                # Log les autres canaux sans analyser
                self.logger.debug(f"[{channel}] <{sender}> {message}")
        except Exception as e:
            self.logger.error(f"Erreur dans on_pubmsg: {e}")
            import traceback
            self.logger.error(f"Stack trace on_pubmsg: {traceback.format_exc()}")

    def on_disconnect(self, connection, event):
        self.logger.warning("Déconnecté du serveur IRC")
        self.connected = False
        self._stop_keepalive()
        self._schedule_reconnect()

    def on_error(self, connection, event):
        self.logger.error(f"Erreur IRC: {event.arguments}")

    def _schedule_reconnect(self):
        self.reconnect_attempts += 1
        
        # Essayer le serveur suivant dans la liste
        servers = self.config['irc']['servers']
        self.current_server_index = (self.current_server_index + 1) % len(servers)
        next_server = servers[self.current_server_index]
        
        # Reconnexion infinie avec backoff exponentiel intelligent
        if self.reconnect_attempts <= self.max_reconnect_attempts:
            # Délai normal pour les premières tentatives
            delay = min(self.retry_delay * self.reconnect_attempts, 300)  # Max 5 minutes
            cycle_info = "initial"
        else:
            # Après max_reconnect_attempts, utiliser backoff exponentiel avec reset périodique
            cycle = (self.reconnect_attempts - self.max_reconnect_attempts) // len(servers) + 1
            delay = min(300 * (2 ** min(cycle - 1, 6)), 1800)  # De 5min à 30min max
            cycle_info = f"cycle {cycle}"
            
            # Reset des tentatives tous les 10 cycles pour éviter l'overflow
            if cycle >= 10:
                self.reconnect_attempts = self.max_reconnect_attempts
                self.logger.info("Reset du compteur de tentatives pour éviter l'escalade infinie")
        
        self.logger.info(f"Reconnexion vers {next_server['hostname']}:{next_server['port']} "
                       f"dans {delay}s (tentative {self.reconnect_attempts}, {cycle_info})")
        
        Timer(delay, self._reconnect).start()

    def _reconnect(self):
        try:
            servers = self.config['irc']['servers']
            current_server = servers[self.current_server_index]
            ssl_status = "SSL" if current_server.get('ssl') else "non-SSL"
            self.logger.info(f"Tentative de reconnexion vers {current_server['hostname']}:{current_server['port']} ({ssl_status})")
            self.jump_server()
        except Exception as e:
            self.logger.error(f"Erreur lors de la reconnexion: {e}")
            self._schedule_reconnect()

    def send_message(self, channel, message):
        if self.connected:
            self.connection.privmsg(channel, message)
            self.logger.info(f"Message envoyé sur {channel}: {message}")
        else:
            self.logger.warning("Impossible d'envoyer le message: non connecté")
    
    def privmsg(self, channel, message):
        """Alias pour compatibilité avec le moderation handler."""
        self.send_message(channel, message)

    def move_user_to_adultes(self, user, reason="Contenu adulte détecté"):
        """Déplace un utilisateur vers le canal de redirection avec SAPART et SAJOIN."""
        if self.connected and self.is_ircop:
            # 1. Faire partir l'utilisateur de #francophonie avec SAPART
            self.connection.send_raw(f"SAPART {user} {self.monitored_channel} :{reason}")
            
            # 2. Le bannir temporairement pour l'empêcher de revenir immédiatement
            self.connection.send_raw(f"MODE {self.monitored_channel} +b {user}!*@*")
            
            # 3. Faire rejoindre l'utilisateur sur le canal de redirection avec SAJOIN
            self.connection.send_raw(f"SAJOIN {user} {self.redirect_channel}")
            
            # 4. Débannir après quelques secondes (pour éviter qu'il revienne direct)
            import threading
            def unban_user():
                if self.connected:
                    self.connection.send_raw(f"MODE {self.monitored_channel} -b {user}!*@*")
                    self.logger.info(f"Ban temporaire levé pour {user} sur {self.monitored_channel} (après 10 minutes)")
            threading.Timer(600.0, unban_user).start()  # Déban après 10 minutes
            
            self.logger.info(f"SAPART {user} de {self.monitored_channel} puis SAJOIN vers {self.redirect_channel}")
            return True
        else:
            self.logger.warning(f"Impossible de déplacer {user}: non connecté ou pas IRCop")
            return False
    
    def send_welcome_message_adultes(self, user):
        """Envoie un message d'accueil sympathique sur le canal de redirection."""
        # Le message sera fourni par l'appelant via le message rotator
        pass
    
    def ban_user(self, channel, user):
        """Méthode de ban classique (gardée pour compatibilité)."""
        if self.connected:
            self.connection.mode(channel, f"+b {user}!*@*")
            self.connection.kick(channel, user, "Non-respect des règles du canal")
            self.logger.info(f"Utilisateur {user} banni de {channel}")
        else:
            self.logger.warning(f"Impossible de bannir {user}: non connecté")
    
    def _start_keepalive(self):
        """Démarre le système de keepalive avec PING périodique."""
        if self.keepalive_timer:
            self.keepalive_timer.cancel()
        
        import threading
        self.keepalive_timer = threading.Timer(self.ping_interval, self._send_keepalive_ping)
        self.keepalive_timer.daemon = True
        self.keepalive_timer.start()
        self.logger.debug(f"Keepalive démarré (PING toutes les {self.ping_interval}s)")
    
    def _stop_keepalive(self):
        """Arrête le système de keepalive."""
        if self.keepalive_timer:
            self.keepalive_timer.cancel()
            self.keepalive_timer = None
            self.logger.debug("Keepalive arrêté")
    
    def _send_keepalive_ping(self):
        """Envoie un PING au serveur pour maintenir la connexion."""
        if self.connected:
            try:
                # Envoyer PING au serveur actuel
                servers = self.config['irc']['servers']
                current_server = servers[self.current_server_index]
                ping_target = current_server['hostname']
                
                self.connection.ping(ping_target)
                self.last_ping_time = time.time()
                self.logger.debug(f"PING envoyé vers {ping_target}")
                
                # Programmer le prochain ping
                self._start_keepalive()
                
            except Exception as e:
                self.logger.warning(f"Erreur lors du PING keepalive: {e}")
                # Si le PING échoue, considérer que la connexion est morte
                self.logger.warning("Connexion potentiellement morte, forçage de la reconnexion")
                self.connected = False
                self._schedule_reconnect()
        else:
            self.logger.debug("PING annulé - non connecté")
    
    def on_pong(self, connection, event):
        """Gestionnaire pour les réponses PONG du serveur."""
        if self.last_ping_time > 0:
            response_time = time.time() - self.last_ping_time
            self.logger.debug(f"PONG reçu en {response_time:.2f}s")
        else:
            self.logger.debug("PONG reçu")
    
    def get_badwords_stats(self):
        """Retourne les statistiques du filtre de mots interdits."""
        if hasattr(self, 'badwords_filter'):
            return self.badwords_filter.get_stats()
        return {"error": "Filtre de mots interdits non initialisé"}
    
    def get_nickname_stats(self):
        """Retourne les statistiques du filtre de pseudos."""
        if hasattr(self, 'nickname_filter'):
            return self.nickname_filter.get_stats()
        return {"error": "Filtre de pseudos non initialisé"}