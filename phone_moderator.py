#!/usr/bin/env python3
"""
Modérateur de numéros de téléphone pour AlphaBaboon.
Système d'avertissement progressif et ban automatique.
"""

import time
import logging
from typing import Dict, List, Optional, Tuple
from phone_number_detector import PhoneNumberDetector


class PhoneModerator:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.detector = PhoneNumberDetector()
        
        # Historique des violations par utilisateur
        self.user_violations = {}  # {username: {'warnings': count, 'numbers': [list], 'last_violation': timestamp}}
        
        # Configuration des avertissements
        self.warning_threshold = config.get('phone_moderation', {}).get('warning_threshold', 1)  # 1 avertissement avant ban
        self.ban_duration_hours = config.get('phone_moderation', {}).get('ban_duration_hours', 24)
        self.violation_reset_hours = config.get('phone_moderation', {}).get('violation_reset_hours', 48)
        
        # Messages d'avertissement rotatifs pour éviter la répétition
        self.warning_messages = [
            "Salut {user} ! 😊 Je t'informe gentiment que partager des numéros de téléphone en public n'est pas autorisé sur {channel}. Tu peux utiliser les messages privés pour ça ! Merci de ta compréhension 💛",
            "Hello {user} ! 🌟 Petit rappel sympa : les numéros de téléphone sont à éviter en public sur {channel}. Utilise plutôt les MP pour ce genre d'info ! Bisous 💋",
            "Coucou {user} ! 👋 Je dois te rappeler amicalement qu'on ne partage pas les numéros de tél en public ici. Garde ça pour les discussions privées stp ! Merci beaucoup 🙏",
            "Hey {user} ! 😄 Alors, on évite de donner son numéro comme ça en public sur {channel}, d'accord ? Les MP sont là pour ça ! Merci de faire attention 💖"
        ]
        
        # Messages de ban (plus sérieux mais toujours polis)
        self.ban_messages = [
            "Désolé {user}, mais tu as déjà été prévenu concernant les numéros de téléphone. Je dois te mettre en sourdine temporairement sur {channel}. Tu pourras revenir parler dans quelques heures ! 🤐",
            "{user}, j'ai dû te mettre en mode silencieux sur {channel} car tu continues à partager des numéros malgré l'avertissement. À bientôt ! 🔇",
            "Sorry {user}, mais règle non respectée = sourdine temporaire sur {channel}. Tu pourras revenir discuter plus tard sans problème ! 😌"
        ]
        
    def check_phone_numbers(self, message: str, sender: str, channel: str) -> Tuple[bool, Optional[dict]]:
        """
        Vérifie si un message contient des numéros de téléphone et retourne l'action à prendre.
        
        Returns:
            Tuple[bool, Optional[dict]]: (has_phone_numbers, action_info)
            action_info = {
                'action': 'warn' | 'ban' | 'none',
                'message': str,  # Message à envoyer
                'numbers': List[str],  # Numéros détectés
                'user_violations': int  # Nombre total de violations
            }
        """
        numbers = self.detector.detect_phone_numbers(message)
        
        if not numbers:
            return False, None
        
        # Extraire les numéros nettoyés
        clean_numbers = []
        detected_numbers = []
        for number, start, end in numbers:
            detected_numbers.append(number)
            clean_numbers.extend(self.detector.extract_clean_numbers(number))
        
        self.logger.info(f"Numéros détectés de {sender} sur {channel}: {detected_numbers}")
        
        # Mettre à jour les violations de l'utilisateur
        action_info = self._update_user_violations(sender, clean_numbers, channel)
        
        return True, action_info
    
    def _update_user_violations(self, username: str, numbers: List[str], channel: str) -> dict:
        """Met à jour les violations d'un utilisateur et détermine l'action."""
        current_time = time.time()
        username_lower = username.lower()
        
        # Initialiser ou récupérer l'historique de l'utilisateur
        if username_lower not in self.user_violations:
            self.user_violations[username_lower] = {
                'warnings': 0,
                'numbers': [],
                'last_violation': current_time,
                'banned_until': 0
            }
        
        user_data = self.user_violations[username_lower]
        
        # Vérifier si les violations précédentes ont expiré
        if current_time - user_data['last_violation'] > (self.violation_reset_hours * 3600):
            self.logger.info(f"Reset des violations pour {username} (expirées)")
            user_data['warnings'] = 0
            user_data['numbers'] = []
        
        # Vérifier si l'utilisateur est encore banni
        if current_time < user_data['banned_until']:
            time_left = int((user_data['banned_until'] - current_time) / 3600)
            self.logger.info(f"{username} encore banni pour {time_left}h")
            return {
                'action': 'none',  # Ne rien faire, déjà banni
                'message': '',
                'numbers': numbers,
                'user_violations': user_data['warnings']
            }
        
        # Ajouter les nouveaux numéros
        user_data['numbers'].extend(numbers)
        user_data['last_violation'] = current_time
        
        # Déterminer l'action selon le nombre d'avertissements
        if user_data['warnings'] >= self.warning_threshold:
            # Ban l'utilisateur
            user_data['banned_until'] = current_time + (self.ban_duration_hours * 3600)
            
            ban_message = self._get_ban_message(username, channel)
            
            self.logger.warning(f"Ban de {username} sur {channel} pour {self.ban_duration_hours}h")
            
            return {
                'action': 'ban',
                'message': ban_message,
                'numbers': numbers,
                'user_violations': user_data['warnings'],
                'ban_duration_hours': self.ban_duration_hours
            }
        else:
            # Avertissement
            user_data['warnings'] += 1
            
            warning_message = self._get_warning_message(username, channel, user_data['warnings'])
            
            self.logger.info(f"Avertissement {user_data['warnings']} pour {username} sur {channel}")
            
            return {
                'action': 'warn',
                'message': warning_message,
                'numbers': numbers,
                'user_violations': user_data['warnings']
            }
    
    def _get_warning_message(self, username: str, channel: str, warning_count: int) -> str:
        """Retourne un message d'avertissement rotatif."""
        # Utiliser le warning_count pour la rotation
        message_index = (warning_count - 1) % len(self.warning_messages)
        message_template = self.warning_messages[message_index]
        
        return message_template.format(user=username, channel=channel)
    
    def _get_ban_message(self, username: str, channel: str) -> str:
        """Retourne un message de ban rotatif."""
        # Rotation basée sur l'heure pour varier
        message_index = int(time.time() / 3600) % len(self.ban_messages)
        message_template = self.ban_messages[message_index]
        
        return message_template.format(user=username, channel=channel)
    
    def get_user_stats(self, username: str) -> Optional[dict]:
        """Retourne les statistiques d'un utilisateur."""
        username_lower = username.lower()
        if username_lower not in self.user_violations:
            return None
        
        user_data = self.user_violations[username_lower]
        current_time = time.time()
        
        return {
            'username': username,
            'warnings': user_data['warnings'],
            'numbers_shared': len(user_data['numbers']),
            'last_violation': user_data['last_violation'],
            'banned_until': user_data['banned_until'],
            'is_banned': current_time < user_data['banned_until'],
            'time_until_unban': max(0, int((user_data['banned_until'] - current_time) / 3600))
        }
    
    def reset_user_violations(self, username: str) -> bool:
        """Remet à zéro les violations d'un utilisateur (commande admin)."""
        username_lower = username.lower()
        if username_lower in self.user_violations:
            del self.user_violations[username_lower]
            self.logger.info(f"Violations reset pour {username}")
            return True
        return False
    
    def get_stats_summary(self) -> dict:
        """Retourne un résumé des statistiques de modération."""
        current_time = time.time()
        
        total_users = len(self.user_violations)
        warned_users = sum(1 for u in self.user_violations.values() if u['warnings'] > 0)
        banned_users = sum(1 for u in self.user_violations.values() if current_time < u['banned_until'])
        total_numbers = sum(len(u['numbers']) for u in self.user_violations.values())
        
        return {
            'total_users_tracked': total_users,
            'users_with_warnings': warned_users,
            'currently_banned': banned_users,
            'total_phone_numbers_detected': total_numbers,
            'warning_threshold': self.warning_threshold,
            'ban_duration_hours': self.ban_duration_hours
        }


# Test unitaire
if __name__ == "__main__":
    # Configuration de test
    test_config = {
        'phone_moderation': {
            'warning_threshold': 1,  # 1 avertissement avant ban
            'ban_duration_hours': 24,
            'violation_reset_hours': 48
        }
    }
    
    moderator = PhoneModerator(test_config)
    
    # Simulation de violations
    print("=== TEST MODÉRATEUR NUMÉROS ===\n")
    
    # Premier message avec numéro
    has_phone, action = moderator.check_phone_numbers(
        "salut appelle moi au 06 12 34 56 78", 
        "TestUser", 
        "#francophonie"
    )
    
    print(f"Message 1: Numéro détecté: {has_phone}")
    if action:
        print(f"Action: {action['action']}")
        print(f"Message: {action['message']}")
        print()
    
    # Deuxième message (devrait causer un ban)
    has_phone2, action2 = moderator.check_phone_numbers(
        "mon tel: 0687654321", 
        "TestUser", 
        "#francophonie"
    )
    
    print(f"Message 2: Numéro détecté: {has_phone2}")
    if action2:
        print(f"Action: {action2['action']}")
        print(f"Message: {action2['message']}")
        print()
    
    # Stats utilisateur
    stats = moderator.get_user_stats("TestUser")
    print(f"Stats TestUser: {stats}")
    
    # Stats générales
    summary = moderator.get_stats_summary()
    print(f"Résumé: {summary}")