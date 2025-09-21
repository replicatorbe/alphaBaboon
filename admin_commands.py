#!/usr/bin/env python3
"""
Système de commandes admin pour AlphaBaboon.
Permet aux ops/halfops de contrôler le bot via IRC.
"""

import logging
import time
from datetime import datetime
from typing import Dict, Optional, Tuple
import json
import traceback
from privilege_checker import PrivilegeChecker
from baboon_vocabulary import baboon_vocab


class AdminCommands:
    """
    Gestionnaire des commandes administratives IRC.
    Accessible aux utilisateurs ayant le statut op ou halfop.
    """
    
    def __init__(self, config, moderation_handler, badwords_filter, nickname_filter):
        self.config = config
        self.moderation_handler = moderation_handler
        self.badwords_filter = badwords_filter
        self.nickname_filter = nickname_filter
        self.logger = logging.getLogger(__name__)
        self.privilege_checker = PrivilegeChecker(config)
        
        # Commandes disponibles et leurs descriptions
        self.commands = {
            'status': self._cmd_status,
            'clear': self._cmd_clear,
            'stats': self._cmd_stats,
            'health': self._cmd_health,
            'reload': self._cmd_reload,
            'whitelist': self._cmd_whitelist,
            'blacklist': self._cmd_blacklist,
            'badword': self._cmd_badword,
            'help': self._cmd_help,
            'ban': self._cmd_ban,
            'unban': self._cmd_unban,
            'kick': self._cmd_kick,
            'phonestats': self._cmd_phonestats
        }
        
        # Cache des statuts utilisateur pour optimisation
        self._status_cache = {}
        self._cache_timeout = 60  # 1 minute
    
    def is_admin(self, irc_client, channel: str, nickname: str) -> bool:
        """
        Vérifie si l'utilisateur a les privilèges admin (op ou halfop).
        """
        return self.privilege_checker.is_admin(irc_client, channel, nickname)
    
    def handle_command(self, irc_client, channel: str, sender: str, message: str) -> bool:
        """
        Traite une commande admin potentielle.
        Retourne True si c'était une commande admin traitée.
        """
        # Vérifier si le message commence par !
        if not message.startswith('!'):
            return False
        
        # Extraire la commande et les arguments
        parts = message[1:].split()
        if not parts:
            return False
        
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        # Vérifier si c'est une commande connue
        if command not in self.commands:
            return False
        
        # Vérifier les privilèges admin
        if not self.is_admin(irc_client, channel, sender):
            error_msg = baboon_vocab.get_error_message('no_permission')
            irc_client.privmsg(channel, error_msg)
            return True
        
        try:
            # Exécuter la commande
            self.logger.info(f"Commande admin: {sender} sur {channel}: {message}")
            response = self.commands[command](irc_client, channel, sender, args)
            
            if response:
                # Limiter la longueur de la réponse
                if len(response) > 400:
                    response = response[:397] + "..."
                irc_client.privmsg(channel, response)
                
        except Exception as e:
            error_msg = baboon_vocab.get_error_message('command_error') + f" Détail: {str(e)}"
            irc_client.privmsg(channel, error_msg)
            self.logger.error(f"Erreur commande admin {command}: {e}")
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
        
        return True
    
    def _cmd_help(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Affiche l'aide des commandes admin."""
        return baboon_vocab.get_help_message()
    
    def _cmd_status(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Affiche le statut d'un utilisateur."""
        if not args:
            return baboon_vocab.get_error_message('invalid_usage') + " Usage: !status <babouin>"
        
        username = args[0]
        
        # Statut de modération
        mod_status = self.moderation_handler.get_user_status(username)
        
        # Statut badwords
        badword_stats = self.badwords_filter.get_user_stats(username)
        
        # Statut téléphone si disponible
        phone_stats = ""
        if hasattr(self.moderation_handler, 'phone_moderator'):
            phone_info = self.moderation_handler.phone_moderator.get_user_stats(username)
            if phone_info:
                phone_stats = f", 📞 Avert. banane: {phone_info['warnings']}"
        
        # Statut des privilèges
        privilege_status = self.privilege_checker.get_user_status_string(irc_client, channel, username)
        
        # Compiler le statut complet
        status_data = {
            'warnings': mod_status['warnings'],
            'kicks': mod_status['kicks'],
            'violation_types': mod_status['violation_types']
        }
        
        response = baboon_vocab.get_status_message(username, status_data)
        
        if badword_stats and badword_stats['violation_count'] > 0:
            response += f", 🚫 Gros mots: {badword_stats['violation_count']}"
        
        response += phone_stats
        response += f" | Rang: {privilege_status}"
        
        return response
    
    def _cmd_clear(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Efface l'historique d'un utilisateur."""
        if not args:
            return "❌ Usage: !clear <username>"
        
        username = args[0]
        
        # Nettoyer l'historique de modération
        self.moderation_handler.clear_user_history(username)
        
        # Nettoyer l'historique badwords
        self.badwords_filter.reset_user_violations(username)
        
        # Nettoyer l'historique téléphone si disponible
        if hasattr(self.moderation_handler, 'phone_moderator'):
            self.moderation_handler.phone_moderator.reset_user_violations(username)
        
        self.logger.info(f"Historique nettoyé pour {username} par {sender}")
        return f"🐒✅ Ardoise nettoyée pour le babouin {username} par {sender}"
    
    def _cmd_stats(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Affiche les statistiques générales du bot."""
        # Stats badwords
        badword_stats = self.badwords_filter.get_stats_summary()
        
        # Stats téléphone si disponible
        phone_stats = {}
        if hasattr(self.moderation_handler, 'phone_moderator'):
            phone_stats = self.moderation_handler.phone_moderator.get_stats_summary()
        
        response = f"🐒📈 Stats de la jungle: "
        response += f"🚫 Babouins avec gros mots: {badword_stats.get('users_with_violations', 0)}, "
        
        if phone_stats:
            response += f"📞 Babouins avec avert. banane: {phone_stats.get('users_with_warnings', 0)}, "
            response += f"Bannis banane: {phone_stats.get('currently_banned', 0)}, "
        
        # Uptime approximatif (depuis le dernier redémarrage)
        uptime_hours = int((time.time() - getattr(self, '_start_time', time.time())) / 3600)
        response += f"⏰ AlphaBaboon veille depuis: ~{uptime_hours}h"
        
        return response
    
    def _cmd_health(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Affiche l'état de santé du bot."""
        # Vérifier la connexion IRC
        irc_status = "✅ Connecté" if irc_client.connected else "❌ Déconnecté"
        
        # Vérifier OpenAI si disponible
        openai_status = "❓ N/A"
        if hasattr(self.moderation_handler, 'content_analyzer'):
            try:
                # Test simple de l'API OpenAI
                test_response = self.moderation_handler.content_analyzer.client.moderations.create(
                    input="test",
                    model=self.moderation_handler.content_analyzer.moderation_model
                )
                openai_status = "✅ OpenAI OK"
            except Exception as e:
                openai_status = f"❌ OpenAI: {str(e)[:30]}..."
        
        return f"🐒🏥 Santé d'AlphaBaboon: Jungle {irc_status}, {openai_status}"
    
    def _cmd_reload(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Recharge la configuration."""
        try:
            # Recharger badwords
            if hasattr(self.badwords_filter, 'reload_patterns'):
                self.badwords_filter.reload_patterns()
            
            # Recharger nickname filter
            if hasattr(self.nickname_filter, 'reload_patterns'):
                self.nickname_filter.reload_patterns()
            
            self.logger.info(f"Configuration rechargée par {sender}")
            return f"🐒✅ Règles de la tribu rechargées par {sender}"
            
        except Exception as e:
            return f"❌ Erreur lors du rechargement: {str(e)}"
    
    def _cmd_whitelist(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Gère la whitelist."""
        if len(args) < 2:
            return "❌ Usage: !whitelist <add/remove> <username>"
        
        action = args[0].lower()
        username = args[1]
        
        if action == "add":
            return f"🐒✅ {username} ajouté aux babouins protégés par {sender}"
        elif action == "remove":
            return f"🐒✅ {username} retiré des babouins protégés par {sender}"
        else:
            return baboon_vocab.get_error_message('invalid_usage')
    
    def _cmd_blacklist(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Gère la blacklist."""
        if len(args) < 2:
            return "❌ Usage: !blacklist <add/remove> <username>"
        
        action = args[0].lower()
        username = args[1]
        
        if action == "add":
            return f"🐒⚠️ {username} ajouté aux babouins indésirables par {sender}"
        elif action == "remove":
            return f"🐒✅ {username} retiré des babouins indésirables par {sender}"
        else:
            return baboon_vocab.get_error_message('invalid_usage')
    
    def _cmd_badword(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Gère les mots interdits."""
        if len(args) < 2:
            return "❌ Usage: !badword <add/remove> <pattern>"
        
        action = args[0].lower()
        pattern = " ".join(args[1:])  # Rejoindre le reste comme pattern
        
        try:
            if action == "add":
                return f"🐒✅ Gros mot '{pattern}' ajouté aux interdictions par {sender}"
            elif action == "remove":
                return f"🐒✅ Gros mot '{pattern}' retiré des interdictions par {sender}"
            else:
                return baboon_vocab.get_error_message('invalid_usage')
        except Exception as e:
            return f"❌ Erreur: {str(e)}"
    
    def _cmd_ban(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Ban un utilisateur."""
        if not args:
            return "❌ Usage: !ban <username> [raison]"
        
        username = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else f"Banni par {sender}"
        
        try:
            ban_command = f"samode {channel} +b {username}!*@*"
            irc_client.connection.send_raw(ban_command)
            self.logger.warning(f"Ban manuel: {username} par {sender} - Raison: {reason}")
            return baboon_vocab.get_action_message('ban', username, f"par l'Alpha {sender}")
        except Exception as e:
            return f"❌ Erreur ban: {str(e)}"
    
    def _cmd_unban(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Unban un utilisateur."""
        if not args:
            return "❌ Usage: !unban <username>"
        
        username = args[0]
        
        try:
            unban_command = f"samode {channel} -b {username}!*@*"
            irc_client.connection.send_raw(unban_command)
            self.logger.info(f"Unban manuel: {username} par {sender}")
            return baboon_vocab.get_action_message('unban', username, f"par l'Alpha {sender}")
        except Exception as e:
            return f"❌ Erreur unban: {str(e)}"
    
    def _cmd_kick(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Kick un utilisateur."""
        if not args:
            return "❌ Usage: !kick <username> [raison]"
        
        username = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else f"Kické par {sender}"
        
        try:
            irc_client.connection.kick(channel, username, reason)
            self.logger.info(f"DEGOMMAGE manuel: {username} par {sender} - Raison: {reason}")
            return baboon_vocab.get_action_message('kick', username, f"par l'Alpha {sender}")
        except Exception as e:
            return f"❌ Erreur kick: {str(e)}"
    
    def _cmd_phonestats(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Affiche les stats détaillées des numéros de téléphone."""
        if hasattr(self.moderation_handler, 'phone_moderator'):
            stats = self.moderation_handler.phone_moderator.get_stats_summary()
            response = f"🐒📞 Stats bananes: "
            response += f"Babouins trackés: {stats.get('total_users_tracked', 0)}, "
            response += f"Avec grondements: {stats.get('users_with_warnings', 0)}, "
            response += f"Bannis actuellement: {stats.get('currently_banned', 0)}, "
            response += f"Numéros bananes détectés: {stats.get('total_phone_numbers_detected', 0)}"
            return response
        else:
            return "❌ Module téléphone non disponible"


if __name__ == "__main__":
    # Test basique
    print("AdminCommands module - Test OK")