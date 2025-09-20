"""
Module de filtrage des pseudos inappropriés pour la modération automatique
Détection des pseudos contenant du contenu adulte et redirection vers #adultes
"""

import re
import logging
import time
from typing import List, Tuple, Optional


class NicknameFilter:
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Liste des patterns de pseudos inappropriés
        self.inappropriate_patterns = [
            "*chaudasse*",
            "*penis*",
            "*connard*",
            "*conard*",
            "*batar*",
            "*prostitu*",
            "*sexe*",
            "*couill*",
            "*salop*",
            "*suce*",
            "*poitrine*",
            "*chatte*en*",
            "*baiseur*",
            "*baise*ta*",
            "*gro*merd*",
            "*enculer*",
            "*gro*sein*",
            "*gros*nichon*",
            "*coquine*",
            "*queue*",
            "*gro*sexe*",
            "*pipeuse*",
            "*pipeur*",
            "*puceau*",
            "*pucelle*",
            "*fil*pute*",
            "*homosex*",
            "*sodomi*",
            "*baise*",
            "*cochonn*",
            "*pedophil*",
            "*grosse*pute*",
            "*branlette*"
        ]
        
        # Pré-compiler tous les patterns regex pour une détection ultra-rapide
        self.compiled_patterns = []
        self.pattern_cache = {}  # Cache pour éviter recompilation
        self._compile_patterns_optimized()
        
        # Configuration du filtre
        filter_config = config.get('nickname_filter', {})
        self.enabled = filter_config.get('enabled', True)
        self.monitored_channels = filter_config.get('channels', ['#francophonie'])
        self.redirect_channel = config['irc'].get('redirect_channel', '#adultes')
        self.send_messages = filter_config.get('send_messages', True)
        self.log_detections = filter_config.get('log_detections', True)
        
        # Canal principal surveillé (pour compatibilité)
        self.monitored_channel = config['irc'].get('monitored_channel', '#francophonie')
        
        # Messages d'accueil personnalisés selon le pattern détecté
        self.smart_welcome_messages = {
            '*sexe*': "👋 Bienvenue dans l'espace adulte approprié ! Ici vous pouvez discuter librement de sujets matures. 🔞",
            '*baise*': "👋 Salut ! Votre pseudo suggère des sujets adultes, vous êtes donc dans le bon espace pour cela. 😉",
            '*connard*': "👋 Bienvenue ! Ici vous pouvez vous exprimer plus librement sans contraintes de langage. 🗣️",
            '*penis*': "👋 Bienvenue dans l'espace adulte ! Discussions matures et libres autorisées ici. 🔞",
            '*suce*': "👋 Salut ! Votre pseudo évoque du contenu adulte, cet espace est fait pour ça. 😏",
            '*pute*': "👋 Bienvenue ! Ici les discussions adultes sont les bienvenues. 🔞",
            '*chaudasse*': "👋 Salut la chaudasse ! Tu es dans le bon espace pour des discussions hot. 🔥",
            '*coquine*': "👋 Salut coquine ! Ici tu peux être toi-même sans retenue. 😉",
            '*queue*': "👋 Bienvenue ! Les sujets adultes sont autorisés dans cet espace. 🔞",
            '*couill*': "👋 Salut ! Ton pseudo suggère des discussions libres, tu es au bon endroit. 😄",
            'default': "👋 Bienvenue ! Votre pseudo contient du contenu adulte, vous êtes donc automatiquement dirigé vers cet espace approprié. 🔞"
        }
        
        # Statistiques
        self.detections_count = 0
        self.redirected_users = set()
        
        status = "activé" if self.enabled else "désactivé"
        self.logger.info(f"Filtre de pseudos {status} avec {len(self.inappropriate_patterns)} patterns sur {self.monitored_channels}")
        self.logger.info(f"Redirection vers: {self.redirect_channel}")
        self.logger.info(f"Messages d'accueil personnalisés: {len(self.smart_welcome_messages)-1} patterns + défaut")

    def _compile_patterns_optimized(self):
        """Compile les patterns en expressions régulières optimisées pour pseudos."""
        compilation_start = time.time()
        compiled_count = 0
        
        # Tous les patterns de pseudos ont des wildcards, optimisons différemment
        # Grouper par préfixe/suffixe commun pour optimisation
        
        for pattern in self.inappropriate_patterns:
            try:
                if pattern in self.pattern_cache:
                    compiled = self.pattern_cache[pattern]
                else:
                    if '*' in pattern:
                        # Pattern avec wildcards : * devient .*? (non-greedy)
                        escaped = re.escape(pattern).replace('\\*', '.*?')
                    else:
                        # Pattern exact : recherche exacte
                        escaped = re.escape(pattern)
                    
                    # Optimisation: compiler avec flags optimisés pour pseudos
                    compiled = re.compile(escaped, re.IGNORECASE | re.UNICODE)
                    self.pattern_cache[pattern] = compiled
                
                self.compiled_patterns.append((pattern, compiled))
                compiled_count += 1
                
            except re.error as e:
                self.logger.warning(f"Pattern de pseudo invalide '{pattern}': {e}")
        
        compilation_time = time.time() - compilation_start
        self.logger.info(f"Optimisation regex pseudos: {compiled_count} patterns compilés en {compilation_time:.3f}s")
    
    def _compile_patterns(self):
        """Ancienne méthode - gardée pour compatibilité."""
        return self._compile_patterns_optimized()

    def check_nickname(self, nickname: str) -> Tuple[bool, Optional[str]]:
        """
        Vérifie si un pseudo contient du contenu inapproprié.
        
        Args:
            nickname: Le pseudo à analyser
            
        Returns:
            Tuple (est_inapproprié, pattern_détecté)
        """
        if not nickname or not nickname.strip() or not self.enabled:
            return False, None
        
        # Normaliser le pseudo (supprimer les caractères spéciaux IRC si besoin)
        normalized_nickname = nickname.lower().strip()
        
        # Tester chaque pattern
        for original_pattern, compiled_pattern in self.compiled_patterns:
            try:
                if compiled_pattern.search(normalized_nickname):
                    self.detections_count += 1
                    if self.log_detections:
                        self.logger.warning(f"Pseudo inapproprié détecté: '{nickname}' correspond au pattern '{original_pattern}'")
                    return True, original_pattern
                    
            except Exception as e:
                self.logger.error(f"Erreur lors de la vérification du pattern '{original_pattern}' sur '{nickname}': {e}")
                continue
        
        return False, None

    def handle_inappropriate_nickname(self, irc_client, user: str, channel: str, detected_pattern: str):
        """
        Gère un pseudo inapproprié en redirigeant l'utilisateur vers #adultes.
        
        Args:
            irc_client: Le client IRC
            user: L'utilisateur avec le pseudo inapproprié
            channel: Le canal d'origine
            detected_pattern: Le pattern qui a déclenché la détection
        """
        try:
            if not irc_client.connected:
                self.logger.warning(f"Impossible de rediriger {user}: client IRC non connecté")
                return False
            
            # Vérifier qu'on est bien sur le bon canal
            if not self.is_enabled_for_channel(channel):
                return False
            
            self.logger.info(f"Redirection de {user} vers {self.redirect_channel} (pseudo inapproprié: {detected_pattern})")
            
            # Messages d'information
            reason = f"Pseudo inapproprié détecté: {detected_pattern}"
            
            if self.send_messages:
                # Message sur #francophonie pour expliquer
                francophonie_msg = f"⚠️ {user}: Votre pseudo contient du contenu inapproprié. Redirection automatique vers {self.redirect_channel}."
                irc_client.send_message(channel, francophonie_msg)
            
            # Rediriger l'utilisateur (comme pour le contenu adulte)
            if irc_client.is_ircop:
                # 1. Faire partir l'utilisateur de #francophonie avec SAPART
                irc_client.connection.send_raw(f"SAPART {user} {channel} :{reason}")
                
                # 2. Le bannir temporairement pour l'empêcher de revenir immédiatement
                irc_client.connection.send_raw(f"MODE {channel} +b {user}!*@*")
                
                # 3. Faire rejoindre l'utilisateur sur le canal de redirection avec SAJOIN
                irc_client.connection.send_raw(f"SAJOIN {user} {self.redirect_channel}")
                
                # 4. Débannir après quelques secondes
                import threading
                def unban_user():
                    if irc_client.connected:
                        irc_client.connection.send_raw(f"MODE {channel} -b {user}!*@*")
                        self.logger.info(f"Ban temporaire levé pour {user} sur {channel} (pseudo inapproprié)")
                threading.Timer(30.0, unban_user).start()  # Déban après 30 secondes
                
                self.logger.info(f"SAPART {user} de {channel} puis SAJOIN vers {self.redirect_channel} (pseudo: {detected_pattern})")
                
                # Message de bienvenue personnalisé sur #adultes (avec délai)
                def send_welcome():
                    if irc_client.connected and self.send_messages:
                        # Choisir le message selon le pattern détecté
                        welcome_msg = self._get_smart_welcome_message(user, detected_pattern)
                        irc_client.send_message(self.redirect_channel, welcome_msg)
                
                threading.Timer(2.0, send_welcome).start()
            else:
                # Sans privilèges IRCop, ban classique
                irc_client.connection.mode(channel, f"+b {user}!*@*")
                irc_client.connection.kick(channel, user, reason)
                self.logger.info(f"Utilisateur {user} banni de {channel} (pseudo inapproprié: {detected_pattern})")
                
                if self.send_messages:
                    explanation_msg = f"ℹ️ {user} a été exclu à cause de son pseudo inapproprié. Il peut rejoindre {self.redirect_channel} pour discuter."
                    irc_client.send_message(channel, explanation_msg)
            
            # Enregistrer la redirection
            self.redirected_users.add(user)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la redirection de {user}: {e}")
            return False

    def _get_smart_welcome_message(self, user: str, detected_pattern: str) -> str:
        """
        Retourne un message d'accueil personnalisé selon le pattern détecté.
        
        Args:
            user: Le pseudo de l'utilisateur
            detected_pattern: Le pattern qui a déclenché la détection
            
        Returns:
            Message d'accueil personnalisé
        """
        # Chercher un message spécifique pour ce pattern
        if detected_pattern in self.smart_welcome_messages:
            message_template = self.smart_welcome_messages[detected_pattern]
        else:
            # Message par défaut
            message_template = self.smart_welcome_messages['default']
        
        # Remplacer les placeholders par le nom d'utilisateur
        personalized_message = f"{user}: {message_template}"
        
        self.logger.info(f"Message d'accueil personnalisé pour {user} (pattern: {detected_pattern})")
        return personalized_message

    def is_enabled_for_channel(self, channel: str) -> bool:
        """Vérifie si le filtre est activé pour ce canal."""
        return self.enabled and channel in self.monitored_channels

    def get_stats(self) -> dict:
        """Retourne les statistiques du filtre."""
        return {
            'detections_count': self.detections_count,
            'redirected_users_count': len(self.redirected_users),
            'patterns_count': len(self.inappropriate_patterns),
            'redirected_users': list(self.redirected_users)
        }

    def add_pattern(self, pattern: str):
        """Ajoute un nouveau pattern à la liste."""
        if pattern not in self.inappropriate_patterns:
            self.inappropriate_patterns.append(pattern)
            try:
                if '*' in pattern:
                    escaped = re.escape(pattern).replace('\\*', '.*?')
                else:
                    escaped = re.escape(pattern)
                compiled = re.compile(escaped, re.IGNORECASE | re.UNICODE)
                self.compiled_patterns.append((pattern, compiled))
                self.logger.info(f"Nouveau pattern de pseudo ajouté: {pattern}")
                return True
            except re.error as e:
                self.logger.error(f"Impossible d'ajouter le pattern de pseudo '{pattern}': {e}")
                return False
        return False

    def remove_pattern(self, pattern: str):
        """Supprime un pattern de la liste."""
        if pattern in self.inappropriate_patterns:
            self.inappropriate_patterns.remove(pattern)
            self.compiled_patterns = [(p, c) for p, c in self.compiled_patterns if p != pattern]
            self.logger.info(f"Pattern de pseudo supprimé: {pattern}")
            return True
        return False