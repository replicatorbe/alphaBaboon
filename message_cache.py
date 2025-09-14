import hashlib
import json
import time
from typing import Optional, Tuple
import logging


class MessageCache:
    def __init__(self, cache_duration_hours=24, max_cache_size=1000):
        self.cache = {}
        self.cache_duration = cache_duration_hours * 3600  # Convert to seconds
        self.max_cache_size = max_cache_size
        self.logger = logging.getLogger(__name__)
        
        # Statistiques
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_savings = 0.0

    def _hash_message(self, message: str) -> str:
        """Créé un hash du message pour la clé de cache."""
        # Normaliser le message (minuscules, espaces nettoyés)
        normalized = ' '.join(message.lower().strip().split())
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    def get(self, message: str) -> Optional[Tuple[bool, float]]:
        """Récupère un résultat du cache s'il existe et est valide."""
        key = self._hash_message(message)
        
        if key in self.cache:
            cached_data = self.cache[key]
            current_time = time.time()
            
            # Vérifier si le cache n'a pas expiré
            if current_time - cached_data['timestamp'] <= self.cache_duration:
                self.cache_hits += 1
                self.total_savings += 0.0001  # Coût réduit avec API Moderation gratuite
                self.logger.debug(f"Cache HIT pour message: {message[:50]}...")
                return cached_data['is_adult_content'], cached_data['confidence_score']
            else:
                # Nettoyer l'entrée expirée
                del self.cache[key]
        
        self.cache_misses += 1
        return None

    def put(self, message: str, is_adult_content: bool, confidence_score: float):
        """Stocke un résultat dans le cache."""
        key = self._hash_message(message)
        
        # Nettoyage si le cache est plein
        if len(self.cache) >= self.max_cache_size:
            self._cleanup_old_entries()
        
        self.cache[key] = {
            'is_adult_content': is_adult_content,
            'confidence_score': confidence_score,
            'timestamp': time.time()
        }
        
        self.logger.debug(f"Cache MISS - Stockage pour: {message[:50]}...")

    def _cleanup_old_entries(self):
        """Nettoie les entrées les plus anciennes du cache."""
        current_time = time.time()
        
        # Supprimer les entrées expirées
        expired_keys = [
            key for key, data in self.cache.items()
            if current_time - data['timestamp'] > self.cache_duration
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        # Si encore trop d'entrées, supprimer les plus anciennes
        if len(self.cache) >= self.max_cache_size:
            sorted_entries = sorted(
                self.cache.items(),
                key=lambda x: x[1]['timestamp']
            )
            
            # Garder seulement les 80% les plus récentes
            keep_count = int(self.max_cache_size * 0.8)
            entries_to_remove = sorted_entries[:-keep_count]
            
            for key, _ in entries_to_remove:
                del self.cache[key]
        
        self.logger.info(f"Cache nettoyé, {len(self.cache)} entrées restantes")

    def get_stats(self) -> dict:
        """Retourne les statistiques du cache."""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate_percent': round(hit_rate, 2),
            'total_savings_usd': round(self.total_savings, 4),
            'cache_size': len(self.cache)
        }

    def clear(self):
        """Vide complètement le cache."""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_savings = 0.0
        self.logger.info("Cache vidé complètement")