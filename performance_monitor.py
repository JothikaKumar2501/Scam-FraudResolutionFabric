"""
Performance Monitoring System for GenAI FraudOps Suite
Tracks agent execution times, API calls, and system performance metrics
"""

import time
import psutil
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import os
from contextlib import contextmanager
from functools import wraps
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """Individual performance metric"""
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def finish(self):
        """Mark the metric as finished and calculate duration"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time

@dataclass
class AgentPerformance:
    """Agent-specific performance data"""
    agent_name: str
    total_calls: int = 0
    total_duration: float = 0.0
    avg_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    last_call: Optional[datetime] = None
    errors: int = 0
    
    def update(self, duration: float, success: bool = True):
        """Update agent performance metrics"""
        self.total_calls += 1
        self.total_duration += duration
        self.avg_duration = self.total_duration / self.total_calls
        self.min_duration = min(self.min_duration, duration)
        self.max_duration = max(self.max_duration, duration)
        self.last_call = datetime.now()
        
        if not success:
            self.errors += 1

class PerformanceMonitor:
    """Main performance monitoring system"""
    
    def __init__(self, log_file: str = "performance_log.json"):
        self.log_file = log_file
        self.metrics: List[PerformanceMetric] = []
        self.agent_performance: Dict[str, AgentPerformance] = {}
        self.system_metrics: Dict[str, Any] = {}
        self.start_time = time.time()
        self.lock = threading.Lock()
        
        # Load existing metrics if file exists
        self._load_metrics()
    
    def _load_metrics(self):
        """Load existing metrics from file"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    data = json.load(f)
                    # Reconstruct metrics from saved data
                    for metric_data in data.get('metrics', []):
                        metric = PerformanceMetric(
                            name=metric_data['name'],
                            start_time=metric_data['start_time'],
                            end_time=metric_data.get('end_time'),
                            duration=metric_data.get('duration'),
                            metadata=metric_data.get('metadata', {})
                        )
                        self.metrics.append(metric)
            except Exception as e:
                logger.error(f"Error loading performance metrics: {e}")
    
    def _save_metrics(self):
        """Save metrics to file"""
        try:
            with open(self.log_file, 'w') as f:
                data = {
                    'metrics': [
                        {
                            'name': m.name,
                            'start_time': m.start_time,
                            'end_time': m.end_time,
                            'duration': m.duration,
                            'metadata': m.metadata
                        }
                        for m in self.metrics
                    ],
                    'agent_performance': {
                        name: {
                            'total_calls': perf.total_calls,
                            'total_duration': perf.total_duration,
                            'avg_duration': perf.avg_duration,
                            'min_duration': perf.min_duration,
                            'max_duration': perf.max_duration,
                            'last_call': perf.last_call.isoformat() if perf.last_call else None,
                            'errors': perf.errors
                        }
                        for name, perf in self.agent_performance.items()
                    },
                    'system_metrics': self.system_metrics,
                    'timestamp': datetime.now().isoformat()
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving performance metrics: {e}")
    
    @contextmanager
    def monitor(self, name: str, metadata: Dict[str, Any] = None):
        """Context manager for monitoring performance"""
        metric = PerformanceMetric(
            name=name,
            start_time=time.time(),
            metadata=metadata or {}
        )
        
        try:
            yield metric
        finally:
            metric.finish()
            with self.lock:
                self.metrics.append(metric)
                self._save_metrics()
    
    def monitor_agent(self, agent_name: str):
        """Decorator for monitoring agent performance"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    logger.error(f"Agent {agent_name} error: {e}")
                    raise
                finally:
                    duration = time.time() - start_time
                    with self.lock:
                        if agent_name not in self.agent_performance:
                            self.agent_performance[agent_name] = AgentPerformance(agent_name)
                        self.agent_performance[agent_name].update(duration, success)
                        self._save_metrics()
            
            return wrapper
        return decorator
    
    def get_agent_performance(self, agent_name: str) -> Optional[AgentPerformance]:
        """Get performance data for a specific agent"""
        return self.agent_performance.get(agent_name)
    
    def get_all_agent_performance(self) -> Dict[str, AgentPerformance]:
        """Get performance data for all agents"""
        return self.agent_performance.copy()
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            self.system_metrics = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_gb': memory.available / (1024**3),
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / (1024**3),
                'uptime_seconds': time.time() - self.start_time,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
        
        return self.system_metrics
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get overall performance summary"""
        total_metrics = len(self.metrics)
        completed_metrics = [m for m in self.metrics if m.duration is not None]
        
        if not completed_metrics:
            return {
                'total_metrics': total_metrics,
                'completed_metrics': 0,
                'avg_duration': 0,
                'total_duration': 0
            }
        
        total_duration = sum(m.duration for m in completed_metrics)
        avg_duration = total_duration / len(completed_metrics)
        
        return {
            'total_metrics': total_metrics,
            'completed_metrics': len(completed_metrics),
            'avg_duration': avg_duration,
            'total_duration': total_duration,
            'agent_count': len(self.agent_performance),
            'system_metrics': self.get_system_metrics()
        }
    
    def get_recent_metrics(self, minutes: int = 60) -> List[PerformanceMetric]:
        """Get metrics from the last N minutes"""
        cutoff_time = time.time() - (minutes * 60)
        return [m for m in self.metrics if m.start_time > cutoff_time]
    
    def clear_old_metrics(self, days: int = 7):
        """Clear metrics older than N days"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        with self.lock:
            self.metrics = [m for m in self.metrics if m.start_time > cutoff_time]
            self._save_metrics()
    
    def export_metrics(self, filename: str = None) -> str:
        """Export metrics to a file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_export_{timestamp}.json"
        
        data = {
            'summary': self.get_performance_summary(),
            'agent_performance': {
                name: {
                    'total_calls': perf.total_calls,
                    'total_duration': perf.total_duration,
                    'avg_duration': perf.avg_duration,
                    'min_duration': perf.min_duration,
                    'max_duration': perf.max_duration,
                    'last_call': perf.last_call.isoformat() if perf.last_call else None,
                    'errors': perf.errors
                }
                for name, perf in self.agent_performance.items()
            },
            'recent_metrics': [
                {
                    'name': m.name,
                    'start_time': m.start_time,
                    'end_time': m.end_time,
                    'duration': m.duration,
                    'metadata': m.metadata
                }
                for m in self.get_recent_metrics(1440)  # Last 24 hours
            ],
            'export_timestamp': datetime.now().isoformat()
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        return filename

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

# Convenience functions
def monitor_function(name: str = None):
    """Decorator to monitor function performance"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = name or func.__name__
            with performance_monitor.monitor(func_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator

def monitor_agent_performance(agent_name: str):
    """Decorator to monitor agent performance"""
    return performance_monitor.monitor_agent(agent_name)

def get_performance_dashboard_data() -> Dict[str, Any]:
    """Get data for performance dashboard"""
    summary = performance_monitor.get_performance_summary()
    agent_perf = performance_monitor.get_all_agent_performance()
    
    # Convert agent performance to list for easier processing
    agent_list = []
    for name, perf in agent_perf.items():
        agent_list.append({
            'name': name,
            'total_calls': perf.total_calls,
            'avg_duration': perf.avg_duration,
            'min_duration': perf.min_duration,
            'max_duration': perf.max_duration,
            'errors': perf.errors,
            'last_call': perf.last_call.isoformat() if perf.last_call else None
        })
    
    return {
        'summary': summary,
        'agents': agent_list,
        'recent_metrics': len(performance_monitor.get_recent_metrics(60))  # Last hour
    }

def log_api_call(api_name: str, duration: float, success: bool = True, metadata: Dict[str, Any] = None):
    """Log API call performance"""
    with performance_monitor.monitor(f"api_{api_name}", metadata or {}):
        pass  # The monitoring is done in the context manager
    
    # Also update agent performance if this is an agent API call
    if api_name.startswith('agent_'):
        agent_name = api_name.replace('agent_', '')
        if agent_name not in performance_monitor.agent_performance:
            performance_monitor.agent_performance[agent_name] = AgentPerformance(agent_name)
        performance_monitor.agent_performance[agent_name].update(duration, success)

# Performance alerts
class PerformanceAlert:
    """Performance alert system"""
    
    def __init__(self, threshold_duration: float = 30.0, threshold_errors: int = 5):
        self.threshold_duration = threshold_duration
        self.threshold_errors = threshold_errors
        self.alerts: List[Dict[str, Any]] = []
    
    def check_agent_performance(self, agent_name: str, performance: AgentPerformance):
        """Check if agent performance needs alerting"""
        alerts = []
        
        if performance.avg_duration > self.threshold_duration:
            alerts.append({
                'type': 'slow_performance',
                'agent': agent_name,
                'message': f"Agent {agent_name} is slow (avg: {performance.avg_duration:.2f}s)",
                'severity': 'warning'
            })
        
        if performance.errors > self.threshold_errors:
            alerts.append({
                'type': 'high_errors',
                'agent': agent_name,
                'message': f"Agent {agent_name} has {performance.errors} errors",
                'severity': 'error'
            })
        
        return alerts

# Global alert system
performance_alert = PerformanceAlert()

def check_performance_alerts() -> List[Dict[str, Any]]:
    """Check for performance alerts"""
    alerts = []
    agent_perf = performance_monitor.get_all_agent_performance()
    
    for agent_name, perf in agent_perf.items():
        agent_alerts = performance_alert.check_agent_performance(agent_name, perf)
        alerts.extend(agent_alerts)
    
    return alerts
