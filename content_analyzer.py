import openai
import logging
import time
import re
from typing import Optional, Tuple
from message_cache import MessageCache


class ContentAnalyzer:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        try:
            self.client = openai.OpenAI(api_key=config['openai']['api_key'])
        except TypeError as e:
            # Fallback pour anciennes versions d'OpenAI
            self.logger.warning(f"Erreur d'initialisation OpenAI: {e}")
            self.logger.info("Tentative avec initialisation basique...")
            import openai as openai_legacy
            openai_legacy.api_key = config['openai']['api_key']
            self.client = openai_legacy
        self.use_moderation_api = config['openai'].get('use_moderation_api', True)
        self.moderation_model = config['openai'].get('moderation_model', 'omni-moderation-latest')
        self.sensitivity = config['moderation']['sensitivity']
        self.last_request_time = 0
        self.min_request_interval = 0.1  # Plus rapide car API Moderation gratuite
        
        # Cache pour économiser les requêtes OpenAI
        self.cache = MessageCache(
            cache_duration_hours=config['moderation'].get('cache_hours', 24),
            max_cache_size=config['moderation'].get('cache_size', 1000)
        )
        
        # Whitelist d'utilisateurs de confiance
        self.trusted_users = set(config['moderation'].get('trusted_users', []))
        
        # Analyse comportementale des utilisateurs
        self.user_behavior = {}  # {username: {'messages': [], 'scores': [], 'last_activity': timestamp}}
        self.behavior_window = 3600  # 1 heure pour l'analyse comportementale
        
        # Mots-clés pour détection rapide AVANT OpenAI (adapté pour contexte Baboon)
        self.adult_keywords = {
            'explicit': [
                r'\bsex[eo]?\b', r'\bbais[eé]r\b', r'\bbaisais\b', r'\bbite\b', r'\bchatte\b', 
                r'\bseins?\b', r'\bnichons?\b', r'\bvagina?\b', r'\bpénis\b',
                r'\borgasme\b', r'\bjouir\b', r'\bmasturbation\b', r'\bérection\b',
                r'\bsodomie\b', r'\bfellation\b', r'\bcunnilingus\b', r'\bcunni\b', r'\bporn\b',
                r'\bqueue\b', r'\bcul\b', r'\bbranler?\b', r'\btailler?\b.*\bpipe\b'
            ],
            'suggestive': [
                r'\bchaud[es]?\b.*\b(discussion|sujet)\b', r'\bépicé[es]?\b',
                r'\bintime[s]?\b', r'\bérotique\b', r'\bsensuel[les]?\b',
                r'\bexcité[es]?\b', r'\ballumé[es]?\b', r'\bcoquin[es]?\b',
                r'\bsexy?\b', r'\bhot\b', r'\bkinky?\b'
            ],
            'drague_rencontre': [
                # Patterns existants
                r'\bmatter\b.*\b(femmes?|mecs?|gens?)\b', r'\bdrague\b', r'\bactif\b.*\bprivé\b',
                r'\bweb\s*cam\b', r'\bcamerka\b', r'\bbc?am\b',
                r'\bplan\s*cul\b', r'\bplan\s*q\b', r'\brdv\b.*\b(sexe?|coquin)\b',
                r'\brencontre\b.*\b(sexe?|adulte|coquin|hot)\b',
                r'\bcherche\b.*\b(femme|mec|partenaire)\b.*\b(sexe?|plan|cam)\b',
                # Nouveaux patterns avancés
                r"\bgenre\s+d['']actif\b", r'\bactif\s+du?\b.*\d{2}\b',
                r'\bpassif\s+du?\b.*\d{2}\b', r'\bvers[ao]\s+du?\b.*\d{2}\b',
                r'\bdu?\s+\d{2}\b.*\b(dispo|libre|actif|passif)\b',
                r'\bdispo\b.*\b(maintenant|là|ce\s+soir|tonight)\b',
                r'\blibre\b.*\b(maintenant|là|ce\s+soir|pour\s+plan)\b',
                r'\b(jeune|mûr)\b.*\b(cherche|dispo|actif)\b',
                r'\bâge?\b.*\b(cherche|pour|avec)\b.*\b(plan|sexe|rencontre)\b',
                # Patterns détectés manquants par OpenAI
                r'\bfun\b.*\b(entre\s+)?adultes?\b', r'\bpour\s+du\s+fun\b',
                r'\bcoucher\s+avec\b', r'\bveut\s+coucher\b',
                r'\brelation\s+intime\b', r'\bmoments?\s+intimes?\b',
                # Patterns orientation sexuelle + rencontre
                r'\bcherche\b.*\b(trans?|transex|transexuel[les]?|transgenre)\b',
                r'\bcherche\b.*\b(gay|homo|lesbian|bi|bisexuel[les]?)\b',
                r'\b(trans?|transex|gay|homo|bi)\b.*\b(relation|rencontre|contact)\b',
                r'\brelation\b.*\b(trans?|transex|gay|homo|bi)\b',
                # Patterns manquants détectés dans l'analyse
                r'\bcherche\s+contact\s+(féminin|masculin)\b',
                r'\bça\s+te\s+dit\b.*\b(de\s+se\s+)?rapprocher\b',
                r'\brelation\s+sexuelle\b', r'\bpour\s+relation\b'
            ],
            'euphemisms_locations': [
                # Références géographiques avec contexte drague (départements français) - REQUIRE CONTEXT
                r'\b(cherche|dispo|actif|passif|plan|rencontre|contact|relation)\b.*\bdu?\s+(59|62|75|69|13|06|33|31|44|35|67|68|54|57|25|39|21|71|01|38|73|74|83|06|04|05|84|30|34|66|11|09|65|64|40|47|82|81|12|48|43|63|03|42|77|78|91|92|93|94|95)\b',
                r'\bdu?\s+(59|62|75|69|13|06|33|31|44|35|67|68|54|57|25|39|21|71|01|38|73|74|83|06|04|05|84|30|34|66|11|09|65|64|40|47|82|81|12|48|43|63|03|42|77|78|91|92|93|94|95)\b.*\b(dispo|actif|cherche|libre|plan|rencontre|contact)\b',
                r'\b(nord|sud|ouest|est|région\s+parisienne|idf|ile\s+de\s+france)\b.*\b(dispo|actif|cherche|libre)\b',
                r'\b(lille|paris|lyon|marseille|toulouse|nantes|strasbourg|montpellier|bordeaux|nice|rennes|reims|tours|dijon|grenoble|angers|metz|nancy|clermont|orleans|le\s+mans|brest|caen|limoges|amiens|besançon|poitiers|pau|bayonne|perpignan|avignon|toulon|cannes|antibes)\b.*\b(actif|dispo|plan|cherche)\b',
                # Patterns démographiques spécifiques
                r'\b(jeune|mûr|senior|ado|étudiant|travailleur)\b.*\b(du?\s+\d{2}|de\s+la\s+région)\b',
                r'\b(célibataire|divorcé|séparé)\b.*\b(du?\s+\d{2}|région|ville)\b',
                r'\bhabite\b.*\b(près|coin|secteur|région)\b.*\b(dispo|libre|actif)\b',
                # Euphémismes contextuels avec géolocalisation
                r'\bbesoin\s+de\s+(compagnie|contact|chaleur)\b.*\b(région|secteur|coin)\b',
                r'\benvie\s+de\s+(parler|discuter)\b.*\b(privé|cam|tel)\b.*\b(du?\s+\d{2}|région)\b',
                r'\bsolitude\b.*\b(cherche|besoin)\b.*\b(région|secteur|près)\b',
                r'\bcombler\b.*\b(manque|vide|solitude)\b.*\b(région|coin)\b',
                r'\b(discussion|contact)\s+(privé[es]?|intime[s]?|personnel[les]?)\b.*\b(région|secteur)\b',
                # Patterns de ciblage démographique avancés
                r'\bcherche\b.*\b(femme|homme|mec|nana|fille|garçon)\b.*\b(du?\s+\d{2}|région|âge|ans)\b',
                r'\b(18|19|20|21|22|23|24|25)\s*[-à]\s*(25|30|35|40)\s*ans\b.*\b(région|secteur)\b',
                r'\bentre\s+\d+\s+et\s+\d+\s+ans\b.*\b(du?\s+\d{2}|région|cherche)\b'
            ],
            'behavioral_patterns': [
                # Patterns comportementaux typiques
                r'\bmp\s+(moi|si)\b', r'\bpv\s+(moi|si)\b', r'\bpriv[éeaé]\s+(moi|toi|nous)\b',
                r'\bviens\s+en\s+(privé|pv|mp)\b', r'\bon\s+se\s+parle\s+en\s+(privé|pv)\b',
                r'\baj[oa]ute\s+(moi|toi)\b.*\b(snap|insta|telegram|discord)\b',
                r'\bmon\s+(snap|insta|telegram|discord|numero|tel)\b',
                r'\benvoie\s+(moi|ton)\b.*\b(snap|num|tel|photo)\b',
                r'\béchange\s+(photos?|nums?|contacts?)\b',
                r'\bmontres?\s+(toi|ça|voir)\b', r'\bfais\s+voir\b',
                r'\bça\s+te\s+dit\s+de\b.*\b(voir|essayer|tester)\b'
            ],
            'time_urgency': [
                # Urgence temporelle typique de la drague
                r'\bmaintenant\b.*\b(dispo|libre|actif)\b',
                r'\bce\s+soir\b.*\b(dispo|libre|pour)\b',
                r'\btoute\s+suite\b.*\b(dispo|libre)\b',
                r'\brapidement\b.*\b(rencontre|plan|voir)\b',
                r'\bvite\s+fait\b.*\b(voir|rencontre)\b',
                r'\bavant\s+que\b.*\b(parents|conjoint|femme|mari)\b'
            ]
        }
        
        # Compiler les regex pour performance
        self.compiled_patterns = {
            level: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for level, patterns in self.adult_keywords.items()
        }

    def analyze_message(self, message: str, sender: str = None) -> Tuple[bool, float]:
        """
        Analyse un message pour détecter du contenu adulte/sexuel avec analyse comportementale.
        
        Returns:
            Tuple[bool, float]: (is_adult_content, confidence_score)
        """
        try:
            # Vérifier si l'utilisateur est de confiance
            if sender and sender.lower() in self.trusted_users:
                self.logger.debug(f"Utilisateur de confiance {sender} - analyse ignorée")
                return False, 0.0
            
            # Analyse comportementale si sender fourni
            behavior_bonus = 0.0
            if sender:
                behavior_bonus = self._analyze_user_behavior(sender, message)
            
            # Vérifier le cache d'abord
            cached_result = self.cache.get(message)
            if cached_result is not None:
                # Appliquer le bonus comportemental au cache
                is_cached, cached_score = cached_result
                final_score = min(cached_score + behavior_bonus, 10.0)
                final_result = (final_score >= self.sensitivity, final_score)
                if behavior_bonus > 0:
                    self.logger.info(f"Cache + bonus comportemental: {cached_score}+{behavior_bonus}={final_score}")
                return final_result
            
            # Détection rapide par mots-clés AVANT OpenAI
            keyword_score = self._quick_keyword_analysis(message)
            
            # Appliquer bonus comportemental
            adjusted_score = min(keyword_score + behavior_bonus, 10.0)
            
            if adjusted_score >= 9.0:  # Très explicite - pas besoin d'OpenAI
                result = (True, adjusted_score)
                self.cache.put(message, True, keyword_score)  # Cache le score original
                self.logger.info(f"Détection rapide: mots-clés={keyword_score}, comportement={behavior_bonus}, final={adjusted_score}")
                return result
            
            # Si pas détecté par mots-clés, utiliser OpenAI
            # Gestion du rate limiting
            current_time = time.time()
            if current_time - self.last_request_time < self.min_request_interval:
                time.sleep(self.min_request_interval - (current_time - self.last_request_time))
            
            # Utiliser l'API Moderation (gratuite) ou Chat selon config
            if self.use_moderation_api:
                openai_result = self._analyze_with_moderation_api(message)
            else:
                openai_result = self._analyze_with_chat_api(message)
            
            # Combiner score OpenAI + comportemental
            is_openai, openai_score = openai_result
            
            # IMPORTANT: Prendre le MAXIMUM entre keywords et OpenAI pour éviter les faux négatifs
            # Car OpenAI peut parfois sous-estimer les contenus en français
            base_score = max(keyword_score, openai_score)
            final_score = min(base_score + behavior_bonus, 10.0)
            final_result = (final_score >= self.sensitivity, final_score)
            
            if keyword_score > openai_score:
                self.logger.warning(f"Keywords supérieur à OpenAI: {keyword_score} > {openai_score} - utilisation keywords")
            
            # Stocker dans le cache (score original)
            self.cache.put(message, *openai_result)
            
            api_type = "Moderation (GRATUIT)" if self.use_moderation_api else "Chat"
            self.logger.info(f"Analyse OpenAI {api_type}: keywords={keyword_score}, openai={openai_score}, comportement={behavior_bonus}, final={final_score}")
            
            return final_result
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse OpenAI: {e}")
            # Fallback sur analyse keywords + comportementale en cas d'erreur OpenAI
            keyword_score = self._quick_keyword_analysis(message)
            behavior_bonus = 0.0
            if sender:
                behavior_bonus = self._analyze_user_behavior(sender, message)
            final_score = min(keyword_score + behavior_bonus, 10.0)
            is_adult = final_score >= self.sensitivity
            self.logger.info(f"Fallback keywords: {keyword_score}+{behavior_bonus}={final_score} -> {'ADULTE' if is_adult else 'OK'}")
            return is_adult, final_score

    def _quick_keyword_analysis(self, message: str) -> float:
        """Analyse rapide basée sur les mots-clés avec scoring contextuel avancé."""
        message_lower = message.lower()
        
        # Dictionnaire pour tracker les matches par catégorie
        matches = {
            'explicit': [],
            'suggestive': [],
            'drague_rencontre': [],
            'euphemisms_locations': [],
            'behavioral_patterns': [],
            'time_urgency': []
        }
        
        # Détecter tous les patterns
        for category, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(message_lower):
                    matches[category].append(pattern.pattern)
                    self.logger.debug(f"Pattern {category} détecté: {pattern.pattern}")
        
        # Calcul du score contextuel
        contextual_score = self._calculate_contextual_score(matches, message_lower)
        
        # Analyse des euphémismes avancée
        euphemism_score = self._analyze_euphemisms(message_lower)
        
        # Score final = max des deux analyses
        return max(contextual_score, euphemism_score)
    
    def _calculate_contextual_score(self, matches: dict, message: str) -> float:
        """Calcule un score contextuel basé sur les combinaisons de patterns."""
        base_scores = {
            'explicit': 9.5,           # Très explicite -> redirection immédiate
            'suggestive': 6.0,         # Suggestif modéré
            'drague_rencontre': 8.0,   # Drague classique -> forte suspicion
            'euphemisms_locations': 5.5, # Euphémismes géographiques
            'behavioral_patterns': 7.0,   # Comportements typiques drague
            'time_urgency': 6.5          # Urgence temporelle
        }
        
        # Score de base (plus élevé des catégories détectées)
        max_base_score = 0.0
        total_matches = 0
        
        for category, match_list in matches.items():
            if match_list:
                max_base_score = max(max_base_score, base_scores[category])
                total_matches += len(match_list)
        
        if max_base_score == 0:
            return 0.0
        
        # Bonus pour combinaisons suspectes
        bonus = 0.0
        
        # Combinaison localisation + comportement = très suspect
        if matches['euphemisms_locations'] and matches['behavioral_patterns']:
            bonus += 2.0
            self.logger.debug("Bonus: géolocalisation + comportement suspect")
        
        # Combinaison drague + urgence = très suspect
        if matches['drague_rencontre'] and matches['time_urgency']:
            bonus += 1.5
            self.logger.debug("Bonus: drague + urgence temporelle")
        
        # Combinaison comportement + urgence = suspect
        if matches['behavioral_patterns'] and matches['time_urgency']:
            bonus += 1.0
            self.logger.debug("Bonus: comportement + urgence")
        
        # Bonus pour multiplicité de patterns (plus il y en a, plus c'est suspect)
        if total_matches >= 3:
            bonus += 1.0 + (total_matches - 3) * 0.3
            self.logger.debug(f"Bonus multiplicité: {total_matches} patterns détectés")
        
        # Score final avec plafond
        final_score = min(max_base_score + bonus, 10.0)
        
        self.logger.info(f"Score contextuel: base={max_base_score}, bonus={bonus}, final={final_score}")
        return final_score
    
    def _analyze_euphemisms(self, message: str) -> float:
        """Analyse avancée des euphémismes et du contexte implicite."""
        euphemism_patterns = {
            # Euphémismes sexuels courants
            'sexual_euphemisms': [
                r"\bs['']amuser\b.*\b(ensemble|à\s+deux)\b",
                r'\bpasser\s+un\s+bon\s+moment\b.*\b(ensemble|privé)\b',
                r'\bfaire\s+(connaissance|plus\s+ample\s+connaissance)\b.*\b(privé|intimement)\b',
                r'\bse\s+rapprocher\b.*\b(physiquement|intimement)\b',
                r'\bêtre\s+(proche|intime)\b.*\b(avec|ensemble)\b',
                r'\bpartager\s+(quelque\s+chose|intimité|moment)\b',
                r'\bse\s+voir\s+en\s+(privé|tête\s+à\s+tête|intimité)\b'
            ],
            
            # Invitations déguisées
            'disguised_invitations': [
                r'\bviens\s+(chez\s+moi|me\s+voir)\b.*\b(tranquille|seuls?)\b',
                r'\bpasser\s+à\s+la\s+maison\b.*\b(discrètement|tranquille)\b',
                r'\binvite\b.*\b(chez\s+moi|à\s+la\s+maison)\b.*\b(seuls?|tranquille)\b',
                r'\bvenir\s+me\s+tenir\s+compagnie\b',
                r'\bse\s+retrouver\b.*\b(quelque\s+part|tranquille|seuls?)\b'
            ],
            
            # Demandes de contact déguisées
            'contact_fishing': [
                r"\btu\s+(habites?\s+où|es\s+d['']où|viens\s+d['']où)\b",
                r'\bpas\s+loin\s+de\b.*\b(chez\s+moi|ma\s+ville)\b',
                r'\btu\s+connais\b.*\b(ma\s+ville|ma\s+région|le\s+coin)\b',
                r'\bça\s+te\s+dit\s+de\b.*\b(se\s+voir|sortir|boire\s+un\s+verre)\b',
                r'\bon\s+pourrait\s+se\b.*\b(voir|rencontrer|retrouver)\b'
            ],
            
            # Validation seeking (patterns de drague)
            'validation_seeking': [
                r'\btu\s+es\s+(jolie|belle|mignonne|sexy)\b',
                r"\bj['']adore\s+ton\b.*\b(style|look|profil|photo)\b",
                r'\btu\s+me\s+plais\b',
                r"\bj['']aimerais\s+te\s+(connaître|voir)\b",
                r"\btu\s+m['']intéresses?\b",
                r'\bça\s+me\s+ferait\s+plaisir\s+de\b.*\b(te\s+connaître|discuter)\b'
            ],
            
            # Contexte relationnel suspect (patterns plus spécifiques)
            'relationship_context': [
                r'\b(célibataire|seul[es]?|libre)\b.*\b(cherche|envie|besoin)\b.*\b(sexe|plan|cam|rencontre)\b',
                r'\ben\s+manque\s+de\b.*\b(compagnie|affection|contact)\b.*\b(sexe|plan|cam)\b'
            ]
        }
        
        total_score = 0.0
        detected_categories = []
        
        # Analyser chaque catégorie d'euphémismes
        for category, patterns in euphemism_patterns.items():
            category_score = 0.0
            matches_count = 0
            
            for pattern_str in patterns:
                pattern = re.compile(pattern_str, re.IGNORECASE)
                if pattern.search(message):
                    matches_count += 1
                    self.logger.debug(f"Euphémisme {category} détecté: {pattern_str}")
            
            if matches_count > 0:
                detected_categories.append(category)
                # Score par catégorie avec bonus pour multiplicité
                category_score = self._get_euphemism_category_score(category) + (matches_count - 1) * 0.3
                total_score = max(total_score, category_score)
        
        # Bonus pour combinaisons d'euphémismes
        combination_bonus = self._calculate_euphemism_combinations(detected_categories)
        final_score = min(total_score + combination_bonus, 10.0)
        
        if final_score > 0:
            self.logger.info(f"Analyse euphémismes: catégories={detected_categories}, "
                           f"base={total_score:.1f}, combo={combination_bonus:.1f}, final={final_score:.1f}")
        
        return final_score
    
    def _get_euphemism_category_score(self, category: str) -> float:
        """Retourne le score de base pour chaque catégorie d'euphémisme."""
        scores = {
            'sexual_euphemisms': 7.5,      # Euphémismes sexuels -> score élevé
            'disguised_invitations': 8.0,   # Invitations déguisées -> très suspect
            'contact_fishing': 6.5,         # Pêche d'informations -> suspect
            'validation_seeking': 7.0,      # Recherche validation -> drague
            'relationship_context': 5.5     # Contexte relationnel -> modéré
        }
        return scores.get(category, 0.0)
    
    def _calculate_euphemism_combinations(self, categories: list) -> float:
        """Calcule des bonus pour les combinaisons suspectes d'euphémismes."""
        if len(categories) < 2:
            return 0.0
        
        bonus = 0.0
        
        # Combinaisons très suspectes
        high_risk_combinations = [
            ('sexual_euphemisms', 'disguised_invitations'),  # Sexuel + invitation = très suspect
            ('contact_fishing', 'disguised_invitations'),    # Contact + invitation = très suspect
            ('validation_seeking', 'sexual_euphemisms')      # Validation + sexuel = drague claire
        ]
        
        for cat1, cat2 in high_risk_combinations:
            if cat1 in categories and cat2 in categories:
                bonus += 2.0
                self.logger.debug(f"Combinaison euphémisme très suspecte: {cat1} + {cat2}")
        
        # Bonus général pour multiple catégories
        if len(categories) >= 3:
            bonus += 1.5
            self.logger.debug(f"Bonus multiplicité euphémismes: {len(categories)} catégories")
        
        return min(bonus, 3.0)  # Plafond du bonus
    
    def analyze_message_comprehensive(self, message: str, sender: str = None) -> dict:
        """
        Analyse complète d'un message avec tous les détails de scoring.
        Utile pour debugging et statistiques détaillées.
        """
        if sender and sender.lower() in self.trusted_users:
            return {
                'is_adult_content': False,
                'final_score': 0.0,
                'trusted_user': True,
                'analysis_details': {}
            }
        
        analysis_details = {}
        
        # 1. Analyse des patterns contextuels
        message_lower = message.lower()
        matches = {
            'explicit': [], 'suggestive': [], 'drague_rencontre': [],
            'euphemisms_locations': [], 'behavioral_patterns': [], 'time_urgency': []
        }
        
        for category, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(message_lower):
                    matches[category].append(pattern.pattern)
        
        contextual_score = self._calculate_contextual_score(matches, message_lower)
        analysis_details['contextual'] = {
            'score': contextual_score,
            'matches': {k: v for k, v in matches.items() if v}
        }
        
        # 2. Analyse des euphémismes
        euphemism_score = self._analyze_euphemisms(message_lower)
        analysis_details['euphemisms'] = {'score': euphemism_score}
        
        # 3. Analyse comportementale
        behavior_bonus = 0.0
        if sender:
            behavior_bonus = self._analyze_user_behavior(sender, message)
            analysis_details['behavioral'] = {
                'bonus': behavior_bonus,
                'user_stats': self.get_user_behavior_stats(sender)
            }
        
        # 4. Score final combiné
        base_score = max(contextual_score, euphemism_score)
        final_score = min(base_score + behavior_bonus, 10.0)
        
        # 5. Recommandation d'action
        action_recommendation = self._get_action_recommendation(final_score, analysis_details)
        
        return {
            'is_adult_content': final_score >= self.sensitivity,
            'final_score': final_score,
            'base_score': base_score,
            'behavioral_bonus': behavior_bonus,
            'sensitivity_threshold': self.sensitivity,
            'trusted_user': False,
            'analysis_details': analysis_details,
            'action_recommendation': action_recommendation
        }
    
    def _get_action_recommendation(self, score: float, details: dict) -> dict:
        """Recommande une action basée sur le score et les détails d'analyse."""
        if score >= 9.0:
            return {
                'action': 'immediate_redirect',
                'reason': 'Contenu explicite détecté',
                'confidence': 'très_élevée'
            }
        elif score >= 7.0:
            return {
                'action': 'redirect_with_warning', 
                'reason': 'Contenu fortement suspect de drague',
                'confidence': 'élevée'
            }
        elif score >= 5.0:
            behavioral_bonus = details.get('behavioral', {}).get('bonus', 0.0)
            if behavioral_bonus >= 1.0:
                return {
                    'action': 'warn_and_monitor',
                    'reason': 'Pattern comportemental suspect détecté',
                    'confidence': 'modérée'
                }
            else:
                return {
                    'action': 'monitor_only',
                    'reason': 'Contenu modérément suspect',
                    'confidence': 'modérée'
                }
        else:
            return {
                'action': 'no_action',
                'reason': 'Contenu acceptable',
                'confidence': 'faible'
            }
    
    def get_cache_stats(self) -> dict:
        """Retourne les statistiques du cache."""
        return self.cache.get_stats()
    
    def add_trusted_user(self, username: str):
        """Ajoute un utilisateur à la whitelist."""
        self.trusted_users.add(username.lower())
        self.logger.info(f"Utilisateur {username} ajouté à la whitelist")
    
    def remove_trusted_user(self, username: str):
        """Retire un utilisateur de la whitelist."""
        self.trusted_users.discard(username.lower())
        self.logger.info(f"Utilisateur {username} retiré de la whitelist")
    
    def _analyze_user_behavior(self, username: str, message: str) -> float:
        """Analyse le comportement d'un utilisateur pour détecter des patterns suspects."""
        current_time = time.time()
        username_lower = username.lower()
        
        # Initialiser ou nettoyer les données utilisateur
        if username_lower not in self.user_behavior:
            self.user_behavior[username_lower] = {
                'messages': [],
                'scores': [],
                'last_activity': current_time,
                'suspicious_patterns': 0,
                'total_messages': 0
            }
        
        user_data = self.user_behavior[username_lower]
        
        # Nettoyer les anciens messages (plus vieux que behavior_window)
        cutoff_time = current_time - self.behavior_window
        user_data['messages'] = [(msg, timestamp, score) for msg, timestamp, score in user_data['messages'] 
                                if timestamp > cutoff_time]
        user_data['scores'] = [score for _, timestamp, score in user_data['messages']]
        
        # Analyser le message actuel
        message_score = self._quick_keyword_analysis(message)
        
        # Ajouter le message à l'historique
        user_data['messages'].append((message, current_time, message_score))
        user_data['scores'].append(message_score)
        user_data['last_activity'] = current_time
        user_data['total_messages'] += 1
        
        # Calculer le bonus comportemental
        return self._calculate_behavior_bonus(user_data, message, message_score)
    
    def _calculate_behavior_bonus(self, user_data: dict, current_message: str, current_score: float) -> float:
        """Calcule le bonus comportemental basé sur l'historique de l'utilisateur."""
        messages = user_data['messages']
        scores = user_data['scores']
        
        if len(messages) < 2:
            return 0.0  # Pas assez d'historique
        
        bonus = 0.0
        recent_messages = messages[-5:]  # 5 derniers messages
        
        # Pattern 1: Escalade progressive (messages de plus en plus suspects)
        if len(recent_messages) >= 3:
            recent_scores = [score for _, _, score in recent_messages]
            if self._detect_escalation(recent_scores):
                bonus += 1.5
                self.logger.debug("Bonus: escalade progressive détectée")
        
        # Pattern 2: Répétition de patterns suspects
        repetition_bonus = self._detect_repetitive_patterns(recent_messages)
        bonus += repetition_bonus
        
        # Pattern 3: Fréquence élevée de messages suspects
        recent_suspicious = sum(1 for _, _, score in recent_messages if score > 5.0)
        if recent_suspicious >= 3:
            bonus += 1.0
            self.logger.debug(f"Bonus: fréquence élevée ({recent_suspicious}/5 messages suspects)")
        
        # Pattern 4: Persistance après avertissement (simulation)
        avg_score = sum(scores) / len(scores) if scores else 0
        if avg_score > 4.0 and len(messages) >= 5:
            bonus += 0.8
            self.logger.debug(f"Bonus: persistance comportementale (moyenne: {avg_score:.1f})")
        
        # Pattern 5: Messages très courts et répétitifs (spam drague)
        if self._detect_spam_pattern(recent_messages):
            bonus += 2.0
            self.logger.debug("Bonus: pattern de spam détecté")
        
        return min(bonus, 3.0)  # Plafond du bonus comportemental
    
    def _detect_escalation(self, scores: list) -> bool:
        """Détecte une escalade progressive dans les scores."""
        if len(scores) < 3:
            return False
        
        # Vérifier si les scores augmentent globalement
        increases = 0
        for i in range(1, len(scores)):
            if scores[i] > scores[i-1]:
                increases += 1
        
        return increases >= len(scores) // 2
    
    def _detect_repetitive_patterns(self, messages: list) -> float:
        """Détecte la répétition de patterns suspects."""
        if len(messages) < 3:
            return 0.0
        
        # Chercher des phrases ou mots répétés
        message_texts = [msg.lower() for msg, _, _ in messages]
        
        # Détecter les mots-clés répétés
        all_words = ' '.join(message_texts).split()
        word_counts = {}
        for word in all_words:
            if len(word) > 3:  # Ignorer les mots trop courts
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Mots suspects répétés
        suspicious_words = ['dispo', 'actif', 'passif', 'privé', 'snap', 'plan', 'cherche', 'rencontre']
        repetition_score = 0.0
        
        for word, count in word_counts.items():
            if count >= 3 and (word in suspicious_words or any(sw in word for sw in suspicious_words)):
                repetition_score += 0.5
                self.logger.debug(f"Mot suspect répété: {word} ({count}x)")
        
        return min(repetition_score, 2.0)
    
    def _detect_spam_pattern(self, messages: list) -> bool:
        """Détecte les patterns de spam (messages courts et répétitifs)."""
        if len(messages) < 4:
            return False
        
        # Compter les messages très courts
        short_messages = sum(1 for msg, _, _ in messages if len(msg.strip()) < 20)
        
        # Compter les messages avec patterns drague
        drague_messages = sum(1 for _, _, score in messages if score > 6.0)
        
        # Pattern de spam si beaucoup de messages courts ET suspects
        return short_messages >= 3 and drague_messages >= 2
    
    def get_user_behavior_stats(self, username: str) -> dict:
        """Retourne les statistiques comportementales d'un utilisateur."""
        username_lower = username.lower()
        if username_lower not in self.user_behavior:
            return {}
        
        user_data = self.user_behavior[username_lower]
        current_time = time.time()
        
        # Nettoyer les anciens messages pour les stats
        cutoff_time = current_time - self.behavior_window
        recent_messages = [(msg, timestamp, score) for msg, timestamp, score in user_data['messages'] 
                          if timestamp > cutoff_time]
        
        recent_scores = [score for _, _, score in recent_messages]
        
        return {
            'total_messages': user_data['total_messages'],
            'recent_messages_count': len(recent_messages),
            'average_recent_score': sum(recent_scores) / len(recent_scores) if recent_scores else 0.0,
            'max_recent_score': max(recent_scores) if recent_scores else 0.0,
            'suspicious_messages': sum(1 for score in recent_scores if score > 5.0),
            'last_activity': user_data['last_activity']
        }

    def _analyze_with_moderation_api(self, message: str) -> Tuple[bool, float]:
        """Analyse avec l'API Moderation d'OpenAI (gratuite)."""
        moderation_response = self.client.moderations.create(
            input=message,
            model=self.moderation_model  # omni-moderation-latest (nouveau modèle OpenAI)
        )
        self.last_request_time = time.time()
        return self._parse_moderation_response(moderation_response, message)

    def _analyze_with_chat_api(self, message: str) -> Tuple[bool, float]:
        """Analyse avec l'API Chat d'OpenAI (payante, pour fallback)."""
        # Garder l'ancienne méthode comme fallback
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "Tu es un modérateur automatique. Réponds par un score 0-10 pour le contenu adulte/sexuel."
                },
                {"role": "user", "content": f"Message: {message}"}
            ],
            max_tokens=50,
            temperature=0.1
        )
        
        self.last_request_time = time.time()
        result_text = response.choices[0].message.content.strip()
        score, explanation = self._parse_chat_response(result_text)
        is_adult_content = score >= self.sensitivity
        return is_adult_content, score

    def _parse_moderation_response(self, moderation_response, message: str) -> Tuple[bool, float]:
        """Parse la réponse de l'API Moderation d'OpenAI."""
        try:
            result = moderation_response.results[0]
            
            # Récupérer les scores de chaque catégorie
            categories = result.categories
            category_scores = result.category_scores
            
            # Se concentrer sur les catégories liées au contenu adulte/sexuel
            adult_categories = {
                'sexual': category_scores.sexual if hasattr(category_scores, 'sexual') else 0,
                'sexual/minors': category_scores.sexual_minors if hasattr(category_scores, 'sexual_minors') else 0,
            }
            
            # Prendre le score maximum parmi les catégories adultes
            max_adult_score = max(adult_categories.values())
            
            # Convertir le score (0.0-1.0) en score sur 10
            score_out_of_10 = max_adult_score * 10
            
            # Déterminer si c'est flaggé
            is_flagged = categories.sexual or (hasattr(categories, 'sexual_minors') and categories.sexual_minors)
            
            # Si pas flaggé par OpenAI mais score élevé, ajuster
            if not is_flagged and score_out_of_10 < self.sensitivity:
                score_out_of_10 = min(score_out_of_10, self.sensitivity - 0.1)
            
            is_adult_content = score_out_of_10 >= self.sensitivity
            
            self.logger.debug(f"OpenAI Moderation - Sexual: {adult_categories['sexual']:.3f}, "
                            f"Flagged: {is_flagged}, Score final: {score_out_of_10:.1f}/10")
            
            return is_adult_content, score_out_of_10
            
        except Exception as e:
            self.logger.error(f"Erreur parsing réponse Moderation: {e}")
            # Fallback sur keywords si erreur
            keyword_score = self._quick_keyword_analysis(message)
            return keyword_score >= self.sensitivity, keyword_score

    def _parse_chat_response(self, response: str) -> Tuple[float, str]:
        """Parse la réponse de l'API Chat (méthode originale)."""
        try:
            parts = response.split(' ', 1)
            if len(parts) >= 2:
                score_part = parts[0].split('/')[0]
                explanation = parts[1] if len(parts) > 1 else "Analyse automatique"
                score = float(score_part)
                return min(max(score, 0), 10), explanation
        except (ValueError, IndexError) as e:
            self.logger.warning(f"Impossible de parser la réponse Chat: {response}, erreur: {e}")
        
        # Fallback: analyser si certains mots-clés sont présents
        adult_keywords = [
            'sexe', 'cul', 'baiser', 'bite', 'chatte', 'seins', 'nichons',
            'orgasme', 'jouir', 'porn', 'masturbation', 'érection'
        ]
        
        message_lower = response.lower()
        if any(keyword in message_lower for keyword in adult_keywords):
            return 8.0, "Mots-clés adultes détectés"
        
        return 0.0, "Analyse par défaut"

    def _create_analysis_prompt(self, message: str) -> str:
        """Créé le prompt d'analyse optimisé pour la détection de contenu adulte en français."""
        return f"""
Analyse ce message IRC en français pour détecter du contenu adulte/sexuel:

"{message}"

Critères de détection:
- Références sexuelles explicites ou implicites
- Langage à connotation sexuelle
- Descriptions d'actes intimes
- Références à l'anatomie dans un contexte sexuel
- Invitations ou suggestions à caractère sexuel
- Contenu érotique ou pornographique

Ignore:
- Les discussions médicales légitimes
- Les références culturelles innocentes
- L'humour léger sans connotation explicite
- Les expressions courantes non sexuelles

Réponds UNIQUEMENT par: [SCORE]/10 [EXPLICATION]
Exemple: "8/10 Contenu à connotation sexuelle explicite"
"""

    def _parse_response(self, response: str) -> Tuple[float, str]:
        """Parse la réponse OpenAI pour extraire le score et l'explication."""
        try:
            parts = response.split(' ', 1)
            if len(parts) >= 2:
                score_part = parts[0].split('/')[0]
                explanation = parts[1] if len(parts) > 1 else "Analyse automatique"
                score = float(score_part)
                return min(max(score, 0), 10), explanation
        except (ValueError, IndexError) as e:
            self.logger.warning(f"Impossible de parser la réponse OpenAI: {response}, erreur: {e}")
        
        # Fallback: analyser si certains mots-clés sont présents
        adult_keywords = [
            'sexe', 'cul', 'baiser', 'bite', 'chatte', 'seins', 'nichons',
            'orgasme', 'jouir', 'porn', 'masturbation', 'érection'
        ]
        
        message_lower = response.lower()
        if any(keyword in message_lower for keyword in adult_keywords):
            return 8.0, "Mots-clés adultes détectés"
        
        return 0.0, "Analyse par défaut"