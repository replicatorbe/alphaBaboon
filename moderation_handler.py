import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List
from content_analyzer import ContentAnalyzer
from message_rotator import MessageRotator
from phone_moderator import PhoneModerator


class ModerationHandler:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.content_analyzer = ContentAnalyzer(config)
        self.message_rotator = MessageRotator(config)
        self.phone_moderator = PhoneModerator(config)
        
        # Stockage des infractions par utilisateur
        self.user_violations: Dict[str, List[datetime]] = {}
        
        # Configuration de modération
        self.reset_hours = config['moderation']['reset_hours']
        self.cooldown_minutes = config['moderation']['cooldown_minutes']
        self.move_delay = config['moderation'].get('move_delay_seconds', 3)
        self.welcome_delay = config['moderation'].get('welcome_delay_seconds', 5)
        
        # Dernière action par utilisateur pour éviter le spam de modération
        self.last_action: Dict[str, datetime] = {}

    def analyze_message(self, sender: str, message: str, channel: str, irc_connection):
        """Analyse un message et applique les sanctions si nécessaire."""
        try:
            # 1. Vérifier les numéros de téléphone (priorité car applicable partout)
            has_phone, phone_action = self.phone_moderator.check_phone_numbers(message, sender, channel)
            
            if has_phone and phone_action and phone_action['action'] != 'none':
                self._handle_phone_violation(sender, channel, irc_connection, phone_action)
                return  # Arrêter ici car numéro détecté
            
            # 2. Vérifier le cooldown pour éviter le spam de modération adulte
            if not self._can_moderate_user(sender):
                return
            
            # 3. Analyser le contenu adulte avec OpenAI (inclut cache, whitelist, keywords)  
            is_adult_content, confidence_score = self.content_analyzer.analyze_message(message, sender)
            
            if is_adult_content:
                self.logger.warning(f"Contenu adulte détecté de {sender}: {message[:100]}... (score: {confidence_score})")
                self._handle_violation(sender, channel, irc_connection, confidence_score)
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse du message de {sender}: {e}")

    def _can_moderate_user(self, user: str) -> bool:
        """Vérifie si on peut modérer un utilisateur (cooldown)."""
        if user not in self.last_action:
            return True
        
        last_action_time = self.last_action[user]
        cooldown = timedelta(minutes=self.cooldown_minutes)
        
        return datetime.now() - last_action_time > cooldown

    def _handle_violation(self, user: str, channel: str, irc_connection, confidence_score: float):
        """Gère une violation en déplaçant l'utilisateur vers #adultes."""
        current_time = datetime.now()
        
        # Nettoyer les anciennes violations
        self._clean_old_violations(user, current_time)
        
        # Ajouter la nouvelle violation
        if user not in self.user_violations:
            self.user_violations[user] = []
        self.user_violations[user].append(current_time)
        
        violation_count = len(self.user_violations[user])
        
        self.logger.info(f"Violation #{violation_count} pour {user} (score: {confidence_score})")
        
        # Toujours déplacer vers #adultes de manière sympathique
        self._redirect_to_adultes(user, channel, irc_connection)
        
        # Mettre à jour le timestamp de la dernière action
        self.last_action[user] = current_time

    def _clean_old_violations(self, user: str, current_time: datetime):
        """Supprime les violations anciennes (reset après 24h)."""
        if user not in self.user_violations:
            return
        
        reset_threshold = current_time - timedelta(hours=self.reset_hours)
        self.user_violations[user] = [
            violation_time for violation_time in self.user_violations[user]
            if violation_time > reset_threshold
        ]
        
        # Supprimer l'utilisateur s'il n'a plus de violations récentes
        if not self.user_violations[user]:
            del self.user_violations[user]
            if user in self.last_action:
                del self.last_action[user]
            self.logger.info(f"Compteur de violations réinitialisé pour {user}")

    def _redirect_to_adultes(self, user: str, channel: str, irc_connection):
        """Déplace un utilisateur vers le canal de redirection de manière sympathique."""
        import threading
        
        # Message sympathique et varié avant le déplacement
        redirect_msg = self.message_rotator.get_redirect_message(user)
        irc_connection.privmsg(channel, redirect_msg)
        
        # Programmer le déplacement après quelques secondes
        def move_user():
            success = irc_connection.move_user_to_adultes(user, f"Discussion plus appropriée sur {irc_connection.redirect_channel} 😊")
            if success:
                # Programmer le message d'accueil personnalisé
                def send_welcome():
                    welcome_msg = self.message_rotator.get_welcome_message(user)
                    irc_connection.send_message(irc_connection.redirect_channel, welcome_msg)
                
                threading.Timer(self.welcome_delay, send_welcome).start()
        
        threading.Timer(self.move_delay, move_user).start()
        
        self.logger.info(f"Redirection programmée pour {user} vers {irc_connection.redirect_channel}")
    
    def _handle_phone_violation(self, user: str, channel: str, irc_connection, phone_action: dict):
        """Gère une violation de numéro de téléphone."""
        import threading
        
        action_type = phone_action['action']
        message = phone_action['message']
        numbers = phone_action['numbers']
        
        if action_type == 'warn':
            # Envoyer l'avertissement sympathique
            irc_connection.privmsg(channel, message)
            self.logger.info(f"Avertissement numéro envoyé à {user} sur {channel}")
            
        elif action_type == 'ban':
            # Envoyer le message d'explication du ban
            irc_connection.privmsg(channel, message)
            
            # Programmer le ban après quelques secondes
            def apply_ban():
                try:
                    # Commande samode pour mettre en sourdine (sans /)
                    ban_command = f"samode {channel} +b {user}!*@*"
                    irc_connection.connection.send_raw(ban_command)
                    
                    self.logger.warning(f"Ban appliqué: {user} sur {channel} pour numéros de téléphone")
                    
                    # Message d'explication après le ban
                    explanation = f"{user} a été mis en sourdine temporairement pour non-respect des règles (numéros de téléphone en public). Ban automatique pendant {phone_action.get('ban_duration_hours', 24)}h."
                    irc_connection.privmsg(channel, explanation)
                    
                except Exception as e:
                    self.logger.error(f"Erreur lors du ban de {user}: {e}")
            
            # Appliquer le ban après 3 secondes
            threading.Timer(3.0, apply_ban).start()

    def get_user_status(self, user: str) -> Dict:
        """Retourne le statut d'un utilisateur pour debugging."""
        current_time = datetime.now()
        self._clean_old_violations(user, current_time)
        
        violation_count = len(self.user_violations.get(user, []))
        last_action = self.last_action.get(user)
        can_moderate = self._can_moderate_user(user)
        
        return {
            'user': user,
            'violation_count': violation_count,
            'last_action': last_action.isoformat() if last_action else None,
            'can_moderate': can_moderate,
            'violations': [v.isoformat() for v in self.user_violations.get(user, [])]
        }