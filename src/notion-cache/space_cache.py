import logging
import threading

from cachetools import TTLCache

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 1800 


class SpaceCache:
    """Thread-safe cache mapping space names to UUIDs."""

    def __init__(self, notion_service, ttl: int = _DEFAULT_TTL):
        self._notion = notion_service
        self._cache = TTLCache(maxsize=100, ttl=ttl)
        self._lock = threading.Lock()

    def load(self) -> None:
        """Fetch spaces from Notion and populate the cache."""
        try:
            spaces = self._notion.list_spaces()
            with self._lock:
                self._cache.clear()
                for space in spaces:
                    self._cache[space["name"]] = space["id"]
            logger.info("SpaceCache loaded %d space(s)", len(spaces))
        except Exception as e:
            logger.error("SpaceCache failed to load: %s", e, exc_info=True)

    def add(self, name: str, uuid: str) -> None:
        """Add a single space to the cache."""
        with self._lock:
            self._cache[name] = uuid
        logger.info("SpaceCache added space '%s'", name)

    def invalidate(self) -> None:
        """Clear cache and reload from Notion."""
        self.load()

    def get_spaces(self) -> dict[str, str]:
        """Return a snapshot of {name: uuid} mappings."""
        with self._lock:
            return dict(self._cache)
