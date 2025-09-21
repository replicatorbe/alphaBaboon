#!/usr/bin/env python3
"""
Vérificateur de privilèges IRC pour AlphaBaboon.
Gère la détection des ops, halfops, voice et exemptions de modération.
"""

import logging
from typing import Optional


class PrivilegeChecker:
    """
    Gestionnaire centralisé pour vérifier les privilèges IRC.
    Supporte op, halfop, voice et exemptions de modération.
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Configuration des exemptions
        self.exempt_ops = config.get('moderation', {}).get('exempt_ops', True)
        self.exempt_halfops = config.get('moderation', {}).get('exempt_halfops', True) 
        self.exempt_voice = config.get('moderation', {}).get('exempt_voice', True)
        
        self.logger.info(f"Exemptions modération: ops={self.exempt_ops}, halfops={self.exempt_halfops}, voice={self.exempt_voice}")
    
    def check_user_privileges(self, irc_client, channel: str, nickname: str) -> dict:
        """
        Vérifie tous les privilèges d'un utilisateur.
        Retourne un dict avec les statuts détectés.
        """
        try:
            if not hasattr(irc_client, 'channels') or channel not in irc_client.channels:
                return {'op': False, 'halfop': False, 'voice': False, 'error': 'Channel not found'}
            
            channel_obj = irc_client.channels[channel]
            
            # Méthode 1: Utiliser les méthodes IRC library
            is_op = False
            is_halfop = False
            is_voice = False
            
            try:
                is_op = channel_obj.is_oper(nickname)
            except:
                pass
            
            try:
                is_halfop = channel_obj.is_halfop(nickname) if hasattr(channel_obj, 'is_halfop') else False
            except:
                pass
            
            try:
                is_voice = channel_obj.is_voiced(nickname) if hasattr(channel_obj, 'is_voiced') else False
            except:
                pass
            
            # Méthode 2: Vérifier les modes utilisateur si disponible
            if not (is_op or is_halfop or is_voice):
                try:
                    if hasattr(channel_obj, 'get_user_modes'):
                        modes = channel_obj.get_user_modes(nickname)
                        if modes:
                            is_op = 'o' in modes
                            is_halfop = 'h' in modes  
                            is_voice = 'v' in modes
                except:
                    pass
            
            # Méthode 3: Parser les préfixes dans la liste des utilisateurs
            if not (is_op or is_halfop or is_voice):
                try:
                    users = channel_obj.users()
                    for user in users:
                        # Certaines libs IRC stockent les préfixes avec le nom
                        if user.lstrip('@%+') == nickname:
                            if user.startswith('@'):
                                is_op = True
                            elif user.startswith('%'):
                                is_halfop = True
                            elif user.startswith('+'):
                                is_voice = True
                            break
                except:
                    pass
            
            result = {
                'op': is_op,
                'halfop': is_halfop, 
                'voice': is_voice,
                'error': None
            }
            
            self.logger.debug(f"Privilèges {nickname} sur {channel}: {result}")
            return result
            
        except Exception as e:
            error_result = {'op': False, 'halfop': False, 'voice': False, 'error': str(e)}
            self.logger.error(f"Erreur vérification privilèges {nickname}: {e}")
            return error_result
    
    def is_admin(self, irc_client, channel: str, nickname: str) -> bool:
        """
        Vérifie si l'utilisateur peut utiliser les commandes admin.
        Admin = op ou halfop.
        """
        privileges = self.check_user_privileges(irc_client, channel, nickname)
        return privileges['op'] or privileges['halfop']
    
    def is_exempt_from_moderation(self, irc_client, channel: str, nickname: str) -> bool:
        """
        Vérifie si l'utilisateur est exempté de la modération automatique.
        Selon la config: ops, halfops, et/ou voice.
        """
        privileges = self.check_user_privileges(irc_client, channel, nickname)
        
        # Vérifier les exemptions selon la configuration
        if privileges['op'] and self.exempt_ops:
            self.logger.debug(f"{nickname} exempté (op)")
            return True
        
        if privileges['halfop'] and self.exempt_halfops:
            self.logger.debug(f"{nickname} exempté (halfop)")
            return True
            
        if privileges['voice'] and self.exempt_voice:
            self.logger.debug(f"{nickname} exempté (voice)")
            return True
        
        return False
    
    def get_user_status_string(self, irc_client, channel: str, nickname: str) -> str:
        """
        Retourne une chaîne décrivant le statut de l'utilisateur.
        """
        privileges = self.check_user_privileges(irc_client, channel, nickname)
        
        if privileges['error']:
            return f"❓ Erreur: {privileges['error']}"
        
        statuses = []
        if privileges['op']:
            statuses.append("🛡️ Alpha")  # Op = Alpha du groupe
        if privileges['halfop']:
            statuses.append("🎯 Lieutenant")  # Halfop = Lieutenant
        if privileges['voice']:
            statuses.append("🗣️ Porte-voix")  # Voice = Porte-voix de la tribu
            
        if not statuses:
            return "🐒 Membre de la tribu"  # Utilisateur normal
        
        return " + ".join(statuses)
    
    def log_privilege_check(self, irc_client, channel: str, nickname: str, action: str):
        """
        Log détaillé d'une vérification de privilèges pour debug.
        """
        privileges = self.check_user_privileges(irc_client, channel, nickname)
        is_exempt = self.is_exempt_from_moderation(irc_client, channel, nickname)
        
        privilege_detail = {
            'user': nickname,
            'channel': channel,
            'action': action,
            'privileges': privileges,
            'is_exempt': is_exempt,
            'config': {
                'exempt_ops': self.exempt_ops,
                'exempt_halfops': self.exempt_halfops,
                'exempt_voice': self.exempt_voice
            }
        }
        
        self.logger.info(f"🔍 PRIVILEGE_CHECK: {privilege_detail}")


if __name__ == "__main__":
    # Test basique
    test_config = {
        'moderation': {
            'exempt_ops': True,
            'exempt_halfops': True,
            'exempt_voice': False
        }
    }
    
    checker = PrivilegeChecker(test_config)
    print("PrivilegeChecker test OK")