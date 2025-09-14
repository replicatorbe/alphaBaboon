import re
import logging
from typing import Tuple, List, Dict


class DrugDetector:
    """
    Détecteur de références aux drogues en français pour compléter OpenAI.
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.sensitivity = config.get('drug_detection', {}).get('sensitivity', 4.0)
        
        # Patterns de base pour drogues
        self.drug_patterns = [
            # Cannabis et dérivés
            r'\b(cannabis|weed|shit|bheu|beuh|marie?-?jeanne|ganja|herb|herbe)\b',
            r'\b(joint|spliff|pétard|bédo|bedo|stick)\b',
            r'\b(hash|hasch|hashish|pollen|résine)\b',
            
            # Cocaïne
            r'\b(cocaïne|cocaine|coke|coca|poudre|neige|blanche)\b',
            r'\b(crack|rock|caillou)\b',
            
            # Héroïne et opiacés
            r'\b(héroïne|heroine|hero|héro|smack|brown|brune)\b',
            r'\b(morphine|opium|fentanyl)\b',
            
            # Drogues de synthèse
            r'\b(ecstasy|ecsta|taz|mdma|molly)\b',
            r'\b(speed|amphét|amphétamines?|crystal|ice)\b',
            r'\b(lsd|acide|buvard|carton)\b',
            r'\b(ketamine|keta|special[_\-]?k)\b',
            r'\b(ghb|drogue\s+du\s+viol)\b',
            
            # Autres drogues
            r'\b(champis?|champi|psilos?|magic|mushroom)\b',
            r'\b(poppers|solvants?)\b',
            r'\b(méthadone|subutex|sub)\b',
        ]
        
        # Patterns d'action (vente, achat, etc.)
        self.action_patterns = [
            r'\b(vend[s]?|vente|vendre|à\s+vendre|dispo|disponible)\b',
            r'\b(achète?|achat|acheter|cherche|recherche)\b',
            r'\b(livre?|livraison|livrer)\b',
            r'\b(deal|dealer|contact)\b',
            r'\b(fourni[st]?|fournir|source)\b',
            r'\b(commande|commander)\b',
        ]
        
        # Patterns de quantité/prix
        self.quantity_patterns = [
            r'\b\d+\s*(g|gr|grammes?|kilos?|kg)\b',
            r'\b\d+\s*€\b',
            r'\b(barrette|sachet|pochon|stick)\b',
            r'\b(petit|gros|demi|quart)\b',
        ]
        
        # Patterns de lieux (souvent utilisés pour deals)
        self.location_patterns = [
            r'\b(bordeaux|paris|lyon|marseille|toulouse|nantes|strasbourg)\b',
            r'\b(gare|station|métro|parking|parc)\b',
            r'\b(\d{2})\b',  # Codes postaux
        ]
        
        # Patterns d'urgence/discrétion
        self.urgency_patterns = [
            r'\b(urgent|vite|rapide|immédiat)\b',
            r'\b(discret|discrète|planqué|caché)\b',
            r'\b(sûr|sécurisé|fiable)\b',
        ]
        
        # Compiler tous les patterns
        self.compiled_drug_patterns = [re.compile(p, re.IGNORECASE) for p in self.drug_patterns]
        self.compiled_action_patterns = [re.compile(p, re.IGNORECASE) for p in self.action_patterns]
        self.compiled_quantity_patterns = [re.compile(p, re.IGNORECASE) for p in self.quantity_patterns]
        self.compiled_location_patterns = [re.compile(p, re.IGNORECASE) for p in self.location_patterns]
        self.compiled_urgency_patterns = [re.compile(p, re.IGNORECASE) for p in self.urgency_patterns]

    def analyze_message(self, message: str) -> Tuple[bool, float, List[str]]:
        """
        Analyse un message pour détecter des références aux drogues.
        
        Returns:
            Tuple[is_drug_related, confidence_score, detected_patterns]
        """
        detected_elements = []
        score = 0.0
        
        # Nettoyer le message
        cleaned_message = self._clean_message(message)
        
        # 1. Détecter les drogues mentionnées
        drug_matches = []
        for pattern in self.compiled_drug_patterns:
            matches = pattern.findall(cleaned_message)
            if matches:
                drug_matches.extend(matches)
                detected_elements.append(f"drogue:{matches[0]}")
        
        if drug_matches:
            score += 3.0  # Base score pour mention de drogue
            
            # 2. Bonus si actions de vente/achat
            action_matches = []
            for pattern in self.compiled_action_patterns:
                matches = pattern.findall(cleaned_message)
                if matches:
                    action_matches.extend(matches)
                    detected_elements.append(f"action:{matches[0]}")
            
            if action_matches:
                score += 4.0  # Bonus important pour action commerciale
                
                # 3. Bonus pour quantités/prix
                quantity_matches = []
                for pattern in self.compiled_quantity_patterns:
                    matches = pattern.findall(cleaned_message)
                    if matches:
                        quantity_matches.extend(matches)
                        detected_elements.append(f"quantité:{matches[0]}")
                
                if quantity_matches:
                    score += 2.0
                
                # 4. Bonus pour géolocalisation
                location_matches = []
                for pattern in self.compiled_location_patterns:
                    matches = pattern.findall(cleaned_message)
                    if matches:
                        location_matches.extend(matches)
                        detected_elements.append(f"lieu:{matches[0]}")
                
                if location_matches:
                    score += 1.5
                
                # 5. Bonus pour urgence/discrétion
                urgency_matches = []
                for pattern in self.compiled_urgency_patterns:
                    matches = pattern.findall(cleaned_message)
                    if matches:
                        urgency_matches.extend(matches)
                        detected_elements.append(f"urgence:{matches[0]}")
                
                if urgency_matches:
                    score += 1.0
        
        # Calculs spéciaux pour certaines combinaisons
        if drug_matches and action_matches and len(cleaned_message.split()) <= 8:
            # Messages courts avec drogue + action = très suspect
            score += 2.0
            detected_elements.append("format_suspect")
        
        # Normaliser le score sur 10
        final_score = min(score, 10.0)
        is_drug_related = final_score >= self.sensitivity
        
        if detected_elements:
            self.logger.info(f"Analyse drogue: score={final_score:.1f}, éléments={detected_elements}")
        
        return is_drug_related, final_score, detected_elements

    def _clean_message(self, message: str) -> str:
        """Nettoie le message pour améliorer la détection."""
        # Remplacer les caractères spéciaux utilisés pour contourner les filtres
        message = re.sub(r'[0@]', 'o', message)
        message = re.sub(r'[3€]', 'e', message) 
        message = re.sub(r'[1!|]', 'i', message)
        message = re.sub(r'[5$]', 's', message)
        message = re.sub(r'[4@]', 'a', message)
        
        # Supprimer la ponctuation excessive
        message = re.sub(r'[\.]{2,}', ' ', message)
        message = re.sub(r'[!]{2,}', '!', message)
        message = re.sub(r'[\s]{2,}', ' ', message)
        
        return message.strip()

    def get_violation_type(self, detected_elements: List[str]) -> str:
        """Détermine le type de violation selon les éléments détectés."""
        has_action = any('action:' in elem for elem in detected_elements)
        has_quantity = any('quantité:' in elem for elem in detected_elements)
        
        if has_action and has_quantity:
            return "traffic_de_drogue"
        elif has_action:
            return "commerce_illegal"
        else:
            return "reference_drogue"

    def get_detection_summary(self, detected_elements: List[str]) -> str:
        """Génère un résumé des éléments détectés."""
        if not detected_elements:
            return ""
        
        summary_parts = []
        drugs = [elem.split(':')[1] for elem in detected_elements if elem.startswith('drogue:')]
        actions = [elem.split(':')[1] for elem in detected_elements if elem.startswith('action:')]
        
        if drugs:
            summary_parts.append(f"Drogues: {', '.join(drugs)}")
        if actions:
            summary_parts.append(f"Actions: {', '.join(actions)}")
        
        return " | ".join(summary_parts)