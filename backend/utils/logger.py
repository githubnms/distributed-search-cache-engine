"""
Logging Utility
Provides structured logging with different formats and outputs
"""

import logging
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import traceback

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def setup_logging():
    """Setup logging configuration"""
    # Create logs directory if it doesn't exist
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    root_logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(
        log_dir / f'app_{datetime.now().strftime("%Y%m%d")}.log'
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    root_logger.addHandler(file_handler)
    
    # Set third-party loggers to WARNING
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('fastapi').setLevel(logging.WARNING)
    
    return root_logger

def get_logger(name: str) -> logging.Logger:
    """Get logger instance"""
    return logging.getLogger(name)

class StructuredLogger:
    """
    Structured logger that outputs JSON format for better parsing
    """
    
    def __init__(self, name: str, log_dir: str = "logs"):
        self.logger = logging.getLogger(name)
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # Set level
        self.logger.setLevel(logging.DEBUG)
        
        # Console handler (JSON format)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(console_handler)
        
        # File handler (JSON format)
        file_handler = logging.FileHandler(
            self.log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(file_handler)
        
        # Error file handler (for errors only)
        error_handler = logging.FileHandler(
            self.log_dir / f"{name}_error_{datetime.now().strftime('%Y%m%d')}.log"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(error_handler)
    
    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, exc_info: bool = False, **kwargs):
        if exc_info:
            kwargs['exception'] = traceback.format_exc()
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log(logging.CRITICAL, message, **kwargs)
    
    def _log(self, level: int, message: str, **kwargs):
        extra = {
            'timestamp': datetime.utcnow().isoformat(),
            'logger': self.logger.name,
            **kwargs
        }
        self.logger.log(level, message, extra=extra)

class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging
    """
    
    def format(self, record):
        log_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage()
        }
        
        # Add exception info if present
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, 'extra'):
            log_record.update(record.extra)
        
        return json.dumps(log_record)

class LoggerContext:
    """
    Context manager for adding context to logs
    """
    
    def __init__(self, logger: StructuredLogger, **context):
        self.logger = logger
        self.context = context
        self.old_filters = []
    
    def __enter__(self):
        # Add filter to inject context
        filter = ContextFilter(self.context)
        self.logger.logger.addFilter(filter)
        self.old_filters.append(filter)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Remove filter
        for filter in self.old_filters:
            self.logger.logger.removeFilter(filter)

class ContextFilter(logging.Filter):
    """
    Filter that adds context to log records
    """
    
    def __init__(self, context: Dict):
        super().__init__()
        self.context = context
    
    def filter(self, record):
        if not hasattr(record, 'extra'):
            record.extra = {}
        record.extra.update(self.context)
        return True

# Performance monitoring decorator
def log_performance(logger):
    """
    Decorator to log function performance
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            import time
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start
                logger.info(f"{func.__name__} completed", 
                          function=func.__name__,
                          duration_ms=round(duration * 1000, 2),
                          status="success")
                return result
            except Exception as e:
                duration = time.time() - start
                logger.error(f"{func.__name__} failed",
                           function=func.__name__,
                           duration_ms=round(duration * 1000, 2),
                           error=str(e),
                           exc_info=True)
                raise
        
        def sync_wrapper(*args, **kwargs):
            import time
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start
                logger.info(f"{func.__name__} completed",
                          function=func.__name__,
                          duration_ms=round(duration * 1000, 2),
                          status="success")
                return result
            except Exception as e:
                duration = time.time() - start
                logger.error(f"{func.__name__} failed",
                           function=func.__name__,
                           duration_ms=round(duration * 1000, 2),
                           error=str(e),
                           exc_info=True)
                raise
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator