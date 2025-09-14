import json
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path


class StateManager:
    """
    Gestionnaire d'état pour AlphaBaboon - Sauvegarde et restauration des données.
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.state_file = config.get('state_manager', {}).get('state_file', 'bot_state.json')
        self.backup_file = config.get('state_manager', {}).get('backup_file', 'bot_state_backup.json')
        self.save_interval = config.get('state_manager', {}).get('save_interval_minutes', 10) * 60
        self.max_age_hours = config.get('state_manager', {}).get('max_violation_age_hours', 48)
        
        # État à sauvegarder
        self.state_data = {}
        
        # Thread de sauvegarde
        self.save_thread = None
        self.is_running = False
        
        # Références aux composants
        self.moderation_handler = None
    
    def set_moderation_handler(self, moderation_handler):
        """Associe le gestionnaire de modération pour la sauvegarde d'état."""
        self.moderation_handler = moderation_handler
    
    def start_auto_save(self):
        """Démarre la sauvegarde automatique périodique."""
        if self.is_running:
            return
        
        self.is_running = True
        self.save_thread = threading.Thread(target=self._auto_save_loop, daemon=True)
        self.save_thread.start()
        self.logger.info(f"Sauvegarde automatique démarrée (toutes les {self.save_interval//60} minutes)")
    
    def stop_auto_save(self):
        """Arrête la sauvegarde automatique."""
        self.is_running = False
        if self.save_thread:
            self.save_thread.join(timeout=5)
        
        # Sauvegarder une dernière fois
        self.save_state()
        self.logger.info("Sauvegarde automatique arrêtée")
    
    def _auto_save_loop(self):
        """Boucle de sauvegarde automatique."""
        while self.is_running:
            try:
                time.sleep(self.save_interval)
                if self.is_running:  # Vérifier qu'on n'est pas en cours d'arrêt
                    self.save_state()
            except Exception as e:
                self.logger.error(f"Erreur dans la boucle de sauvegarde automatique: {e}")
    
    def save_state(self):
        """Sauvegarde l'état actuel du bot."""
        try:
            # Préparer les données à sauvegarder
            state_data = {
                'timestamp': datetime.now().isoformat(),
                'version': '3.0',
                'user_violations': {},
                'stats': {
                    'total_saves': self.state_data.get('stats', {}).get('total_saves', 0) + 1,
                    'last_save': datetime.now().isoformat()
                }
            }
            
            # Sauvegarder les violations utilisateurs si disponibles
            if self.moderation_handler and hasattr(self.moderation_handler, 'user_violations'):
                # Filtrer les violations récentes seulement
                cutoff_time = datetime.now() - timedelta(hours=self.max_age_hours)
                
                for user, history in self.moderation_handler.user_violations.items():
                    if hasattr(history, 'warnings'):
                        # Format nouveau (AdvancedModerationHandler)
                        recent_warnings = [
                            w.isoformat() if hasattr(w, 'isoformat') else str(w)
                            for w in history.warnings if w > cutoff_time
                        ]
                        recent_kicks = [
                            k.isoformat() if hasattr(k, 'isoformat') else str(k)
                            for k in history.kicks if k > cutoff_time
                        ]
                        
                        if recent_warnings or recent_kicks:
                            state_data['user_violations'][user] = {
                                'warnings': recent_warnings,
                                'kicks': recent_kicks,
                                'violations_by_type': {
                                    vtype: [v.isoformat() if hasattr(v, 'isoformat') else str(v) 
                                           for v in violations if v > cutoff_time]
                                    for vtype, violations in history.violations_by_type.items()
                                }
                            }
                    else:
                        # Format ancien (liste simple)
                        recent_violations = [
                            v.isoformat() if hasattr(v, 'isoformat') else str(v)
                            for v in history if v > cutoff_time
                        ]
                        if recent_violations:
                            state_data['user_violations'][user] = {'violations': recent_violations}
            
            # Créer une sauvegarde de l'ancien fichier
            state_path = Path(self.state_file)
            backup_path = Path(self.backup_file)
            
            if state_path.exists():
                # Copier l'ancien fichier en backup
                import shutil
                shutil.copy2(state_path, backup_path)
            
            # Écrire le nouvel état
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)
            
            self.state_data = state_data
            
            users_count = len(state_data['user_violations'])
            total_saves = state_data['stats']['total_saves']
            
            self.logger.debug(f"État sauvegardé: {users_count} utilisateurs, sauvegarde #{total_saves}")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde d'état: {e}")
            import traceback
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
    
    def restore_state(self) -> bool:
        """Restaure l'état depuis le fichier de sauvegarde."""
        try:
            state_path = Path(self.state_file)
            backup_path = Path(self.backup_file)
            
            # Tenter de charger le fichier principal
            load_path = None
            if state_path.exists():
                load_path = state_path
            elif backup_path.exists():
                load_path = backup_path
                self.logger.warning("Fichier d'état principal introuvable, utilisation du backup")
            
            if not load_path:
                self.logger.info("Aucun fichier d'état trouvé, démarrage à neuf")
                return False
            
            with open(load_path, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # Vérifier la version
            version = state_data.get('version', '1.0')
            if version != '3.0':
                self.logger.warning(f"Version d'état incompatible: {version}, démarrage à neuf")
                return False
            
            # Vérifier l'âge du fichier
            timestamp_str = state_data.get('timestamp')
            if timestamp_str:
                try:
                    from datetime import datetime
                    timestamp = datetime.fromisoformat(timestamp_str)
                    age_hours = (datetime.now() - timestamp).total_seconds() / 3600
                    
                    if age_hours > 24:  # État trop ancien
                        self.logger.warning(f"État trop ancien ({age_hours:.1f}h), démarrage à neuf")
                        return False
                        
                except ValueError:
                    pass
            
            # Restaurer les données si moderation_handler disponible
            if self.moderation_handler and hasattr(self.moderation_handler, 'user_violations'):
                restored_users = 0
                
                for user, data in state_data.get('user_violations', {}).items():
                    if 'warnings' in data:  # Format nouveau
                        from advanced_moderation_handler import UserViolationHistory
                        from datetime import datetime
                        
                        history = UserViolationHistory(warnings=[], kicks=[], violations_by_type={})
                        
                        # Restaurer warnings
                        for w_str in data.get('warnings', []):
                            try:
                                history.warnings.append(datetime.fromisoformat(w_str))
                            except ValueError:
                                continue
                        
                        # Restaurer kicks
                        for k_str in data.get('kicks', []):
                            try:
                                history.kicks.append(datetime.fromisoformat(k_str))
                            except ValueError:
                                continue
                        
                        # Restaurer violations par type
                        for vtype, violations in data.get('violations_by_type', {}).items():
                            history.violations_by_type[vtype] = []
                            for v_str in violations:
                                try:
                                    history.violations_by_type[vtype].append(datetime.fromisoformat(v_str))
                                except ValueError:
                                    continue
                        
                        if history.warnings or history.kicks:
                            self.moderation_handler.user_violations[user] = history
                            restored_users += 1
                    
                    else:  # Format ancien (compatibilité)
                        violations = []
                        for v_str in data.get('violations', []):
                            try:
                                violations.append(datetime.fromisoformat(v_str))
                            except ValueError:
                                continue
                        
                        if violations:
                            # Adapter au nouveau format
                            from advanced_moderation_handler import UserViolationHistory
                            history = UserViolationHistory(warnings=violations, kicks=[], violations_by_type={})
                            self.moderation_handler.user_violations[user] = history
                            restored_users += 1
                
                total_saves = state_data.get('stats', {}).get('total_saves', 0)
                self.logger.info(f"État restauré: {restored_users} utilisateurs, sauvegarde #{total_saves}")
                self.state_data = state_data
                return True
            
            else:
                self.logger.warning("Moderation handler non disponible, état non restauré")
                return False
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la restauration d'état: {e}")
            import traceback
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
            return False
    
    def get_state_info(self) -> Dict[str, Any]:
        """Retourne des informations sur l'état sauvegardé."""
        try:
            if Path(self.state_file).exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                return {
                    'file_exists': True,
                    'timestamp': data.get('timestamp'),
                    'version': data.get('version'),
                    'users_count': len(data.get('user_violations', {})),
                    'total_saves': data.get('stats', {}).get('total_saves', 0),
                    'file_size_kb': Path(self.state_file).stat().st_size / 1024
                }
            else:
                return {
                    'file_exists': False,
                    'message': 'Aucun fichier d\'état trouvé'
                }
        except Exception as e:
            return {
                'file_exists': False,
                'error': str(e)
            }