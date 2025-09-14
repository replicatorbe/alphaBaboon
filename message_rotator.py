import random
import logging
from datetime import datetime
from typing import List, Dict


class MessageRotator:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.redirect_channel = config['irc']['redirect_channel']
        
        # Historique des messages utilisés pour éviter les répétitions
        self.message_history = []
        self.max_history = 10  # Éviter la répétition des 10 derniers messages
        
        # Messages de base (seront complétés par les messages temporels)
        self.base_redirect_messages = [
            f"🐒 @{{user}}, je t'emmène sur {self.redirect_channel} pour ce genre de discussion ! 😉",
            f"🔥 @{{user}}, hop direction {self.redirect_channel} pour les sujets chauds ! 🌶️", 
            f"😊 @{{user}}, {self.redirect_channel} sera parfait pour continuer cette conversation !",
            f"🐒 @{{user}}, allez zou ! {self.redirect_channel} t'attend pour parler de ça ! 😄",
            f"🌶️ @{{user}}, ce sujet a sa place sur {self.redirect_channel} ! On y va ? 😊",
            f"🔄 @{{user}}, petit déménagement vers {self.redirect_channel} pour cette discussion ! 🏠",
            f"🎯 @{{user}}, {self.redirect_channel} est le bon endroit pour ça ! Je t'y emmène ! 🚀",
            f"💫 @{{user}}, direction {self.redirect_channel} pour approfondir le sujet ! ✨"
        ]
        
        # Messages d'accueil de base
        self.base_welcome_messages = [
            f"🐒 Salut {{user}} ! Tu peux parler librement de sujets adultes ici, c'est fait pour ça ! 😊",
            f"🔥 Hey {{user}} ! Bienvenue sur {self.redirect_channel}, ici c'est le bon endroit pour ce genre de discussion ! 😉",
            f"🌶️ Coucou {{user}} ! Sur {self.redirect_channel} on peut aborder tous les sujets, fais-toi plaisir ! 😄",
            f"✨ Bienvenue {{user}} ! {self.redirect_channel} est ton espace de liberté pour ces discussions ! 🎉",
            f"🎯 {{user}}, tu es maintenant dans le bon salon ! Ici pas de limites ! 💬",
            f"🌟 Salut {{user}} ! {self.redirect_channel} t'accueille pour tes discussions sans tabou ! 🗣️",
            f"🔓 Hey {{user}} ! Zone libre activée sur {self.redirect_channel} ! Parle sans contraintes ! 🎊"
        ]

    def get_redirect_message(self, user: str, context: str = None) -> str:
        """Retourne un message de redirection en évitant les répétitions."""
        current_hour = datetime.now().hour
        
        # Ajouter des messages contextuels selon l'heure
        time_specific_messages = self._get_time_specific_redirect_messages(current_hour)
        
        # Combiner les messages de base et temporels
        all_messages = self.base_redirect_messages + time_specific_messages
        
        # Filtrer les messages récemment utilisés
        available_messages = [
            msg for msg in all_messages 
            if msg not in self.message_history
        ]
        
        # Si tous les messages ont été utilisés récemment, réinitialiser l'historique
        if not available_messages:
            available_messages = all_messages
            self.message_history.clear()
        
        # Choisir un message au hasard
        chosen_message = random.choice(available_messages)
        
        # Ajouter à l'historique
        self.message_history.append(chosen_message)
        if len(self.message_history) > self.max_history:
            self.message_history.pop(0)
        
        return chosen_message.format(user=user)

    def get_welcome_message(self, user: str) -> str:
        """Retourne un message d'accueil contextuel."""
        current_hour = datetime.now().hour
        
        # Ajouter des messages contextuels selon l'heure
        time_specific_messages = self._get_time_specific_welcome_messages(current_hour)
        
        # Combiner les messages de base et temporels
        all_messages = self.base_welcome_messages + time_specific_messages
        
        # Sélection aléatoire
        chosen_message = random.choice(all_messages)
        
        return chosen_message.format(user=user)

    def _get_time_specific_redirect_messages(self, hour: int) -> List[str]:
        """Retourne des messages de redirection adaptés à l'heure."""
        redirect_channel = self.redirect_channel
        
        if 6 <= hour < 12:  # Matin
            return [
                f"☀️ @{{user}}, pour bien commencer la journée, direction {redirect_channel} ! 🌅",
                f"🌤️ @{{user}}, matinée épicée en vue ? {redirect_channel} t'attend ! ☕"
            ]
        elif 12 <= hour < 14:  # Midi  
            return [
                f"🍽️ @{{user}}, pause déjeuner coquine ? {redirect_channel} pour l'apéritif ! 🥂",
                f"☀️ @{{user}}, midi bien chaud ! Direction {redirect_channel} ! 🌡️"
            ]
        elif 14 <= hour < 18:  # Après-midi
            return [
                f"🌞 @{{user}}, l'après-midi se réchauffe ! {redirect_channel} pour la suite ! 🔥",
                f"☕ @{{user}}, pause café épicée ? {redirect_channel} est parfait ! ☕"
            ]
        elif 18 <= hour < 22:  # Soirée
            return [
                f"🌆 @{{user}}, soirée qui commence bien ! {redirect_channel} pour la détente ! 🍷",
                f"🔥 @{{user}}, l'apéro se corse ! {redirect_channel} pour continuer ! 🍻"
            ]
        else:  # Nuit (22h-6h)
            return [
                f"🌙 @{{user}}, nuit coquine en perspective ? {redirect_channel} t'accueille ! ✨",
                f"🌟 @{{user}}, les nuits sont faites pour ça ! Direction {redirect_channel} ! 🌛"
            ]

    def _get_time_specific_welcome_messages(self, hour: int) -> List[str]:
        """Retourne des messages d'accueil adaptés à l'heure."""
        redirect_channel = self.redirect_channel
        
        if 6 <= hour < 12:  # Matin
            return [
                f"🌅 Bonjour {{user}} ! {redirect_channel} pour un réveil en douceur ! ☀️",
                f"☕ Salut {{user}} ! Café et discussions libres sur {redirect_channel} ! 🌤️"
            ]
        elif 12 <= hour < 14:  # Midi
            return [
                f"🍽️ Bon appétit {{user}} ! {redirect_channel} pour digérer en beauté ! 😋",
                f"🥂 {{user}}, pause déjeuner détente sur {redirect_channel} ! Santé ! 🍷"
            ]
        elif 14 <= hour < 18:  # Après-midi
            return [
                f"☀️ {{user}}, {redirect_channel} pour une après-midi détendue ! 🌞",
                f"☕ Bienvenue {{user}} ! {redirect_channel} pour ta pause bien méritée ! 😌"
            ]
        elif 18 <= hour < 22:  # Soirée
            return [
                f"🌆 Bonsoir {{user}} ! {redirect_channel} pour une soirée décontractée ! 🍷",
                f"🔥 {{user}}, soirée sympa en vue sur {redirect_channel} ! Profite bien ! 🎉"
            ]
        else:  # Nuit
            return [
                f"🌙 Bonsoir {{user}} ! {redirect_channel} pour des nuits étoilées ! ✨",
                f"🌟 {{user}}, nuit libre sur {redirect_channel} ! Fais-toi plaisir ! 🌛"
            ]

    def get_stats(self) -> Dict:
        """Retourne les statistiques du rotateur de messages."""
        return {
            'total_redirect_messages': len(self.base_redirect_messages),
            'total_welcome_messages': len(self.base_welcome_messages),
            'recent_messages_used': len(self.message_history),
            'max_history_size': self.max_history,
            'current_hour': datetime.now().hour
        }