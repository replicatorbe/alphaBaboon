#!/usr/bin/env python3
"""
Détecteur de numéros de téléphone pour AlphaBaboon.
Détecte tous les formats de numéros français et internationaux.
"""

import re
import logging
from typing import List, Tuple, Optional


class PhoneNumberDetector:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Patterns pour détecter les numéros de téléphone français
        self.phone_patterns = [
            # Format classique: 06 12 34 56 78 (espaces)
            r'0[1-9](?:\s+\d{2}){4}',
            
            # Format avec points: 06.12.34.56.78
            r'0[1-9](?:\.\d{2}){4}',
            
            # Format avec tirets: 06-12-34-56-78
            r'0[1-9](?:-\d{2}){4}',
            
            # Format collé exact: 0612345678 (10 chiffres)
            r'0[1-9]\d{8}',
            
            # Format international +33: +33 6 12 34 56 78
            r'\+33\s*[1-9](?:\s*\d{2}){4}',
            
            # Format international collé: +33612345678
            r'\+33[1-9]\d{8}',
            
            # Format avec parenthèses: (06) 12 34 56 78
            r'\(0[1-9]\)\s*(?:\d{2}\s*){4}',
            
            # Format mixte espaces irréguliers: 06  12 34  56 78
            r'0[1-9]\s*\d{2}\s*\d{2}\s*\d{2}\s*\d{2}',
            
            # Format avec séparateurs spéciaux: 06_12_34_56_78, 06/12/34/56/78
            r'0[1-9](?:[_/]\d{2}){4}',
            
            # Numéros fixes avec espaces: 01 23 45 67 89
            r'0[1-5](?:\s+\d{2}){4}',
            
            # Numéros fixes collés: 0123456789
            r'0[1-5]\d{8}',
            
            # Numéros spéciaux courts: 3615, 3617, 3618, 3620, etc. (liste restrictive)
            r'\b36(?:15|17|18|20|24|28|29)\b',
            
            # Format international autre pays: +XX XXXXXXXXX
            r'\+\d{2,3}\s*\d{6,12}'
        ]
        
        # Compiler les patterns pour performance
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.phone_patterns]
        
        # Exceptions - patterns à ignorer (faux positifs courants)
        self.exceptions = [
            r'19\d{2}',  # Années 19XX
            r'20\d{2}',  # Années 20XX
            r'[0-2]\d:[0-5]\d',  # Format heure HH:MM
            r'\d+\s*(euro|€|franc|dollars?|USD)',  # Prix
            r'https?://[^\s]+',  # URLs complètes
            r'www\.[^\s]+',  # URLs www
            r'[a-zA-Z0-9.-]+\.(?:fr|com|net|org)[^\s]*',  # Domaines
            r'cam\.baboon\.fr[^\s]*',  # URLs webcam Baboon spécifiquement
        ]
        
        self.exception_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.exceptions]

    def detect_phone_numbers(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Détecte tous les numéros de téléphone dans un texte.
        
        Returns:
            List[Tuple[str, int, int]]: Liste des (numéro_trouvé, position_début, position_fin)
        """
        found_numbers = []
        
        for pattern in self.compiled_patterns:
            for match in pattern.finditer(text):
                number = match.group()
                start, end = match.span()
                
                # Vérifier si ce n'est pas une exception
                if not self._is_exception(number, text, start, end):
                    found_numbers.append((number, start, end))
                    self.logger.debug(f"Numéro détecté: '{number}' position {start}-{end}")
        
        # Supprimer les doublons (même position)
        found_numbers = list(set(found_numbers))
        
        # Trier par position
        found_numbers.sort(key=lambda x: x[1])
        
        return found_numbers

    def _is_exception(self, number: str, full_text: str, start: int, end: int) -> bool:
        """Vérifie si le numéro détecté est en fait une exception (année, heure, etc.)."""
        
        # Vérifier si le numéro fait partie d'un pseudonyme (entouré de lettres/chiffres)
        if start > 0 and full_text[start-1].isalnum():
            # Il y a une lettre ou un chiffre juste avant le numéro
            if end < len(full_text) and full_text[end].isalnum():
                # Il y a aussi une lettre ou un chiffre juste après
                self.logger.debug(f"Exception pseudonyme détectée: '{number}' fait partie d'un nom d'utilisateur")
                return True
        
        # Vérifier contre les patterns d'exception sur le numéro seul
        for exception_pattern in self.exception_patterns:
            if exception_pattern.match(number):
                self.logger.debug(f"Exception détectée: '{number}' (pattern d'exception)")
                return True
        
        # Vérifier si le numéro fait partie d'une URL
        # Chercher s'il y a une URL qui CONTIENT ce numéro
        url_patterns = [
            r'https?://[^\s]*' + re.escape(number) + r'[^\s]*',
            r'www\.[^\s]*' + re.escape(number) + r'[^\s]*',
            r'[a-zA-Z0-9.-]+\.(?:fr|com|net|org)[^\s]*' + re.escape(number) + r'[^\s]*',
        ]
        
        for url_pattern in url_patterns:
            if re.search(url_pattern, full_text):
                self.logger.debug(f"Exception URL détectée: '{number}' fait partie d'une URL")
                return True
        
        # Contexte autour du numéro pour détecter les faux positifs
        context_start = max(0, start - 20)
        context_end = min(len(full_text), end + 20)
        context = full_text[context_start:context_end].lower()
        
        # Faux positifs contextuels (mais PAS pour numéros de téléphone)
        false_positive_contexts = [
            'année', 'an ', ' ans', 'depuis', 'en 19', 'en 20', 'vers 19', 'vers 20',
            'heures', 'heure', 'h ', ' h:',
            'prix', 'euro', '€', 'coût', 'coute', 'tarif',
            'page', 'ligne', 'article', 'référence', 'ref ',
            # Retirer 'numéro de' car souvent suivi d'un vrai numéro de téléphone
        ]
        
        for fp_context in false_positive_contexts:
            if fp_context in context:
                self.logger.debug(f"Exception contextuelle: '{number}' dans contexte '{context}'")
                return True
        
        return False

    def has_phone_number(self, text: str) -> bool:
        """Vérifie rapidement si le texte contient un numéro de téléphone."""
        return len(self.detect_phone_numbers(text)) > 0

    def extract_clean_numbers(self, text: str) -> List[str]:
        """Extrait les numéros nettoyés (sans espaces/séparateurs) pour storage/comparaison."""
        numbers = self.detect_phone_numbers(text)
        clean_numbers = []
        
        for number, _, _ in numbers:
            # Nettoyer le numéro: supprimer espaces, points, tirets, parenthèses
            clean = re.sub(r'[^\d+]', '', number)
            
            # Normaliser format international
            if clean.startswith('+33'):
                clean = '0' + clean[3:]  # +33123456789 -> 0123456789
            elif clean.startswith('33') and len(clean) == 11:
                clean = '0' + clean[2:]  # 33123456789 -> 0123456789
            
            clean_numbers.append(clean)
        
        return clean_numbers

    def get_number_info(self, number: str) -> dict:
        """Retourne des informations sur le type de numéro détecté."""
        clean_number = re.sub(r'[^\d]', '', number)
        
        if clean_number.startswith('06') or clean_number.startswith('07'):
            return {'type': 'mobile', 'operator': 'mobile', 'risk': 'high'}
        elif clean_number.startswith('01') or clean_number.startswith('02') or \
             clean_number.startswith('03') or clean_number.startswith('04') or \
             clean_number.startswith('05'):
            return {'type': 'fixe', 'operator': 'fixe', 'risk': 'medium'}
        elif clean_number.startswith('08'):
            return {'type': 'special', 'operator': 'surtaxé', 'risk': 'high'}
        elif clean_number.startswith('09'):
            return {'type': 'voip', 'operator': 'internet', 'risk': 'medium'}
        else:
            return {'type': 'unknown', 'operator': 'unknown', 'risk': 'high'}


# Test unitaire si exécuté directement
if __name__ == "__main__":
    detector = PhoneNumberDetector()
    
    test_messages = [
        "appelle moi au 06 12 34 56 78",
        "mon numéro: 0612345678",
        "contacte moi +33 6 12 34 56 78",
        "je suis du 59, tel: 06.12.34.56.78",
        "whatsapp 06-12-34-56-78",
        "on était en 2023, vers 15h30",  # Should not detect
        "j'ai 25 ans depuis 2020",  # Should not detect
        "prix: 1234 euros",  # Should not detect
        "fixe: 01 23 45 67 89",
        "tel (06) 12 34 56 78 dispo",
        "06  12 34  56 78 libre ce soir"
    ]
    
    print("=== TEST DÉTECTEUR DE NUMÉROS ===")
    for msg in test_messages:
        numbers = detector.detect_phone_numbers(msg)
        has_phone = detector.has_phone_number(msg)
        clean_nums = detector.extract_clean_numbers(msg)
        
        print(f"\nMessage: '{msg}'")
        print(f"Contient numéro: {has_phone}")
        if numbers:
            for num, start, end in numbers:
                info = detector.get_number_info(num)
                print(f"  - Trouvé: '{num}' pos {start}-{end} | Type: {info['type']} | Risque: {info['risk']}")
            print(f"  - Numéros nettoyés: {clean_nums}")