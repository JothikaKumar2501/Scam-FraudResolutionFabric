import json
import os
from typing import Dict, Any, Optional, List
import hashlib
import time
from functools import lru_cache
import pickle

# Import Mem0 integration
try:
    from mem0_integration import get_mem0_manager, store_memory, retrieve_memories, MemoryType
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    print("Warning: Mem0 integration not available")

class ContextStore:
    """Enhanced context store with intelligent caching, performance optimization, and Mem0 integration"""
    
    def __init__(self, cache_dir="context_cache", max_cache_size=1000):
        self.cache_dir = cache_dir
        self.max_cache_size = max_cache_size
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
        
        # Create cache directory if it doesn't exist
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        
        # Initialize in-memory cache for frequently accessed data
        self._memory_cache = {}
        self._cache_timestamps = {}
        self._cache_access_count = {}
        
        # Initialize Mem0 manager if available
        self.mem0_manager = None
        if MEM0_AVAILABLE:
            try:
                self.mem0_manager = get_mem0_manager()
                print("Mem0 integration initialized successfully")
            except Exception as e:
                print(f"Mem0 integration failed: {e}")
                self.mem0_manager = None
    
    def _generate_cache_key(self, data: Any, prefix: str = "") -> str:
        """Generate a unique cache key for data"""
        if isinstance(data, dict):
            # Sort dictionary keys for consistent hashing
            sorted_data = json.dumps(data, sort_keys=True, default=str)
        else:
            sorted_data = str(data)
        
        # Create hash of the data
        data_hash = hashlib.md5(sorted_data.encode()).hexdigest()
        return f"{prefix}_{data_hash}" if prefix else data_hash
    
    def _get_cache_file_path(self, cache_key: str) -> str:
        """Get the file path for a cache key"""
        return os.path.join(self.cache_dir, f"{cache_key}.pkl")
    
    def _is_cache_valid(self, cache_key: str, max_age_seconds: int = 3600) -> bool:
        """Check if cache entry is still valid (not expired)"""
        if cache_key not in self._cache_timestamps:
            return False
        
        cache_time = self._cache_timestamps[cache_key]
        return (time.time() - cache_time) < max_age_seconds
    
    def _evict_oldest_cache(self):
        """Evict the oldest cache entry when cache is full"""
        if len(self._memory_cache) >= self.max_cache_size:
            # Find the oldest accessed cache entry
            oldest_key = min(self._cache_access_count.keys(), 
                           key=lambda k: self._cache_access_count.get(k, 0))
            
            # Remove from memory cache
            if oldest_key in self._memory_cache:
                del self._memory_cache[oldest_key]
            if oldest_key in self._cache_timestamps:
                del self._cache_timestamps[oldest_key]
            if oldest_key in self._cache_access_count:
                del self._cache_access_count[oldest_key]
            
            # Remove from disk cache
            cache_file = self._get_cache_file_path(oldest_key)
            if os.path.exists(cache_file):
                os.remove(cache_file)
            
            self.cache_stats['evictions'] += 1
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from cache with intelligent fallback"""
        # Try memory cache first
        if key in self._memory_cache and self._is_cache_valid(key):
            self._cache_access_count[key] = self._cache_access_count.get(key, 0) + 1
            self.cache_stats['hits'] += 1
            return self._memory_cache[key]
        
        # Try disk cache
        cache_file = self._get_cache_file_path(key)
        if os.path.exists(cache_file) and self._is_cache_valid(key):
            try:
                with open(cache_file, 'rb') as f:
                    data = pickle.load(f)
                # Move to memory cache for faster access
                self._memory_cache[key] = data
                self._cache_timestamps[key] = time.time()
                self._cache_access_count[key] = 1
                self.cache_stats['hits'] += 1
                return data
            except Exception as e:
                print(f"Error loading cache file {cache_file}: {e}")
        
        self.cache_stats['misses'] += 1
        return default
    
    def set(self, key: str, value: Any, max_age_seconds: int = 3600) -> None:
        """Set a value in cache with expiration"""
        # Evict oldest if cache is full
        if len(self._memory_cache) >= self.max_cache_size:
            self._evict_oldest_cache()
        
        # Store in memory cache
        self._memory_cache[key] = value
        self._cache_timestamps[key] = time.time()
        self._cache_access_count[key] = self._cache_access_count.get(key, 0) + 1
        
        # Store in disk cache for persistence
        try:
            cache_file = self._get_cache_file_path(key)
            with open(cache_file, 'wb') as f:
                pickle.dump(value, f)
        except Exception as e:
            print(f"Error saving cache file {cache_file}: {e}")
    
    def cache_agent_response(self, agent_name: str, input_data: Any, response: Any, 
                           max_age_seconds: int = 1800) -> None:
        """Cache agent responses to avoid redundant API calls"""
        cache_key = self._generate_cache_key(input_data, f"agent_{agent_name}")
        self.set(cache_key, response, max_age_seconds)
    
    def get_cached_agent_response(self, agent_name: str, input_data: Any) -> Optional[Any]:
        """Get cached agent response if available"""
        cache_key = self._generate_cache_key(input_data, f"agent_{agent_name}")
        return self.get(cache_key)
    
    def cache_context_data(self, context_type: str, data: Any, 
                          max_age_seconds: int = 7200) -> None:
        """Cache context data for reuse across agents"""
        cache_key = self._generate_cache_key(data, f"context_{context_type}")
        self.set(cache_key, data, max_age_seconds)
    
    def get_cached_context_data(self, context_type: str, data: Any) -> Optional[Any]:
        """Get cached context data if available"""
        cache_key = self._generate_cache_key(data, f"context_{context_type}")
        return self.get(cache_key)
    
    def cache_transaction_context(self, transaction_id: str, context: Dict[str, Any]) -> None:
        """Cache transaction-specific context data"""
        cache_key = f"transaction_{transaction_id}"
        self.set(cache_key, context, max_age_seconds=3600)
    
    def get_cached_transaction_context(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Get cached transaction context if available"""
        cache_key = f"transaction_{transaction_id}"
        return self.get(cache_key)
    
    def invalidate_cache(self, pattern: str = None) -> None:
        """Invalidate cache entries matching a pattern"""
        if pattern is None:
            # Clear all cache
            self._memory_cache.clear()
            self._cache_timestamps.clear()
            self._cache_access_count.clear()
            
            # Clear disk cache
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.pkl'):
                    os.remove(os.path.join(self.cache_dir, filename))
        else:
            # Clear cache entries matching pattern
            keys_to_remove = [key for key in self._memory_cache.keys() if pattern in key]
            for key in keys_to_remove:
                del self._memory_cache[key]
                if key in self._cache_timestamps:
                    del self._cache_timestamps[key]
                if key in self._cache_access_count:
                    del self._cache_access_count[key]
                
                # Remove from disk cache
                cache_file = self._get_cache_file_path(key)
                if os.path.exists(cache_file):
                    os.remove(cache_file)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        stats = {
            'memory_cache_size': len(self._memory_cache),
            'disk_cache_files': len([f for f in os.listdir(self.cache_dir) if f.endswith('.pkl')]),
            'max_cache_size': self.max_cache_size,
            'cache_hit_rate': self.cache_stats['hits'] / (self.cache_stats['hits'] + self.cache_stats['misses']) if (self.cache_stats['hits'] + self.cache_stats['misses']) > 0 else 0,
            'evictions': self.cache_stats['evictions'],
            'mem0_available': MEM0_AVAILABLE and self.mem0_manager is not None
        }
        return stats
    
    # Mem0 Integration Methods
    
    def store_mem0_context(self, case_id: str, context_data: Dict[str, Any], agent_name: str = "system") -> bool:
        """Store context data in Mem0"""
        if not self.mem0_manager:
            return False
        
        try:
            return self.mem0_manager.store_context_summary(case_id, agent_name, json.dumps(context_data, indent=2))
        except Exception as e:
            print(f"Error storing context in Mem0: {e}")
            return False
    
    def store_mem0_agent_summary(self, case_id: str, agent_name: str, summary: str) -> bool:
        """Store agent summary in Mem0"""
        if not self.mem0_manager:
            return False
        
        try:
            return self.mem0_manager.store_agent_summary(case_id, agent_name, summary)
        except Exception as e:
            print(f"Error storing agent summary in Mem0: {e}")
            return False
    
    def store_mem0_risk_assessment(self, case_id: str, risk_assessment: str, confidence: float) -> bool:
        """Store risk assessment in Mem0"""
        if not self.mem0_manager:
            return False
        
        try:
            return self.mem0_manager.store_risk_assessment(case_id, risk_assessment, confidence)
        except Exception as e:
            print(f"Error storing risk assessment in Mem0: {e}")
            return False
    
    def store_mem0_policy_decision(self, case_id: str, policy_decision: str) -> bool:
        """Store policy decision in Mem0"""
        if not self.mem0_manager:
            return False
        
        try:
            return self.mem0_manager.store_policy_decision(case_id, policy_decision)
        except Exception as e:
            print(f"Error storing policy decision in Mem0: {e}")
            return False
    
    def store_mem0_customer_interaction(self, case_id: str, interaction: str) -> bool:
        """Store customer interaction in Mem0"""
        if not self.mem0_manager:
            return False
        
        try:
            return self.mem0_manager.store_customer_interaction(case_id, interaction)
        except Exception as e:
            print(f"Error storing customer interaction in Mem0: {e}")
            return False
    
    def retrieve_mem0_memories(self, case_id: str, query: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve memories from Mem0"""
        if not self.mem0_manager:
            return []
        
        try:
            if query:
                return self.mem0_manager.search_case_memories(case_id, query, limit)
            else:
                return self.mem0_manager.retrieve_case_memories(case_id, limit)
        except Exception as e:
            print(f"Error retrieving memories from Mem0: {e}")
            return []
    
    def get_mem0_case_summary(self, case_id: str) -> str:
        """Get case summary from Mem0"""
        if not self.mem0_manager:
            return "Mem0 not available"
        
        try:
            return self.mem0_manager.get_case_summary(case_id)
        except Exception as e:
            print(f"Error getting case summary from Mem0: {e}")
            return f"Error retrieving case summary: {e}"
    
    def clear_cache_stats(self) -> None:
        """Clear cache statistics"""
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
    
    def optimize_cache(self) -> None:
        """Optimize cache performance by removing old entries and defragmenting"""
        current_time = time.time()
        
        # Remove expired cache entries
        expired_keys = []
        for key, timestamp in self._cache_timestamps.items():
            if (current_time - timestamp) > 7200:  # 2 hours
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove_from_cache(key)
        
        # If cache is still too large, remove least accessed entries
        if len(self._memory_cache) > self.max_cache_size * 0.8:
            # Sort by access count and remove least accessed
            sorted_keys = sorted(self._cache_access_count.keys(), 
                               key=lambda k: self._cache_access_count.get(k, 0))
            
            # Remove 20% of least accessed entries
            remove_count = int(len(sorted_keys) * 0.2)
            for key in sorted_keys[:remove_count]:
                self._remove_from_cache(key)
    
    def _remove_from_cache(self, key: str) -> None:
        """Remove a key from all cache layers"""
        if key in self._memory_cache:
            del self._memory_cache[key]
        if key in self._cache_timestamps:
            del self._cache_timestamps[key]
        if key in self._cache_access_count:
            del self._cache_access_count[key]
        
        # Remove from disk cache
        cache_file = self._get_cache_file_path(key)
        if os.path.exists(cache_file):
            try:
                os.remove(cache_file)
            except Exception as e:
                print(f"Error removing cache file {cache_file}: {e}")
    
    def __getitem__(self, key: str) -> Any:
        """Get item using bracket notation"""
        return self.get(key)
    
    def __setitem__(self, key: str, value: Any) -> None:
        """Set item using bracket notation"""
        self.set(key, value)
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache"""
        return key in self._memory_cache or os.path.exists(self._get_cache_file_path(key))
    
    def __len__(self) -> int:
        """Get total number of cached items"""
        return len(self._memory_cache) + len([f for f in os.listdir(self.cache_dir) if f.endswith('.pkl')])
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get detailed memory usage statistics"""
        memory_size = sum(len(str(v)) for v in self._memory_cache.values())
        disk_size = 0
        
        try:
            for f in os.listdir(self.cache_dir):
                if f.endswith('.pkl'):
                    file_path = self._get_cache_file_path(f.replace('.pkl', ''))
                    if os.path.exists(file_path):
                        disk_size += os.path.getsize(file_path)
        except Exception:
            pass
        
        return {
            'memory_cache_size_bytes': memory_size,
            'disk_cache_size_bytes': disk_size,
            'total_size_bytes': memory_size + disk_size,
            'memory_cache_items': len(self._memory_cache),
            'disk_cache_files': len([f for f in os.listdir(self.cache_dir) if f.endswith('.pkl')])
        }

# Global context store instance
context_store = ContextStore()

# Convenience functions for easy caching
def cache_agent_result(agent_name: str, input_data: Any, result: Any) -> None:
    """Cache agent result for future use"""
    context_store.cache_agent_response(agent_name, input_data, result)

def get_cached_agent_result(agent_name: str, input_data: Any) -> Optional[Any]:
    """Get cached agent result if available"""
    return context_store.get_cached_agent_response(agent_name, input_data)

def cache_context(context_type: str, data: Any, context: Dict[str, Any]) -> None:
    """Cache context data for reuse"""
    context_store.cache_context_data(context_type, data, context)

def get_cached_context(context_type: str, data: Any) -> Optional[Any]:
    """Get cached context data if available"""
    return context_store.get_cached_context_data(context_type, data) 