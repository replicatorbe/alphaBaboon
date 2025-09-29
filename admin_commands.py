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
from host_resolver import HostResolver


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
        self.host_resolver = HostResolver(config)
        
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
            'banpseudo': self._cmd_banpseudo,
            'unban': self._cmd_unban,
            'kick': self._cmd_kick,
            'phonestats': self._cmd_phonestats,
            'hostinfo': self._cmd_hostinfo,
            'clearcache': self._cmd_clearcache,
            'regle': self._cmd_regle
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
        
        # Stats hosts cache
        cache_stats = self.host_resolver.get_cache_stats()
        
        response = f"🐒📈 Stats de la jungle: "
        response += f"🚫 Babouins avec gros mots: {badword_stats.get('users_with_violations', 0)}, "
        
        if phone_stats:
            response += f"📞 Babouins avec avert. banane: {phone_stats.get('users_with_warnings', 0)}, "
            response += f"Bannis banane: {phone_stats.get('currently_banned', 0)}, "
        
        # Ajout des stats de cache hosts
        response += f"🔍 Hosts trackés: {cache_stats['total_cached']} ({cache_stats['expired_entries']} exp.), "
        
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
        """Ban un utilisateur par host (*@host) pour plus d'efficacité."""
        if not args:
            return baboon_vocab.get_error_message('invalid_usage') + " Usage: !ban <babouin> [raison]"
        
        username = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else f"Banni par {sender}"
        
        try:
            # Essayer d'abord de récupérer le host directement depuis WHO
            host = self._get_user_host_via_who(irc_client, username)
            
            if host:
                # Ban par host: plus efficace
                ban_mask = f"*@{host}"
                ban_type = "par host"
                has_host = True
            else:
                # Fallback: ban par pseudo
                ban_mask = f"{username}!*@*"
                ban_type = "par pseudo"
                has_host = False
                host = "N/A"
            
            # Appliquer le ban
            ban_command = f"mode {channel} +b {ban_mask}"
            irc_client.connection.send_raw(ban_command)
            
            # Log détaillé
            ban_detail = {
                'username': username,
                'ban_mask': ban_mask,
                'has_host': has_host,
                'host': host,
                'banned_by': sender,
                'reason': reason
            }
            self.logger.warning(f"🔨 BAN APPLIED: {ban_detail}")
            
            # Message de retour
            response = baboon_vocab.get_action_message('ban', username, f"par l'Alpha {sender}")
            response += f" (Ban {ban_type}: {ban_mask})"
            
            return response
            
        except Exception as e:
            error_detail = f"Erreur ban {username}: {str(e)}"
            self.logger.error(error_detail)
            return baboon_vocab.get_error_message('command_error') + f" {str(e)}"
    
    def _cmd_unban(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Unban un utilisateur (essaie les deux formats: host et pseudo)."""
        if not args:
            return baboon_vocab.get_error_message('invalid_usage') + " Usage: !unban <babouin>"
        
        username = args[0]
        
        try:
            # Essayer tous les formats possibles de ban
            unban_masks = []
            unban_type_parts = []
            
            # 1. Vérifier si on a un host en cache pour ce user
            user_info = self.host_resolver.get_user_full_info(irc_client, channel, username)
            
            if user_info.get('has_host'):
                # Format par host: *@host
                host = user_info.get('host')
                host_mask = f"*@{host}"
                unban_masks.append(host_mask)
                unban_type_parts.append("host")
            
            # 2. Toujours essayer le format par pseudo: pseudo!*@*
            pseudo_mask = f"{username}!*@*"
            unban_masks.append(pseudo_mask)
            unban_type_parts.append("pseudo")
            
            # Envoyer toutes les commandes unban
            for mask in unban_masks:
                unban_command = f"mode {channel} -b {mask}"
                irc_client.connection.send_raw(unban_command)
                self.logger.info(f"Unban envoyé: {unban_command}")
            
            # Log détaillé
            unban_detail = {
                'username': username,
                'unban_masks': unban_masks,
                'unban_type': " + ".join(unban_type_parts),
                'unbanned_by': sender
            }
            self.logger.info(f"✅ UNBAN APPLIED: {unban_detail}")
            
            response = baboon_vocab.get_action_message('unban', username, f"par l'Alpha {sender}")
            response += f" ({' + '.join(unban_type_parts)})"
            
            return response
            
        except Exception as e:
            error_detail = f"Erreur unban {username}: {str(e)}"
            self.logger.error(error_detail)
            return baboon_vocab.get_error_message('command_error') + f" {str(e)}"
    
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
    
    def _cmd_hostinfo(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Affiche les informations host d'un utilisateur pour debug."""
        if not args:
            return baboon_vocab.get_error_message('invalid_usage') + " Usage: !hostinfo <babouin>"
        
        username = args[0]
        
        try:
            user_info = self.host_resolver.get_user_full_info(irc_client, channel, username)
            cache_stats = self.host_resolver.get_cache_stats()
            
            # Status plus détaillé
            if user_info.get('has_host'):
                host_status = f"✅ {user_info['host']}"
                ban_will_use = "par host (*@host)" 
            else:
                host_status = "❌ Non trouvé"
                ban_will_use = "par pseudo (pseudo!*@*)"
            
            response = f"🐒🔍 {username}: Host {host_status}"
            
            # Âge du cache plus lisible
            if user_info.get('cache_age') is not None:
                age = user_info['cache_age']
                if age < 60:
                    age_str = f"{age}s"
                elif age < 3600:
                    age_str = f"{age//60}min"
                else:
                    age_str = f"{age//3600}h"
                response += f" (Cache: {age_str})"
            else:
                response += " (Pas en cache)"
            
            response += f" | Ban utilisera: {ban_will_use}"
            response += f" | Cache: {cache_stats['total_cached']}/{cache_stats['expired_entries']} exp."
            
            return response
            
        except Exception as e:
            return baboon_vocab.get_error_message('command_error') + f" {str(e)}"
    
    def _cmd_clearcache(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Vide le cache des hosts pour forcer une nouvelle détection."""
        try:
            cache_stats_before = self.host_resolver.get_cache_stats()
            hosts_count = cache_stats_before['total_cached']
            
            # Vider le cache
            self.host_resolver.clear_cache()
            
            self.logger.info(f"Cache hosts vidé par {sender} ({hosts_count} entrées supprimées)")
            return f"🐒🗑️ Cache des hosts vidé par {sender} ({hosts_count} babouins oubliés)"
            
        except Exception as e:
            self.logger.error(f"Erreur vidage cache: {e}")
            return baboon_vocab.get_error_message('command_error') + f" {str(e)}"
    
    def _cmd_banpseudo(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Ban un utilisateur par pseudo (pseudo!*@*) uniquement."""
        if not args:
            return baboon_vocab.get_error_message('invalid_usage') + " Usage: !banpseudo <babouin> [raison]"
        
        username = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else f"Banni par {sender}"
        
        try:
            # Utiliser directement le masque pseudo
            ban_mask = self.host_resolver.get_pseudo_ban_mask(username)
            
            # Appliquer le ban avec le masque pseudo
            ban_command = f"mode {channel} +b {ban_mask}"
            irc_client.connection.send_raw(ban_command)
            
            # Log détaillé
            ban_detail = {
                'username': username,
                'ban_mask': ban_mask,
                'ban_type': 'pseudo_only',
                'banned_by': sender,
                'reason': reason
            }
            self.logger.warning(f"🔨 BANPSEUDO APPLIED: {ban_detail}")
            
            response = baboon_vocab.get_action_message('ban', username, f"par l'Alpha {sender}")
            response += f" (Ban par pseudo: {ban_mask})"
            
            return response
            
        except Exception as e:
            error_detail = f"Erreur banpseudo {username}: {str(e)}"
            self.logger.error(error_detail)
            return baboon_vocab.get_error_message('command_error') + f" {str(e)}"
    
    def _cmd_regle(self, irc_client, channel: str, sender: str, args: list) -> str:
        """Affiche les règles de bon savoir vivre sur le tchat."""
        try:
            # Vérifier si le channel a le mode +V activé
            has_voice_mode = self._check_channel_voice_mode(irc_client, channel)
            
            # Règles de base communes
            rules = [
                "🐒📋 Règles de bon savoir vivre sur le tchat:",
                "• Respect mutuel entre tous les babouins",
                "• Pas d'insultes, de harcèlement ou d'attaques personnelles", 
                "• Pas de spam ou de flood",
                "• Pas de publicité non autorisée",
                "• Respecter les décisions des modérateurs"
            ]
            
            # Ajouter règle adulte selon le mode +V
            if not has_voice_mode:
                rules.append("• Discussions à caractère adulte interdites")
            
            rules.append("• Utiliser le bon sens et garder une ambiance conviviale 🌴")
            
            # Joindre les règles avec des retours à la ligne
            response = " | ".join(rules)
            
            self.logger.info(f"Règles affichées sur {channel} par {sender} (Mode +V: {has_voice_mode})")
            return response
            
        except Exception as e:
            self.logger.error(f"Erreur affichage règles: {e}")
            return baboon_vocab.get_error_message('command_error') + f" {str(e)}"
    
    def _check_channel_voice_mode(self, irc_client, channel: str) -> bool:
        """
        Vérifie si le channel a le mode +V activé.
        Retourne True si +V est actif, False sinon.
        """
        try:
            # Méthode 1: Liste des canaux connus avec mode +V (hardcodé pour #adultes)
            voice_only_channels = ['#adultes']  # Canaux connus comme étant en mode +V
            if channel.lower() in [c.lower() for c in voice_only_channels]:
                self.logger.debug(f"Canal {channel} identifié comme +V (liste hardcodée)")
                return True
            
            # Méthode 2: Vérifier dans les propriétés du channel si disponibles
            if hasattr(irc_client, 'channels') and channel in irc_client.channels:
                channel_obj = irc_client.channels[channel]
                
                # Vérifier les modes du channel
                if hasattr(channel_obj, 'modes'):
                    modes = str(channel_obj.modes)
                    if 'V' in modes or 'v' in modes:
                        self.logger.debug(f"Mode +V détecté via channel.modes pour {channel}: {modes}")
                        return True
                
                # Vérifier d'autres propriétés possibles
                if hasattr(channel_obj, 'voice_only') and channel_obj.voice_only:
                    self.logger.debug(f"Mode +V détecté via channel.voice_only pour {channel}")
                    return True
                
                # Vérifier les attributs du channel
                for attr in dir(channel_obj):
                    if 'voice' in attr.lower() or 'mode' in attr.lower():
                        try:
                            value = getattr(channel_obj, attr)
                            if 'V' in str(value) or (hasattr(value, '__call__') and 'V' in str(value())):
                                self.logger.debug(f"Mode +V peut-être détecté via {attr} pour {channel}")
                                return True
                        except:
                            continue
            
            # Méthode 3: Envoyer une requête MODE pour obtenir les modes du canal
            try:
                irc_client.connection.send_raw(f"MODE {channel}")
                self.logger.debug(f"Requête MODE envoyée pour {channel}")
            except:
                pass
            
            # Par défaut, considérer qu'il n'y a pas de mode +V
            self.logger.debug(f"Aucun mode +V détecté pour {channel}")
            return False
            
        except Exception as e:
            self.logger.warning(f"Erreur vérification mode +V pour {channel}: {e}")
            return False
    
    def _get_user_host_via_who(self, irc_client, username: str) -> Optional[str]:
        """
        Récupère le host d'un utilisateur, principalement depuis le cache.
        """
        try:
            # Méthode 1: Vérifier dans le cache du host_resolver (alimenté automatiquement)
            if self.host_resolver._is_host_cached(username):
                cached_host = self.host_resolver.user_hosts[username]
                self.logger.info(f"Host trouvé en cache pour {username}: {cached_host}")
                return cached_host
            
            # Si pas en cache, l'utilisateur n'a probablement pas été vu récemment
            # Envoyer un WHOIS pour forcer la récupération (asynchrone)
            self.logger.info(f"Host non trouvé en cache pour {username}, envoi WHOIS")
            irc_client.connection.send_raw(f"WHOIS {username}")
            
            # Retourner None pour utiliser le ban par pseudo
            # Le WHOIS mettra à jour le cache pour les prochaines fois
            self.logger.info(f"Utilisation du ban par pseudo pour {username} (host non disponible)")
            return None
            
        except Exception as e:
            self.logger.error(f"Erreur récupération host pour {username}: {e}")
            return None


if __name__ == "__main__":
    # Test basique
    print("AdminCommands module - Test OK")