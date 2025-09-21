#!/usr/bin/env python3
"""
Dictionnaire de vocabulaire Baboon pour remplacer la terminologie IRC.
Transforme le tchat en vraie jungle de babouins !
"""

import re
from typing import Dict, List


class BaboonVocabulary:
    """
    Gestionnaire du vocabulaire thématique Baboon/jungle.
    Remplace la terminologie IRC par des termes plus fun et thématiques.
    """
    
    def __init__(self):
        # Vocabulaire de base : IRC -> Baboon
        self.vocabulary = {
            # Actions de modération
            'kick': 'DEGOMMER',
            'kicked': 'DEGOMMÉ',
            'kicker': 'DEGOMMER',
            'kické': 'DEGOMMÉ',
            'ban': 'BANNIR',
            'banni': 'BANNI',
            'unban': 'GRACIER',
            'débannir': 'GRACIER',
            'déban': 'GRÂCE',
            
            # Lieux et concepts
            'canal': 'Tribu',
            'canaux': 'Tribus', 
            'salon': 'Tribu',
            'salons': 'Tribus',
            'channel': 'Tribu',
            'channels': 'Tribus',
            'serveur': 'Territoire',
            'server': 'Territoire',
            'réseau': 'Jungle',
            'network': 'Jungle',
            
            # Rôles et statuts
            'op': 'Alpha',
            'ops': 'Alphas',
            'operator': 'Alpha',
            'opérateur': 'Alpha',
            'halfop': 'Lieutenant',
            'halfops': 'Lieutenants',
            'voice': 'Porte-voix',
            'voiced': 'Porte-voix',
            'admin': 'Chef de la jungle',
            'admins': 'Chefs de la jungle',
            'modérateur': 'Gardien',
            'modérateurs': 'Gardiens',
            
            # Utilisateurs
            'utilisateur': 'Babouin',
            'utilisateurs': 'Babouins',
            'user': 'Babouin',
            'users': 'Babouins',
            'membre': 'Membre de la tribu',
            'membres': 'Membres de la tribu',
            'nick': 'Surnom de jungle',
            'nickname': 'Surnom de jungle',
            'pseudo': 'Surnom de jungle',
            
            # Actions générales
            'rejoindre': 'rejoindre la tribu',
            'quitter': 'quitter la tribu',
            'connecter': 'entrer dans la jungle',
            'déconnecter': 'sortir de la jungle',
            'message': 'cri',
            'messages': 'cris',
            'parler': 'crier',
            'dire': 'crier',
            'chat': 'bavardage de singes',
            'discussion': 'palabre de la tribu',
            
            # Violations et problèmes
            'violation': 'bêtise',
            'violations': 'bêtises',
            'avertissement': 'grondement',
            'avertissements': 'grondements',
            'warning': 'grondement',
            'warnings': 'grondements',
            'sanction': 'punition',
            'sanctions': 'punitions',
            'modération': 'discipline de la jungle',
            
            # Émotions et expressions
            'cool': 'tranquille comme un singe',
            'problème': 'embrouille dans la jungle',
            'erreur': 'boulette de babouin',
            'succès': 'victoire de la tribu',
            'échec': 'raté de singe',
            'bienvenue': 'bienvenue dans notre jungle',
            'salut': 'salut fellow babouin',
            'bonjour': 'salutation de la jungle',
            
            # Technique
            'bot': 'AlphaBaboon',
            'robot': 'AlphaBaboon', 
            'système': 'organisation de la jungle',
            'configuration': 'règles de la tribu',
            'log': 'carnet de bord',
            'logs': 'carnets de bord',
            'debug': 'investigation de singe',
            'erreur': 'boulette',
            'bug': 'cafouillage de babouin'
        }
        
        # Expressions complètes à remplacer
        self.expressions = {
            'vous avez été kické': 'tu as été DEGOMMÉ de la tribu',
            'utilisateur kické': 'babouin DEGOMMÉ',
            'kick temporaire': 'DEGOMMAGE temporaire',
            'ban temporaire': 'bannissement temporaire de la jungle',
            'rejoindre le canal': 'rejoindre la tribu',
            'quitter le canal': 'quitter la tribu',
            'sur le canal': 'dans la tribu',
            'dans le salon': 'dans la tribu',
            'modération activée': 'discipline de la jungle activée',
            'bot connecté': 'AlphaBaboon arrive dans la jungle',
            'bot déconnecté': 'AlphaBaboon quitte la jungle',
            'privilèges op': 'statut Alpha',
            'privilèges admin': 'pouvoir de chef',
            'commande admin': 'ordre du chef',
            'violation détectée': 'bêtise détectée',
            'avertissement donné': 'grondement donné',
            'numéro de téléphone': 'numéro de banane', # Plus fun !
            'mot interdit': 'gros mot de singe',
            'contenu inapproprié': 'comportement indigne d\'un babouin'
        }
        
        # Préfixes pour les messages
        self.prefixes = {
            'error': '🐒💥',
            'warning': '🐒⚠️', 
            'info': '🐒ℹ️',
            'success': '🐒✅',
            'action': '🐒⚡',
            'kick': '🐒👢',
            'ban': '🐒🔨',
            'welcome': '🐒🎉'
        }
    
    def baboonify_text(self, text: str) -> str:
        """
        Transforme un texte en utilisant le vocabulaire Baboon.
        """
        result = text
        
        # D'abord remplacer les expressions complètes
        for original, baboon in self.expressions.items():
            # Case insensitive replacement
            pattern = re.compile(re.escape(original), re.IGNORECASE)
            result = pattern.sub(baboon, result)
        
        # Ensuite remplacer les mots individuels
        for original, baboon in self.vocabulary.items():
            # Utiliser word boundaries pour éviter les remplacements partiels
            pattern = r'\b' + re.escape(original) + r'\b'
            result = re.sub(pattern, baboon, result, flags=re.IGNORECASE)
        
        return result
    
    def get_action_message(self, action: str, user: str, reason: str = "") -> str:
        """
        Génère un message d'action avec vocabulaire Baboon.
        """
        prefix = self.prefixes.get(action, '🐒')
        
        if action == 'kick':
            base_msg = f"{prefix} {user} a été DEGOMMÉ de la tribu"
        elif action == 'ban':
            base_msg = f"{prefix} {user} a été banni de la jungle"
        elif action == 'warning':
            base_msg = f"{prefix} {user}, attention ! Grondement de la tribu"
        elif action == 'welcome':
            base_msg = f"{prefix} Bienvenue dans notre jungle {user} !"
        elif action == 'unban':
            base_msg = f"{prefix} {user} a été gracié et peut revenir dans la jungle"
        else:
            base_msg = f"{prefix} Action sur {user}"
        
        if reason:
            baboon_reason = self.baboonify_text(reason)
            base_msg += f" - Raison: {baboon_reason}"
        
        return base_msg
    
    def get_status_message(self, user: str, status_data: dict) -> str:
        """
        Génère un message de statut avec vocabulaire Baboon.
        """
        msg = f"🐒📊 Statut de {user} dans la jungle: "
        
        warnings = status_data.get('warnings', 0)
        kicks = status_data.get('kicks', 0)
        
        if warnings > 0:
            msg += f"⚠️ {warnings} grondement(s), "
        
        if kicks > 0:
            msg += f"👢 {kicks} dégommage(s), "
        
        if status_data.get('violation_types'):
            violations = ', '.join(status_data['violation_types'])
            baboon_violations = self.baboonify_text(violations)
            msg += f"Types de bêtises: {baboon_violations}"
        
        if warnings == 0 and kicks == 0:
            msg += "Sage comme un vieux babouin 🐒✨"
        
        return msg
    
    def get_help_message(self) -> str:
        """
        Message d'aide avec vocabulaire Baboon.
        """
        return (
            "🐒🎯 Commandes du chef de la jungle: "
            "!status <babouin>, !clear <babouin>, !stats, !health, !reload, "
            "!whitelist <add/remove> <babouin>, !blacklist <add/remove> <babouin>, "
            "!badword <add/remove> <gros mot>, !ban <babouin>, !unban <babouin>, "
            "!kick <babouin>, !phonestats"
        )
    
    def get_error_message(self, error_type: str = "generic") -> str:
        """
        Messages d'erreur avec vocabulaire Baboon.
        """
        errors = {
            'no_permission': "🐒❌ Seuls les Alphas et Lieutenants peuvent donner des ordres !",
            'user_not_found': "🐒❓ Ce babouin n'existe pas dans notre jungle...",
            'command_error': "🐒💥 Boulette dans l'exécution de la commande !",
            'invalid_usage': "🐒🤔 Utilisation incorrecte, fellow babouin !",
            'generic': "🐒😵 Quelque chose a foiré dans la jungle..."
        }
        return errors.get(error_type, errors['generic'])


# Instance globale pour usage facile
baboon_vocab = BaboonVocabulary()


if __name__ == "__main__":
    # Tests
    vocab = BaboonVocabulary()
    
    test_texts = [
        "L'utilisateur a été kické du canal",
        "Violation détectée sur le serveur",
        "Le bot est connecté au réseau IRC",
        "Avertissement donné à l'op du salon"
    ]
    
    print("=== TEST VOCABULAIRE BABOON ===")
    for text in test_texts:
        baboonified = vocab.baboonify_text(text)
        print(f"Original: {text}")
        print(f"Baboon:   {baboonified}\n")
    
    print("Messages d'action:")
    print(vocab.get_action_message('kick', 'TestUser', 'comportement inapproprié'))
    print(vocab.get_action_message('welcome', 'NewUser'))
    print(vocab.get_help_message())