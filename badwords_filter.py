"""
Module de filtrage des mots interdits pour la modération automatique
Détection rapide et précise sans IA pour sanctionner immédiatement
"""

import re
import logging
import time
import threading
from typing import List, Tuple, Optional, Dict
from collections import defaultdict


class BadWordsFilter:
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Liste des mots interdits avec patterns (précis pour éviter faux positifs)
        self.badwords = [
            "*fuck*",
            "*encul*",
            "*grosse*merd*",
            "*fil*pute*",
            "*te*baise*",
            "*faire foutre*",
            "*faire baiser*",
            "*gros*lard*",
            "*bougnoule*",
            "*sal*maracain*",
            "*connard*",
            "*conar*",
            "*fils*pute*",
            "*bougnoume*",
            "*sal*noir*",
            "*arabe*merde*",
            "*enfoir*",
            "*abruti*",
            "*salaud*",
            "*stupide*",
            "*connasse*",
            "*branle*",
            "*bouffon*",
            "*boufon*",
            "*baise ta*",
            "*baise ton*",
            "*sodomise*",
            "*venez sur*",
            "*sperme*",
            "*ta gueule*",
            "*server -m*",
            "*j*envi*sex*",
            "*salop*",
            "*pucel*",
            "*suceu*",
            "*va baiser ta mere*",
            "*vais baiser ta*",
            "*faire sucer*",
            # Patterns avec espaces pour éviter faux positifs
            " cons ",
            " puta ",
            " sexe ",
            " pute ",
            " nique ",
            " bite ",
            " pd ",
            " tamer ",
            " je suce ",
            " tu suce ",
            " couille "
        ]
        
        # Pré-compiler tous les patterns regex pour une détection ultra-rapide
        self.compiled_patterns = []
        self.pattern_cache = {}  # Cache pour éviter recompilation
        self._compile_patterns_optimized()
        
        # Configuration du filtre
        filter_config = config.get('badwords_filter', {})
        self.enabled = filter_config.get('enabled', True)
        self.monitored_channels = filter_config.get('channels', ['#francophonie'])
        self.immediate_ban = filter_config.get('immediate_ban', True)
        self.send_warning_message = filter_config.get('send_warning_message', True)
        self.log_detections = filter_config.get('log_detections', True)
        
        # Canal principal surveillé (pour compatibilité)
        self.monitored_channel = config['irc'].get('monitored_channel', '#francophonie')
        
        # Système de violations progressives
        self.user_violations = defaultdict(list)  # {user: [timestamps]}
        self.user_warnings = defaultdict(int)     # {user: warning_count}
        self.banned_users_temp = {}              # {user: unban_timestamp}
        
        # Configuration des sanctions
        self.warning_threshold_1 = 1  # Première violation = avertissement
        self.warning_threshold_2 = 2  # Deuxième violation = kick
        self.ban_threshold = 3        # Troisième violation = ban 10 min
        self.ban_duration_minutes = 10
        self.violation_reset_hours = 2  # Reset des violations après 2h (plus sympa)
        
        # Statistiques
        self.detections_count = 0
        self.banned_users = set()
        
        status = "activé" if self.enabled else "désactivé"
        self.logger.info(f"Filtre de mots interdits {status} avec {len(self.badwords)} patterns sur {self.monitored_channels}")
        self.logger.info(f"Sanctions: 1ère violation=avertissement, 2ème=kick, 3ème=ban {self.ban_duration_minutes}min (reset {self.violation_reset_hours}h)")

    def _compile_patterns_optimized(self):
        """Compile les patterns en expressions régulières optimisées."""
        compilation_start = time.time()
        compiled_count = 0
        
        # Grouper les patterns par type pour optimisation
        wildcard_patterns = []
        exact_patterns = []
        
        for pattern in self.badwords:
            if '*' in pattern:
                wildcard_patterns.append(pattern)
            else:
                exact_patterns.append(pattern)
        
        # Compiler les patterns avec wildcards
        for pattern in wildcard_patterns:
            try:
                if pattern in self.pattern_cache:
                    compiled = self.pattern_cache[pattern]
                else:
                    # Pattern avec wildcards : * devient .*? (non-greedy)
                    escaped = re.escape(pattern).replace('\\*', '.*?')
                    compiled = re.compile(escaped, re.IGNORECASE | re.UNICODE)
                    self.pattern_cache[pattern] = compiled
                
                self.compiled_patterns.append((pattern, compiled))
                compiled_count += 1
                
            except re.error as e:
                self.logger.warning(f"Pattern wildcard invalide '{pattern}': {e}")
        
        # Compiler les patterns exactes - optimisation : un seul regex pour tous
        if exact_patterns:
            try:
                # Créer un pattern combiné pour les recherches exactes (plus rapide)
                escaped_exact = [re.escape(p) for p in exact_patterns]
                combined_pattern = '|'.join(f'({escaped})' for escaped in escaped_exact)
                combined_regex = re.compile(combined_pattern, re.IGNORECASE | re.UNICODE)
                
                # Ajouter chaque pattern individuel pour le reporting
                for pattern in exact_patterns:
                    escaped = re.escape(pattern)
                    compiled = re.compile(escaped, re.IGNORECASE | re.UNICODE)
                    self.compiled_patterns.append((pattern, compiled))
                    compiled_count += 1
                
                # Stocker le regex combiné pour usage futur si besoin
                self.combined_exact_regex = combined_regex
                
            except re.error as e:
                self.logger.warning(f"Erreur compilation patterns exacts: {e}")
                # Fallback : compilation individuelle
                for pattern in exact_patterns:
                    try:
                        escaped = re.escape(pattern)
                        compiled = re.compile(escaped, re.IGNORECASE | re.UNICODE)
                        self.compiled_patterns.append((pattern, compiled))
                        compiled_count += 1
                    except re.error as pe:
                        self.logger.warning(f"Pattern exact invalide '{pattern}': {pe}")
        
        compilation_time = time.time() - compilation_start
        self.logger.info(f"Optimisation regex: {compiled_count} patterns compilés en {compilation_time:.3f}s")
    
    def _compile_patterns(self):
        """Ancienne méthode - gardée pour compatibilité."""
        return self._compile_patterns_optimized()

    def check_message(self, message: str, sender: str) -> Tuple[bool, Optional[str]]:
        """
        Vérifie si un message contient des mots interdits.
        
        Args:
            message: Le message à analyser
            sender: L'expéditeur du message
            
        Returns:
            Tuple (est_interdit, pattern_détecté)
        """
        if not message or not message.strip() or not self.enabled:
            return False, None
        
        # Normaliser le message (espaces multiples, etc.)
        normalized_message = ' '.join(message.split()).lower()
        
        # Tester chaque pattern
        for original_pattern, compiled_pattern in self.compiled_patterns:
            try:
                if compiled_pattern.search(normalized_message):
                    self.detections_count += 1
                    if self.log_detections:
                        self.logger.warning(f"Mot interdit détecté de {sender}: pattern '{original_pattern}' dans '{message[:100]}...'")
                    return True, original_pattern
                    
            except Exception as e:
                self.logger.error(f"Erreur lors de la vérification du pattern '{original_pattern}': {e}")
                continue
        
        return False, None

    def _clean_old_violations(self, user: str):
        """Nettoie les anciennes violations (plus de 2h)."""
        current_time = time.time()
        cutoff_time = current_time - (self.violation_reset_hours * 3600)
        
        if user in self.user_violations:
            # Garder seulement les violations récentes
            recent_violations = [t for t in self.user_violations[user] if t > cutoff_time]
            self.user_violations[user] = recent_violations
            
            # Mettre à jour le compteur d'avertissements
            self.user_warnings[user] = len(recent_violations)

    def _is_user_temp_banned(self, user: str) -> bool:
        """Vérifie si l'utilisateur est temporairement banni."""
        if user in self.banned_users_temp:
            unban_time = self.banned_users_temp[user]
            if time.time() < unban_time:
                return True
            else:
                # Le ban a expiré, le supprimer
                del self.banned_users_temp[user]
                self.logger.info(f"Ban temporaire expiré pour {user}")
        return False

    def _add_violation(self, user: str):
        """Ajoute une violation pour l'utilisateur."""
        current_time = time.time()
        self.user_violations[user].append(current_time)
        self.user_warnings[user] = len(self.user_violations[user])

    def _get_violation_count(self, user: str) -> int:
        """Retourne le nombre de violations récentes pour l'utilisateur."""
        self._clean_old_violations(user)
        return self.user_warnings.get(user, 0)

    def handle_violation(self, irc_client, user: str, channel: str, detected_pattern: str):
        """
        Gère une violation de mot interdit avec système progressif.
        
        Args:
            irc_client: Le client IRC
            user: L'utilisateur qui a violé
            channel: Le canal
            detected_pattern: Le pattern qui a déclenché la violation
        """
        try:
            if not irc_client.connected:
                self.logger.warning(f"Impossible de sanctionner {user}: client IRC non connecté")
                return False
            
            # Vérifier si l'utilisateur est déjà temporairement banni
            if self._is_user_temp_banned(user):
                self.logger.info(f"Utilisateur {user} déjà temporairement banni, violation ignorée")
                return False
            
            # Ajouter la violation
            self._add_violation(user)
            violation_count = self._get_violation_count(user)
            
            self.logger.warning(f"Violation #{violation_count} de {user} sur {channel}: {detected_pattern}")
            
            if violation_count == 1:
                # Premier avertissement
                self._send_warning(irc_client, user, channel, detected_pattern, 1)
                
            elif violation_count == 2:
                # Deuxième violation: kick
                self._kick_user(irc_client, user, channel, detected_pattern)
                
            elif violation_count >= 3:
                # Troisième violation et plus: ban temporaire
                self._temp_ban_user(irc_client, user, channel, detected_pattern)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la gestion de violation de {user}: {e}")
            return False

    def _send_warning(self, irc_client, user: str, channel: str, detected_pattern: str, warning_num: int):
        """Envoie un avertissement à l'utilisateur."""
        warning_msg = f"{user}: ⚠️ Avertissement #{warning_num}/2 - Langage inapproprié détecté. Prochaine violation = kick."
        irc_client.send_message(channel, warning_msg)
        self.logger.info(f"Avertissement #{warning_num} envoyé à {user} pour: {detected_pattern}")

    def _kick_user(self, irc_client, user: str, channel: str, detected_pattern: str):
        """Kick l'utilisateur du canal."""
        kick_reason = f"2ème violation - Langage inapproprié: {detected_pattern}"
        
        if irc_client.is_ircop:
            irc_client.connection.send_raw(f"KICK {channel} {user} :{kick_reason}")
        else:
            irc_client.connection.kick(channel, user, kick_reason)
        
        warning_msg = f"{user} expulsé du canal (2ème violation). Prochaine violation = ban 10 minutes."
        irc_client.send_message(channel, warning_msg)
        self.logger.info(f"Utilisateur {user} expulsé de {channel} pour: {detected_pattern}")

    def _temp_ban_user(self, irc_client, user: str, channel: str, detected_pattern: str):
        """Ban temporaire de l'utilisateur."""
        ban_reason = f"3ème violation - Ban {self.ban_duration_minutes}min: {detected_pattern}"
        
        # Bannir l'utilisateur
        if irc_client.is_ircop:
            irc_client.connection.send_raw(f"MODE {channel} +b {user}!*@*")
            irc_client.connection.send_raw(f"KICK {channel} {user} :{ban_reason}")
        else:
            irc_client.connection.mode(channel, f"+b {user}!*@*")
            irc_client.connection.kick(channel, user, ban_reason)
        
        # Programmer le déban automatique
        unban_time = time.time() + (self.ban_duration_minutes * 60)
        self.banned_users_temp[user] = unban_time
        self.banned_users.add(user)
        
        # Programmer le déban
        def unban_user():
            try:
                if irc_client.connected:
                    if irc_client.is_ircop:
                        irc_client.connection.send_raw(f"MODE {channel} -b {user}!*@*")
                    else:
                        irc_client.connection.mode(channel, f"-b {user}!*@*")
                    self.logger.info(f"Ban temporaire levé pour {user} sur {channel}")
                    
                    # Nettoyer le ban temporaire
                    if user in self.banned_users_temp:
                        del self.banned_users_temp[user]
            except Exception as e:
                self.logger.error(f"Erreur lors du déban de {user}: {e}")
        
        threading.Timer(self.ban_duration_minutes * 60, unban_user).start()
        
        warning_msg = f"⚠️ {user} banni {self.ban_duration_minutes} minutes (3ème violation)"
        irc_client.send_message(channel, warning_msg)
        self.logger.info(f"Utilisateur {user} banni {self.ban_duration_minutes}min de {channel} pour: {detected_pattern}")

    # Méthode pour compatibilité (ancien nom)
    def ban_user(self, irc_client, user: str, channel: str, detected_pattern: str):
        """Alias pour handle_violation (compatibilité)."""
        return self.handle_violation(irc_client, user, channel, detected_pattern)

    def get_stats(self) -> dict:
        """Retourne les statistiques du filtre."""
        # Nettoyer les bans temporaires expirés
        current_time = time.time()
        expired_bans = [user for user, unban_time in self.banned_users_temp.items() if current_time >= unban_time]
        for user in expired_bans:
            del self.banned_users_temp[user]
        
        return {
            'detections_count': self.detections_count,
            'banned_users_count': len(self.banned_users),
            'temp_banned_users_count': len(self.banned_users_temp),
            'active_violations_count': len(self.user_violations),
            'patterns_count': len(self.badwords),
            'banned_users': list(self.banned_users),
            'temp_banned_users': list(self.banned_users_temp.keys()),
            'users_with_warnings': {user: count for user, count in self.user_warnings.items() if count > 0}
        }

    def add_pattern(self, pattern: str):
        """Ajoute un nouveau pattern à la liste."""
        if pattern not in self.badwords:
            self.badwords.append(pattern)
            try:
                escaped = re.escape(pattern).replace('\\*', '.*?')
                compiled = re.compile(escaped, re.IGNORECASE | re.UNICODE)
                self.compiled_patterns.append((pattern, compiled))
                self.logger.info(f"Nouveau pattern ajouté: {pattern}")
                return True
            except re.error as e:
                self.logger.error(f"Impossible d'ajouter le pattern '{pattern}': {e}")
                return False
        return False

    def remove_pattern(self, pattern: str):
        """Supprime un pattern de la liste."""
        if pattern in self.badwords:
            self.badwords.remove(pattern)
            self.compiled_patterns = [(p, c) for p, c in self.compiled_patterns if p != pattern]
            self.logger.info(f"Pattern supprimé: {pattern}")
            return True
        return False

    def is_enabled_for_channel(self, channel: str) -> bool:
        """Vérifie si le filtre est activé pour ce canal."""
        return self.enabled and channel in self.monitored_channels