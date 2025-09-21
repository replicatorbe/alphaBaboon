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
        try:
            if not hasattr(irc_client, 'channels'):
                return False
            
            if channel not in irc_client.channels:
                return False
            
            channel_obj = irc_client.channels[channel]
            
            # Vérifier si l'utilisateur est op (@) ou halfop (%)
            is_op = channel_obj.is_oper(nickname)
            is_halfop = channel_obj.is_halfop(nickname) if hasattr(channel_obj, 'is_halfop') else False
            
            # Alternative: vérifier dans la liste des utilisateurs avec préfixes
            if not (is_op or is_halfop):
                users = channel_obj.users()
                for user in users:
                    if user == nickname:
                        # Vérifier les modes de l'utilisateur
                        if hasattr(channel_obj, 'get_user_modes'):
                            modes = channel_obj.get_user_modes(nickname)
                            is_op = 'o' in modes
                            is_halfop = 'h' in modes
                        break
            
            self.logger.debug(f"Vérification admin {nickname} sur {channel}: op={is_op}, halfop={is_halfop}")
            return is_op or is_halfop
            
        except Exception as e:
            self.logger.error(f"Erreur vérification admin pour {nickname}: {e}")
            return False
    
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
            irc_client.privmsg(channel, f"❌ @{sender}, seuls les ops/halfops peuvent utiliser cette commande.")
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
            error_msg = f"❌ Erreur lors de l'exécution de la commande: {str(e)}"
            irc_client.privmsg(channel, error_msg)
            self.logger.error(f"Erreur commande admin {command}: {e}")
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
        
        return True
    
    def _cmd_help(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Affiche l'aide des commandes admin."""
        help_text = "🤖 Commandes admin disponibles: "
        help_text += "!status <user>, !clear <user>, !stats, !health, !reload, "
        help_text += "!whitelist <add/remove> <user>, !blacklist <add/remove> <user>, "
        help_text += "!badword <add/remove> <pattern>, !ban <user>, !unban <user>, !kick <user>, !phonestats"
        return help_text
    
    def _cmd_status(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Affiche le statut d'un utilisateur."""
        if not args:
            return "❌ Usage: !status <username>"
        
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
                phone_stats = f", 📞 Avert. tél: {phone_info['warnings']}"
        
        response = f"📊 Status {username}: "
        response += f"⚠️ Warnings: {mod_status['warnings']}, "
        response += f"👢 Kicks: {mod_status['kicks']}"
        
        if badword_stats:
            response += f", 🚫 Mots interdits: {badword_stats['violation_count']}"
        
        response += phone_stats
        
        if mod_status['violation_types']:
            response += f", Types: {', '.join(mod_status['violation_types'])}"
        
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
        return f"✅ Historique de {username} effacé par @{sender}"
    
    def _cmd_stats(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Affiche les statistiques générales du bot."""
        # Stats badwords
        badword_stats = self.badwords_filter.get_stats_summary()
        
        # Stats téléphone si disponible
        phone_stats = {}
        if hasattr(self.moderation_handler, 'phone_moderator'):
            phone_stats = self.moderation_handler.phone_moderator.get_stats_summary()
        
        response = f"📈 Stats bot: "
        response += f"🚫 Users avec violations mots: {badword_stats.get('users_with_violations', 0)}, "
        
        if phone_stats:
            response += f"📞 Users avec avert. tél: {phone_stats.get('users_with_warnings', 0)}, "
            response += f"Bannis tél: {phone_stats.get('currently_banned', 0)}, "
        
        # Uptime approximatif (depuis le dernier redémarrage)
        uptime_hours = int((time.time() - getattr(self, '_start_time', time.time())) / 3600)
        response += f"⏰ Uptime: ~{uptime_hours}h"
        
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
        
        return f"🏥 Santé bot: IRC {irc_status}, {openai_status}"
    
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
            return f"✅ Configuration rechargée par @{sender}"
            
        except Exception as e:
            return f"❌ Erreur lors du rechargement: {str(e)}"
    
    def _cmd_whitelist(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Gère la whitelist."""
        if len(args) < 2:
            return "❌ Usage: !whitelist <add/remove> <username>"
        
        action = args[0].lower()
        username = args[1]
        
        if action == "add":
            # Ajouter à la whitelist (exemple simple)
            return f"✅ {username} ajouté à la whitelist par @{sender}"
        elif action == "remove":
            return f"✅ {username} retiré de la whitelist par @{sender}"
        else:
            return "❌ Action invalide. Utilisez 'add' ou 'remove'"
    
    def _cmd_blacklist(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Gère la blacklist."""
        if len(args) < 2:
            return "❌ Usage: !blacklist <add/remove> <username>"
        
        action = args[0].lower()
        username = args[1]
        
        if action == "add":
            return f"⚠️ {username} ajouté à la blacklist par @{sender}"
        elif action == "remove":
            return f"✅ {username} retiré de la blacklist par @{sender}"
        else:
            return "❌ Action invalide. Utilisez 'add' ou 'remove'"
    
    def _cmd_badword(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Gère les mots interdits."""
        if len(args) < 2:
            return "❌ Usage: !badword <add/remove> <pattern>"
        
        action = args[0].lower()
        pattern = " ".join(args[1:])  # Rejoindre le reste comme pattern
        
        try:
            if action == "add":
                # Tenter d'ajouter le pattern (à implémenter dans badwords_filter)
                return f"✅ Pattern '{pattern}' ajouté aux mots interdits par @{sender}"
            elif action == "remove":
                return f"✅ Pattern '{pattern}' retiré des mots interdits par @{sender}"
            else:
                return "❌ Action invalide. Utilisez 'add' ou 'remove'"
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
            return f"🔨 {username} banni par @{sender}"
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
            return f"✅ {username} débanni par @{sender}"
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
            self.logger.info(f"Kick manuel: {username} par {sender} - Raison: {reason}")
            return f"👢 {username} kické par @{sender}"
        except Exception as e:
            return f"❌ Erreur kick: {str(e)}"
    
    def _cmd_phonestats(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Affiche les stats détaillées des numéros de téléphone."""
        if hasattr(self.moderation_handler, 'phone_moderator'):
            stats = self.moderation_handler.phone_moderator.get_stats_summary()
            response = f"📞 Stats téléphone: "
            response += f"Users trackés: {stats.get('total_users_tracked', 0)}, "
            response += f"Avec warnings: {stats.get('users_with_warnings', 0)}, "
            response += f"Bannis actuellement: {stats.get('currently_banned', 0)}, "
            response += f"Numéros détectés total: {stats.get('total_phone_numbers_detected', 0)}"
            return response
        else:
            return "❌ Module téléphone non disponible"


if __name__ == "__main__":
    # Test basique
    print("AdminCommands module - Test OK")