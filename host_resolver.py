#!/usr/bin/env python3
"""
Résolveur d'host IRC pour AlphaBaboon.
Récupère les vraies informations host des utilisateurs pour des bans efficaces.
"""

import logging
from typing import Optional, Dict
import time


class HostResolver:
    """
    Gestionnaire pour résoudre les hosts des utilisateurs IRC.
    Permet de banner par *@host au lieu de pseudo!*@*.
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Cache des hosts utilisateur
        self.user_hosts: Dict[str, str] = {}
        self.host_cache_timeout = 3600  # 1 heure
        self.last_updated: Dict[str, float] = {}
        
        self.logger.info("HostResolver initialisé pour bans efficaces par host")
    
    def get_user_host(self, irc_client, channel: str, username: str) -> Optional[str]:
        """
        Récupère le host d'un utilisateur depuis IRC.
        Retourne le host pour faire un ban *@host.
        """
        try:
            # Vérifier le cache d'abord
            if self._is_host_cached(username):
                cached_host = self.user_hosts[username]
                self.logger.debug(f"Host en cache pour {username}: {cached_host}")
                return cached_host
            
            # Méthode 1: Utiliser la liste des utilisateurs du canal
            if hasattr(irc_client, 'channels') and channel in irc_client.channels:
                channel_obj = irc_client.channels[channel]
                
                # Chercher dans les informations utilisateur
                if hasattr(channel_obj, 'users'):
                    users = channel_obj.users()
                    for user in users:
                        if user == username or user.lstrip('@%+') == username:
                            # Tenter de récupérer les infos complètes
                            if hasattr(channel_obj, 'get_user_info'):
                                user_info = channel_obj.get_user_info(username)
                                if user_info and hasattr(user_info, 'host'):
                                    host = user_info.host
                                    self._cache_host(username, host)
                                    return host
                                    
                # Méthode alternative: chercher dans users_data si disponible
                if hasattr(channel_obj, 'users_data'):
                    for user_data in channel_obj.users_data.values():
                        if hasattr(user_data, 'nick') and user_data.nick.lower() == username.lower():
                            if hasattr(user_data, 'host') and user_data.host:
                                host = user_data.host
                                self._cache_host(username, host)
                                return host
            
            # Méthode 2: Parsing depuis les événements IRC récents
            # (Les infos host sont souvent disponibles dans les événements join/who)
            if hasattr(irc_client, 'last_user_info'):
                user_info = irc_client.last_user_info.get(username.lower())
                if user_info and 'host' in user_info:
                    host = user_info['host']
                    self._cache_host(username, host)
                    return host
            
            # Méthode 3: Tenter d'extraire le host depuis les données de connexion récentes
            host = self._extract_host_from_recent_data(irc_client, username)
            if host:
                self._cache_host(username, host)
                return host
            
            # Méthode 4: Envoyer une requête WHO (peut prendre du temps)
            self._request_who_info(irc_client, username)
            
            self.logger.warning(f"Impossible de récupérer le host pour {username}")
            return None
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la résolution host pour {username}: {e}")
            return None
    
    def get_ban_mask(self, irc_client, channel: str, username: str) -> str:
        """
        Génère le masque de ban optimal pour un utilisateur.
        Retourne *@host si possible, sinon fallback vers nick!*@*.
        """
        host = self.get_user_host(irc_client, channel, username)
        
        if host:
            # Ban par host: plus efficace car couvre les changements de pseudo
            ban_mask = f"*@{host}"
            self.logger.info(f"Ban mask pour {username}: {ban_mask} (par host)")
            return ban_mask
        else:
            # Fallback: ban par nick (moins efficace)
            ban_mask = f"{username}!*@*"
            self.logger.warning(f"Ban mask pour {username}: {ban_mask} (fallback par nick)")
            return ban_mask

    def get_pseudo_ban_mask(self, username: str) -> str:
        """
        Génère un masque de ban par pseudo uniquement.
        Retourne toujours pseudo!*@*.
        """
        ban_mask = f"{username}!*@*"
        self.logger.info(f"Ban mask pseudo pour {username}: {ban_mask}")
        return ban_mask
    
    def get_user_full_info(self, irc_client, channel: str, username: str) -> Dict:
        """
        Récupère toutes les infos disponibles d'un utilisateur.
        """
        try:
            host = self.get_user_host(irc_client, channel, username)
            
            result = {
                'username': username,
                'host': host,
                'ban_mask': self.get_ban_mask(irc_client, channel, username),
                'has_host': host is not None,
                'cache_age': self._get_cache_age(username)
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Erreur récupération infos pour {username}: {e}")
            return {
                'username': username,
                'host': None,
                'ban_mask': f"{username}!*@*",
                'has_host': False,
                'error': str(e)
            }
    
    def _is_host_cached(self, username: str) -> bool:
        """Vérifie si le host est en cache et pas expiré."""
        if username not in self.user_hosts:
            return False
        
        if username not in self.last_updated:
            return False
        
        age = time.time() - self.last_updated[username]
        return age < self.host_cache_timeout
    
    def _cache_host(self, username: str, host: str):
        """Met en cache le host d'un utilisateur."""
        self.user_hosts[username] = host
        self.last_updated[username] = time.time()
        self.logger.debug(f"Host mis en cache: {username} -> {host}")
    
    def _get_cache_age(self, username: str) -> Optional[int]:
        """Retourne l'âge du cache en secondes."""
        if username not in self.last_updated:
            return None
        return int(time.time() - self.last_updated[username])
    
    def _extract_host_from_recent_data(self, irc_client, username: str) -> Optional[str]:
        """
        Tente d'extraire le host depuis les données de connexion récentes.
        """
        try:
            # Vérifier dans l'historique des connexions/déconnexions
            if hasattr(irc_client, 'connection_history'):
                for event in reversed(irc_client.connection_history[-50:]):  # 50 derniers événements
                    if hasattr(event, 'source') and username.lower() in event.source.lower():
                        # Format typique: nick!user@host
                        if '@' in event.source and '!' in event.source:
                            parts = event.source.split('@')
                            if len(parts) >= 2:
                                host = parts[-1]  # Dernière partie après @
                                self.logger.debug(f"Host trouvé depuis l'historique pour {username}: {host}")
                                return host
            
            # Vérifier dans les événements de message récents
            if hasattr(irc_client, 'recent_messages'):
                for msg_data in reversed(irc_client.recent_messages[-20:]):  # 20 derniers messages
                    if msg_data.get('nick', '').lower() == username.lower():
                        source = msg_data.get('source', '')
                        if '@' in source and '!' in source:
                            parts = source.split('@')
                            if len(parts) >= 2:
                                host = parts[-1]
                                self.logger.debug(f"Host trouvé depuis les messages pour {username}: {host}")
                                return host
            
            return None
            
        except Exception as e:
            self.logger.error(f"Erreur extraction host depuis données récentes pour {username}: {e}")
            return None

    def _request_who_info(self, irc_client, username: str):
        """
        Demande les infos WHO pour un utilisateur.
        Note: Asynchrone, le résultat viendra plus tard.
        """
        try:
            who_command = f"WHO {username}"
            irc_client.connection.send_raw(who_command)
            self.logger.debug(f"Requête WHO envoyée pour {username}")
        except Exception as e:
            self.logger.error(f"Erreur envoi WHO pour {username}: {e}")
    
    def capture_host_from_event(self, username: str, source: str):
        """
        Capture et met en cache le host depuis un événement IRC.
        Format source attendu: nick!user@host
        """
        try:
            if '@' in source and '!' in source:
                parts = source.split('@')
                if len(parts) >= 2:
                    host = parts[-1]
                    self._cache_host(username, host)
                    self.logger.debug(f"Host capturé depuis événement pour {username}: {host}")
                    return host
        except Exception as e:
            self.logger.error(f"Erreur capture host depuis événement pour {username}: {e}")
        return None
    
    def clear_cache(self):
        """Vide le cache des hosts."""
        count = len(self.user_hosts)
        self.user_hosts.clear()
        self.last_updated.clear()
        self.logger.info(f"Cache hosts vidé ({count} entrées supprimées)")
    
    def get_cache_stats(self) -> Dict:
        """Retourne les statistiques du cache."""
        current_time = time.time()
        expired_count = 0
        
        for username, last_update in self.last_updated.items():
            age = current_time - last_update
            if age >= self.host_cache_timeout:
                expired_count += 1
        
        return {
            'total_cached': len(self.user_hosts),
            'expired_entries': expired_count,
            'cache_timeout_hours': self.host_cache_timeout / 3600
        }


if __name__ == "__main__":
    # Test basique
    test_config = {}
    resolver = HostResolver(test_config)
    
    # Simuler des infos
    resolver._cache_host("TestUser", "example.com")
    print(f"Ban mask: {resolver.get_ban_mask(None, '#test', 'TestUser')}")  # Devrait afficher *@example.com
    print(f"Stats: {resolver.get_cache_stats()}")
    print("HostResolver test OK")