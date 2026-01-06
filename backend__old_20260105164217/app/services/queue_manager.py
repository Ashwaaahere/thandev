"""
Queue management service for per-user scan concurrency control.

Uses Redis to track and limit the number of concurrent scans per user.
"""
import logging
from contextlib import contextmanager
from typing import Optional
import redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class TooManyScansForUser(Exception):
    """Raised when a user has exceeded their maximum concurrent scan limit"""
    pass


class QueueManager:
    """Manages per-user scan concurrency using Redis"""
    
    def __init__(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            self.redis_client.ping()
            logger.info("QueueManager: Redis connection established")
        except Exception as e:
            logger.error(f"QueueManager: Failed to connect to Redis: {e}")
            # Fallback: use a mock client that always allows scans
            # This ensures the system works even if Redis is unavailable
            self.redis_client = None
            logger.warning("QueueManager: Running without Redis (no concurrency limits)")
    
    def _get_key(self, user_id: str) -> str:
        """Get Redis key for user scan slots"""
        return f"user_scan_slots:{user_id}"
    
    def get_active_scan_count(self, user_id: str) -> int:
        """Get the current number of active scans for a user"""
        if not self.redis_client:
            return 0  # If Redis unavailable, assume no active scans
        
        try:
            key = self._get_key(user_id)
            count = self.redis_client.get(key)
            return int(count) if count else 0
        except Exception as e:
            logger.warning(f"Failed to get active scan count for user {user_id}: {e}")
            return 0  # On error, allow the scan
    
    @contextmanager
    def user_scan_slot(self, user_id: str, max_per_user: int = 1):
        """
        Context manager for acquiring a scan slot for a user.
        
        Increments the counter on enter and decrements on exit.
        Raises TooManyScansForUser if the limit is exceeded.
        
        Args:
            user_id: User ID
            max_per_user: Maximum number of concurrent scans per user (default: 1)
            
        Raises:
            TooManyScansForUser: If user has reached the maximum concurrent scans
            
        Example:
            with queue_manager.user_scan_slot(user_id, max_per_user=1):
                # Run scan here
                pass
        """
        if not self.redis_client:
            # If Redis unavailable, allow the scan (no concurrency control)
            logger.debug(f"Redis unavailable, allowing scan for user {user_id} without concurrency check")
            yield
            return
        
        key = self._get_key(user_id)
        
        try:
            # Try to increment the counter
            # Use Redis INCR which is atomic
            current_count = self.redis_client.incr(key)
            
            # Set expiration on the key (1 hour) to prevent stale keys
            if current_count == 1:
                # First time setting this key, set expiration
                self.redis_client.expire(key, 3600)
            
            logger.debug(f"User {user_id} scan slot count: {current_count}/{max_per_user}")
            
            # Check if limit exceeded
            if current_count > max_per_user:
                # Decrement since we can't proceed
                self.redis_client.decr(key)
                raise TooManyScansForUser(
                    f"User {user_id} has {current_count - 1} active scans. "
                    f"Maximum allowed: {max_per_user}"
                )
            
            # Slot acquired successfully
            try:
                yield
            finally:
                # Always decrement on exit
                try:
                    new_count = self.redis_client.decr(key)
                    if new_count <= 0:
                        # Remove the key if count reaches 0
                        self.redis_client.delete(key)
                    logger.debug(f"User {user_id} scan slot released. Remaining: {new_count}")
                except Exception as e:
                    logger.error(f"Failed to release scan slot for user {user_id}: {e}")
                    
        except TooManyScansForUser:
            # Re-raise our custom exception
            raise
        except Exception as e:
            logger.error(f"Error managing scan slot for user {user_id}: {e}")
            # On error, allow the scan (fail open)
            yield


# Global instance
_queue_manager: Optional[QueueManager] = None


def get_queue_manager() -> QueueManager:
    """Get or create the global QueueManager instance"""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = QueueManager()
    return _queue_manager
