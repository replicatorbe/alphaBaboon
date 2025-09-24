import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from content_analyzer import ContentAnalyzer
from message_rotator import MessageRotator
from phone_moderator import PhoneModerator
from drug_detector import DrugDetector
from privilege_checker import PrivilegeChecker
from baboon_vocabulary import baboon_vocab


@dataclass
class ModerationResult:
    """Résultat d'analyse de modération avec détails des violations."""
    is_violation: bool
    violation_types: List[str]
    confidence_score: float
    severity_level: int  # 1=warning, 2=kick, 3=ban
    reason: str


@dataclass 
class UserViolationHistory:
    """Historique des violations d'un utilisateur."""
    warnings: List[datetime]
    kicks: List[datetime]
    violations_by_type: Dict[str, List[datetime]]
    
    def __len__(self):
        """Retourne le nombre total de violations."""
        return len(self.warnings) + len(self.kicks)


class AdvancedModerationHandler:
    """
    Gestionnaire de modération avancé utilisant tous les critères OpenAI.
    Système 2-strikes : warning puis kick/ban.
    """
    
    def __init__(self, config, timing_config=None):
        self.config = config
        self.timing_config = timing_config
        self.logger = logging.getLogger(__name__)
        self.content_analyzer = ContentAnalyzer(config)
        self.message_rotator = MessageRotator(config)
        self.phone_moderator = PhoneModerator(config)
        self.drug_detector = DrugDetector(config)
        self.privilege_checker = PrivilegeChecker(config)
        
        # Historique des violations par utilisateur
        self.user_violations: Dict[str, UserViolationHistory] = {}
        
        # Configuration avec timings configurables
        if timing_config:
            mod_settings = timing_config.get_moderation_settings()
            self.reset_hours = mod_settings['reset_hours']
            self.cooldown_minutes = mod_settings['cooldown_minutes']
            self.move_delay = mod_settings['move_delay_seconds']
            self.welcome_delay = mod_settings['welcome_delay_seconds']
        else:
            # Fallback vers config traditionnelle
            self.reset_hours = config['moderation']['reset_hours']
            self.cooldown_minutes = config['moderation']['cooldown_minutes']
            self.move_delay = config['moderation'].get('move_delay_seconds', 3)
            self.welcome_delay = config['moderation'].get('welcome_delay_seconds', 5)
        
        # Seuils de sensibilité par catégorie (score sur 10)
        self.category_thresholds = {
            'sexual': 4.0,
            'sexual/minors': 2.5,  # Seuil ajusté pour éviter les faux positifs
            'harassment': 4.0,
            'harassment/threatening': 2.0,
            'hate': 4.5,
            'hate/threatening': 2.0,
            'violence': 6.0,
            'violence/graphic': 4.0,
            'illicit': 4.5,
            'illicit/violent': 3.0,
            'self-harm': 2.0,
            'self-harm/intent': 1.5,
            'self-harm/instructions': 1.0
        }
        
        # Mapping des sévérités par catégorie
        self.category_severity = {
            'sexual': 1,  # Warning puis kick vers #adultes
            'sexual/minors': 3,  # Ban immédiat
            'harassment': 2,  # Warning puis kick
            'harassment/threatening': 3,  # Ban immédiat
            'hate': 2,
            'hate/threatening': 3,
            'violence': 2,
            'violence/graphic': 2,
            'illicit': 2,
            'illicit/violent': 3,
            'self-harm': 1,  # Warning + aide
            'self-harm/intent': 2,
            'self-harm/instructions': 3
        }
        
        # Messages par type de violation (avec vocabulaire Baboon)
        self.violation_messages = {
            'sexual': "🐒 {user}, ce genre de bavardage c'est plutôt sur la tribu #adultes ! 😊",
            'harassment': "⚠️ {user}, restons courtois entre babouins !",
            'hate': "❌ {user}, pas de gros mots de singe ici s'il te plaît.",
            'violence': "🚫 {user}, évitez les comportements violents dans notre tribu.",
            'illicit': "🚔 {user}, les références aux substances de la jungle ne sont pas autorisées ici.",
            'self-harm': "💜 {user}, si tu as besoin d'aide, n'hésite pas à contacter un chef de la tribu."
        }
        
        # Dernière action par utilisateur pour éviter le spam
        self.last_action: Dict[str, datetime] = {}

    def analyze_message(self, sender: str, message: str, channel: str, irc_client):
        """Analyse avancée d'un message avec tous les critères OpenAI."""
        try:
            # 0. Vérifier d'abord si l'utilisateur est exempté (op/halfop/voice)
            if self.privilege_checker.is_exempt_from_moderation(irc_client, channel, sender):
                self.privilege_checker.log_privilege_check(irc_client, channel, sender, "EXEMPTION_MODERATION")
                return  # Pas de modération pour les privilégiés
            
            # 1. Vérifier les numéros de téléphone (priorité)
            has_phone, phone_action = self.phone_moderator.check_phone_numbers(message, sender, channel)
            if has_phone and phone_action and phone_action['action'] != 'none':
                self._handle_phone_violation(sender, channel, irc_client, phone_action)
                return
            
            # 2. Vérifier le cooldown (mais PAS pour les violations légères qui nécessitent 2-strikes)
            if not self._can_moderate_user(sender):
                # Permettre la 2ème détection pour les violations légères (sexual, self-harm)
                # en vérifiant si l'utilisateur a déjà un warning récent
                if sender in self.user_violations:
                    user_history = self.user_violations[sender]
                    if len(user_history.warnings) > 0 and len(user_history.warnings) < 2:
                        # Laisser passer pour la 2ème chance
                        pass
                    else:
                        return
                else:
                    return
            
            # 3. Analyse complète avec OpenAI
            moderation_result = self._analyze_with_all_criteria(message, sender, channel)
            
            if moderation_result.is_violation:
                # Log détaillé de la violation avec contexte
                violation_detail = {
                    'user': sender,
                    'channel': channel,
                    'violation_types': moderation_result.violation_types,
                    'confidence_score': round(moderation_result.confidence_score, 2),
                    'severity_level': moderation_result.severity_level,
                    'reason': moderation_result.reason,
                    'message_preview': message[:50] + '...' if len(message) > 50 else message
                }
                self.logger.warning(f"🚨 VIOLATION: {violation_detail}")
                self._handle_moderation_violation(sender, channel, irc_client, moderation_result)
                
        except Exception as e:
            # Log détaillé des erreurs avec stack trace
            import traceback
            error_detail = {
                'user': sender,
                'channel': channel,
                'error': str(e),
                'message_length': len(message),
                'message_preview': message[:100] + '...' if len(message) > 100 else message,
                'stack_trace': traceback.format_exc()
            }
            self.logger.error(f"❌ ERREUR ANALYSE: {error_detail}")

    def _analyze_with_all_criteria(self, message: str, sender: str, channel: str = "#francophonie") -> ModerationResult:
        """Analyse un message avec tous les critères OpenAI disponibles."""
        try:
            # Exceptions pour éviter les faux positifs
            message_lower = message.lower()
            if 'kick moi' in message_lower or 'kicke moi' in message_lower or 'kick-moi' in message_lower:
                return ModerationResult(
                    is_violation=False,
                    violation_types=[],
                    confidence_score=0.0,
                    severity_level=0,
                    reason="Exception: demande de kick autorisée"
                )
            # Exceptions pour questions géographiques (faux positifs fréquents)
            geographic_patterns = [
                'tu es d\'où', 'tu es d ou', 'tu viens d\'où', 'tu viens d ou',
                'tu habites où', 'tu habites ou', 'quelle région', 'quel coin',
                'tu es de quel', 'vous êtes d\'où', 'vous êtes d ou',
                'de quelle ville', 'tu vis où', 'tu vis ou'
            ]
            if any(pattern in message_lower for pattern in geographic_patterns):
                return ModerationResult(
                    is_violation=False,
                    violation_types=[],
                    confidence_score=0.0,
                    severity_level=0,
                    reason="Exception: question géographique autorisée"
                )
            
            # Exceptions pour mots/expressions innocents causant des faux positifs
            innocent_patterns = [
                'dick', 'zizi', 'pipi', 'caca',  # Mots enfantins/prénoms
                'abusé parfois', 'c\'est abusé', 'trop abusé',  # Expressions courantes
                'il a raison', 'elle a raison', 'tu as raison'  # Validations
            ]
            for pattern in innocent_patterns:
                if pattern in message_lower and len(message.split()) <= 8:  # Messages courts seulement
                    return ModerationResult(
                        is_violation=False,
                        violation_types=[],
                        confidence_score=0.0,
                        severity_level=0,
                        reason=f"Exception: expression innocente '{pattern}' autorisée"
                    )
            # Exception pour références d'âge innocentes
            import re
            age_pattern = r'\b(à|a)\s+\d{1,2}\s+ans?\b'
            if re.search(age_pattern, message_lower) and len(message.split()) <= 6:
                return ModerationResult(
                    is_violation=False,
                    violation_types=[],
                    confidence_score=0.0,
                    severity_level=0,
                    reason="Exception: référence d'âge simple autorisée"
                )
            # Exception pour photos d'animaux
            if 'tete de' in message_lower and any(animal in message_lower for animal in ['chat', 'chien', 'animal', 'chats', 'chiens']):
                return ModerationResult(
                    is_violation=False,
                    violation_types=[],
                    confidence_score=0.0,
                    severity_level=0,
                    reason="Exception: photo d'animal autorisée"
                )
            # Utiliser l'API Moderation d'OpenAI
            moderation_response = self.content_analyzer.client.moderations.create(
                input=message,
                model=self.content_analyzer.moderation_model
            )
            
            result = moderation_response.results[0]
            categories = result.categories
            category_scores = result.category_scores
            
            violations = []
            max_score = 0.0
            max_severity = 0
            
            # Vérifier chaque catégorie
            category_mapping = {
                'sexual': 'sexual',
                'sexual/minors': 'sexual_minors', 
                'harassment': 'harassment',
                'harassment/threatening': 'harassment_threatening',
                'hate': 'hate',
                'hate/threatening': 'hate_threatening',
                'violence': 'violence',
                'violence/graphic': 'violence_graphic',
                'illicit': 'illicit',
                'illicit/violent': 'illicit_violent',
                'self-harm': 'self_harm',
                'self-harm/intent': 'self_harm_intent',
                'self-harm/instructions': 'self_harm_instructions'
            }
            
            for category_name, attr_name in category_mapping.items():
                if hasattr(category_scores, attr_name) and hasattr(categories, attr_name):
                    score = getattr(category_scores, attr_name) * 10  # Convertir en score sur 10
                    is_flagged = getattr(categories, attr_name)
                    threshold = self.category_thresholds.get(category_name, 5.0)
                    
                    # Sur #adultes, ignorer les violations sexuelles, violence et harassment (contexte adulte)
                    if channel == "#adultes" and category_name in ['sexual', 'sexual/minors', 'violence', 'violence/graphic', 'harassment', 'harassment/threatening']:
                        continue
                    
                    # Ignorer harassment et violence partout (trop de faux positifs)
                    if category_name in ['harassment', 'harassment/threatening', 'violence', 'violence/graphic']:
                        continue
                    
                    if score >= threshold or is_flagged:
                        violations.append(category_name)
                        max_score = max(max_score, score)
                        max_severity = max(max_severity, self.category_severity.get(category_name, 1))
            
            # Si violations détectées par OpenAI, vérifier aussi nos patterns français pour sexual
            # MAIS seulement sur #francophonie (pas sur #adultes où c'est autorisé)
            if 'sexual' not in violations and channel != "#adultes":
                keyword_score = self.content_analyzer._quick_keyword_analysis(message)
                if keyword_score >= self.category_thresholds['sexual']:
                    violations.append('sexual')
                    max_score = max(max_score, keyword_score)
                    max_severity = max(max_severity, 1)
            
            # Vérifier avec notre détecteur de drogues français pour compléter OpenAI
            is_drug_related, drug_score, drug_elements = self.drug_detector.analyze_message(message)
            if is_drug_related:
                # Si pas déjà détecté par OpenAI comme illicit, l'ajouter
                if 'illicit' not in violations:
                    violations.append('illicit')
                    max_score = max(max_score, drug_score)
                    max_severity = max(max_severity, self.category_severity.get('illicit', 2))
                    
            # Construire le résultat
            is_violation = len(violations) > 0
            reason = f"Détection: {', '.join(violations)}" if violations else ""
            
            # Ajouter les détails de détection drogue si applicable
            if is_drug_related and 'illicit' in violations:
                drug_summary = self.drug_detector.get_detection_summary(drug_elements)
                reason += f" (Patterns FR: {drug_summary})"
            
            # Log détaillé de l'analyse
            analysis_detail = {
                'user': sender,
                'channel': channel,
                'violations': violations,
                'confidence_score': round(max_score, 2),
                'severity_level': max_severity,
                'openai_categories_checked': len(category_mapping),
                'drug_detected': is_drug_related if 'is_drug_related' in locals() else False
            }
            self.logger.info(f"📊 ANALYSE: {analysis_detail}")
            
            return ModerationResult(
                is_violation=is_violation,
                violation_types=violations,
                confidence_score=max_score,
                severity_level=max_severity,
                reason=reason
            )
            
        except Exception as e:
            self.logger.error(f"Erreur analyse OpenAI complète: {e}")
            # Fallback vers l'ancien système
            is_adult, score = self.content_analyzer.analyze_message(message, sender)
            violations = ['sexual'] if is_adult else []
            return ModerationResult(
                is_violation=is_adult,
                violation_types=violations,
                confidence_score=score,
                severity_level=1 if is_adult else 0,
                reason="Détection sexuelle (fallback)"
            )

    def _handle_moderation_violation(self, user: str, channel: str, irc_client, result: ModerationResult):
        """Gère une violation selon le système 2-strikes et la sévérité."""
        current_time = datetime.now()
        
        # Initialiser l'historique de l'utilisateur si nécessaire
        if user not in self.user_violations:
            self.user_violations[user] = UserViolationHistory(
                warnings=[], kicks=[], violations_by_type={}
            )
        
        user_history = self.user_violations[user]
        
        # Nettoyer l'historique ancien
        self._clean_old_violations(user, current_time)
        
        # Déterminer l'action selon la sévérité et l'historique
        if result.severity_level >= 3:
            # Violations graves = ban immédiat
            self._apply_ban(user, channel, irc_client, result)
            
        elif result.severity_level >= 2:
            # Violations moyennes = warning puis kick
            if len(user_history.warnings) == 0:
                self._apply_warning(user, channel, irc_client, result)
            else:
                self._apply_kick(user, channel, irc_client, result)
                
        else:
            # Violations légères = warning puis redirection
            # EXCEPTION: Contenu sexuel sur #francophonie = déplacement immédiat
            if 'sexual' in result.violation_types and channel == "#francophonie":
                self._redirect_to_adultes(user, channel, irc_client)
            elif len(user_history.warnings) == 0:
                self._apply_warning(user, channel, irc_client, result)
            else:
                if 'sexual' in result.violation_types and channel != "#adultes":
                    self._redirect_to_adultes(user, channel, irc_client)
                else:
                    self._apply_kick(user, channel, irc_client, result)
        
        # Enregistrer la violation
        for violation_type in result.violation_types:
            if violation_type not in user_history.violations_by_type:
                user_history.violations_by_type[violation_type] = []
            user_history.violations_by_type[violation_type].append(current_time)
        
        self.last_action[user] = current_time

    def _apply_warning(self, user: str, channel: str, irc_client, result: ModerationResult):
        """Applique un avertissement."""
        self.user_violations[user].warnings.append(datetime.now())
        
        # Choisir le message selon le type de violation
        primary_violation = result.violation_types[0] if result.violation_types else 'sexual'
        message_template = self.violation_messages.get(primary_violation, self.violation_messages['sexual'])
        warning_message = message_template.format(user=user)
        
        irc_client.privmsg(channel, warning_message)
        # Log détaillé de l'action
        action_detail = {
            'action': 'WARNING',
            'user': user,
            'channel': channel,
            'violation_types': result.violation_types,
            'total_warnings': len(self.user_violations[user].warnings),
            'message_sent': warning_message[:100] + '...' if len(warning_message) > 100 else warning_message
        }
        self.logger.warning(f"⚠️ ACTION: {action_detail}")

    def _apply_kick(self, user: str, channel: str, irc_client, result: ModerationResult):
        """Applique un kick."""
        self.user_violations[user].kicks.append(datetime.now())
        
        kick_reason = f"2ème bêtise: {', '.join(result.violation_types)}"
        baboon_message = baboon_vocab.get_action_message('kick', user, kick_reason)
        irc_client.privmsg(channel, baboon_message)
        
        import threading
        def delayed_kick():
            irc_client.connection.kick(channel, user, kick_reason)
            # Log détaillé du kick
            action_detail = {
                'action': 'KICK',
                'user': user,
                'channel': channel,
                'violation_types': result.violation_types,
                'total_kicks': len(self.user_violations[user].kicks),
                'reason': kick_reason
            }
            self.logger.warning(f"👢 ACTION: {action_detail}")
        
        threading.Timer(2.0, delayed_kick).start()

    def _apply_ban(self, user: str, channel: str, irc_client, result: ModerationResult):
        """Applique un ban pour violations graves."""
        ban_reason = f"Bêtise grave: {', '.join(result.violation_types)}"
        baboon_message = baboon_vocab.get_action_message('ban', user, ban_reason)
        irc_client.privmsg(channel, baboon_message)
        
        import threading
        def delayed_ban():
            irc_client.connection.send_raw(f"MODE {channel} +b {user}!*@*")
            irc_client.connection.kick(channel, user, ban_reason)
            # Log détaillé du ban
            action_detail = {
                'action': 'BAN',
                'user': user,
                'channel': channel,
                'violation_types': result.violation_types,
                'severity_level': result.severity_level,
                'reason': ban_reason
            }
            self.logger.error(f"🔨 ACTION: {action_detail}")
        
        threading.Timer(2.0, delayed_ban).start()

    def _redirect_to_adultes(self, user: str, channel: str, irc_client):
        """Redirige vers #adultes (violations sexuelles légères)."""
        import threading
        
        redirect_msg = self.message_rotator.get_redirect_message(user)
        irc_client.privmsg(channel, redirect_msg)
        
        def move_user():
            success = irc_client.move_user_to_adultes(user, f"Discussion plus appropriée sur {irc_client.redirect_channel} 😊")
            if success:
                def send_welcome():
                    welcome_msg = self.message_rotator.get_welcome_message(user)
                    irc_client.send_message(irc_client.redirect_channel, welcome_msg)
                threading.Timer(self.welcome_delay, send_welcome).start()
        
        threading.Timer(self.move_delay, move_user).start()

    def _handle_phone_violation(self, user: str, channel: str, irc_client, phone_action: dict):
        """Gère les violations de numéro de téléphone (code existant)."""
        # Réutiliser le code existant de ModerationHandler
        action_type = phone_action['action']
        message = phone_action['message']
        
        if action_type == 'warn':
            irc_client.privmsg(channel, message)
            self.logger.info(f"Avertissement numéro envoyé à {user} sur {channel}")
            
        elif action_type == 'ban':
            irc_client.privmsg(channel, message)
            
            def apply_ban():
                try:
                    ban_command = f"samode {channel} +b {user}!*@*"
                    irc_client.connection.send_raw(ban_command)
                    self.logger.warning(f"Ban appliqué: {user} sur {channel} pour numéros de téléphone")
                except Exception as e:
                    self.logger.error(f"Erreur lors du ban de {user}: {e}")
            
            import threading
            threading.Timer(3.0, apply_ban).start()

    def _can_moderate_user(self, user: str) -> bool:
        """Vérifie le cooldown."""
        if user not in self.last_action:
            return True
        
        last_action_time = self.last_action[user]
        cooldown = timedelta(minutes=self.cooldown_minutes)
        return datetime.now() - last_action_time > cooldown

    def _clean_old_violations(self, user: str, current_time: datetime):
        """Nettoie les violations anciennes."""
        if user not in self.user_violations:
            return
        
        reset_threshold = current_time - timedelta(hours=self.reset_hours)
        user_history = self.user_violations[user]
        
        # Nettoyer warnings et kicks
        user_history.warnings = [w for w in user_history.warnings if w > reset_threshold]
        user_history.kicks = [k for k in user_history.kicks if k > reset_threshold]
        
        # Nettoyer violations par type
        for violation_type in list(user_history.violations_by_type.keys()):
            user_history.violations_by_type[violation_type] = [
                v for v in user_history.violations_by_type[violation_type] 
                if v > reset_threshold
            ]
            if not user_history.violations_by_type[violation_type]:
                del user_history.violations_by_type[violation_type]

    def get_user_status(self, user: str) -> Dict:
        """Retourne le statut d'un utilisateur."""
        current_time = datetime.now()
        self._clean_old_violations(user, current_time)
        
        if user not in self.user_violations:
            return {'user': user, 'warnings': 0, 'kicks': 0, 'violation_types': []}
        
        user_history = self.user_violations[user]
        return {
            'user': user,
            'warnings': len(user_history.warnings),
            'kicks': len(user_history.kicks), 
            'violation_types': list(user_history.violations_by_type.keys()),
            'last_action': self.last_action.get(user)
        }

    def clear_user_history(self, user: str):
        """Vide complètement l'historique d'un utilisateur (remet le compteur à 0)."""
        if user in self.user_violations:
            del self.user_violations[user]
        if user in self.last_action:
            del self.last_action[user]
        self.logger.info(f"Historique vidé pour l'utilisateur {user}")

    def clear_all_history(self):
        """Vide complètement tous les historiques (remet tous les compteurs à 0)."""
        self.user_violations.clear()
        self.last_action.clear()
        self.logger.info("Tous les historiques de violations ont été vidés")

    def clear_bans_on_startup(self, irc_client, channel="#francophonie"):
        """Vide toutes les bans au démarrage du bot."""
        try:
            # Envoyer la commande pour vider la banlist
            irc_client.connection.send_raw(f"MODE {channel} -b")
            self.logger.info(f"Banlist vidée au démarrage pour {channel}")
        except Exception as e:
            self.logger.error(f"Erreur lors du vidage de la banlist: {e}")