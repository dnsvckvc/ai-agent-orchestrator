"""
RSS Feed Monitor Agent - Monitors RSS feeds for new podcast episodes.

This agent periodically checks RSS feeds and identifies new episodes
that need processing (transcription, summarization, etc.).
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from agents.base_agent import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


@dataclass
class PodcastEpisode:
    """Represents a podcast episode from RSS feed."""
    episode_id: str
    title: str
    description: str
    audio_url: str
    publish_date: datetime
    duration: Optional[int] = None  # Duration in seconds
    podcast_name: str = ""
    podcast_url: str = ""
    author: str = ""
    guid: str = ""  # Unique identifier from feed


@dataclass
class RSSFeed:
    """Configuration for an RSS feed to monitor."""
    feed_url: str
    feed_name: str
    enabled: bool = True
    check_frequency_hours: int = 24
    last_checked: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)  # For categorization


class RSSFeedMonitorAgent(BaseAgent):
    """
    Agent that monitors RSS feeds for new podcast episodes.

    Capabilities:
    - Fetch and parse RSS feeds
    - Detect new episodes since last check
    - Filter episodes by date range
    - Track processed episodes to avoid duplicates
    - Support multiple feeds with individual configurations
    """

    def __init__(self, agent_id: str):
        super().__init__(agent_id, "rss_feed_monitor")

        # Storage for processed episode IDs (in production, use Redis or DB)
        self.processed_episodes: set[str] = set()

        # Feeds configuration (will be loaded from config file later)
        self.feeds: List[RSSFeed] = []

        logger.info(f"RSSFeedMonitorAgent {agent_id} initialized")

    async def process(
        self,
        inputs: List[AgentInput],
        parameters: Optional[Dict[str, Any]] = None
    ) -> AgentOutput:
        """
        Process RSS feeds and identify new episodes.

        Input types:
        - "feed_config": JSON configuration with RSS feed URLs and settings
        - "check_request": Request to check specific feeds

        Parameters:
        - lookback_days: How many days back to check (default: 7)
        - force_refresh: Ignore last check time (default: False)
        - feed_urls: Optional list of specific feeds to check

        Returns:
        - List of new podcast episodes to process
        """
        parameters = parameters or {}
        lookback_days = parameters.get("lookback_days", 7)
        force_refresh = parameters.get("force_refresh", False)
        specific_feeds = parameters.get("feed_urls", [])

        new_episodes = []

        # Load feeds from input or use existing configuration
        for agent_input in inputs:
            if agent_input.input_type == "feed_config":
                self._load_feed_config(agent_input.data)

        # If no feeds configured, return empty result
        if not self.feeds:
            logger.warning("No RSS feeds configured")
            return AgentOutput(
                output_type="new_episodes",
                data={"episodes": [], "feeds_checked": 0},
                metadata={"status": "no_feeds_configured"},
                processing_time_ms=0
            )

        # Filter feeds to check
        feeds_to_check = self.feeds
        if specific_feeds:
            feeds_to_check = [f for f in self.feeds if f.feed_url in specific_feeds]

        # Check each feed
        for feed in feeds_to_check:
            if not feed.enabled:
                continue

            # Check if feed needs refresh
            if not force_refresh and feed.last_checked:
                time_since_check = datetime.now() - feed.last_checked
                if time_since_check < timedelta(hours=feed.check_frequency_hours):
                    logger.debug(
                        f"Skipping {feed.feed_name}, checked "
                        f"{time_since_check.total_seconds() / 3600:.1f} hours ago"
                    )
                    continue

            # Fetch and parse feed
            try:
                episodes = await self._fetch_feed(feed, lookback_days)
                new_episodes.extend(episodes)
                feed.last_checked = datetime.now()
                logger.info(f"Found {len(episodes)} new episodes from {feed.feed_name}")
            except Exception as e:
                logger.error(f"Error checking feed {feed.feed_name}: {e}")

        # Remove duplicates and already processed
        unique_episodes = self._deduplicate_episodes(new_episodes)

        return AgentOutput(
            output_type="new_episodes",
            data={
                "episodes": [self._episode_to_dict(ep) for ep in unique_episodes],
                "feeds_checked": len(feeds_to_check),
                "new_count": len(unique_episodes)
            },
            metadata={
                "lookback_days": lookback_days,
                "force_refresh": force_refresh,
                "checked_at": datetime.now().isoformat()
            },
            processing_time_ms=0
        )

    async def _fetch_feed(
        self,
        feed: RSSFeed,
        lookback_days: int
    ) -> List[PodcastEpisode]:
        """
        Fetch and parse RSS feed for new episodes.

        This is a placeholder that will be implemented with actual
        RSS parsing library (feedparser) when feed URLs are provided.

        Args:
            feed: RSS feed configuration
            lookback_days: How many days back to look for episodes

        Returns:
            List of new episodes
        """
        try:
            import feedparser
        except ImportError:
            logger.warning(
                "feedparser not installed. Install with: pip install feedparser"
            )
            return []

        try:
            # Fetch feed
            parsed_feed = await asyncio.to_thread(feedparser.parse, feed.feed_url)

            if parsed_feed.bozo:
                logger.error(f"Error parsing feed {feed.feed_url}: {parsed_feed.bozo_exception}")
                return []

            episodes = []
            cutoff_date = datetime.now() - timedelta(days=lookback_days)

            # Parse entries
            for entry in parsed_feed.entries:
                # Extract publish date
                publish_date = self._parse_date(entry)
                if not publish_date or publish_date < cutoff_date:
                    continue

                # Extract audio URL (look for enclosures)
                audio_url = self._extract_audio_url(entry)
                if not audio_url:
                    continue

                # Create episode ID
                episode_id = entry.get("id") or entry.get("guid") or entry.get("link")
                if not episode_id:
                    # Generate ID from content
                    episode_id = self._generate_episode_id(entry.get("title", ""), publish_date)

                # Check if already processed
                if episode_id in self.processed_episodes:
                    continue

                # Create episode object
                episode = PodcastEpisode(
                    episode_id=episode_id,
                    title=entry.get("title", "Untitled"),
                    description=entry.get("summary", ""),
                    audio_url=audio_url,
                    publish_date=publish_date,
                    duration=self._extract_duration(entry),
                    podcast_name=feed.feed_name,
                    podcast_url=feed.feed_url,
                    author=entry.get("author", ""),
                    guid=entry.get("id", "")
                )

                episodes.append(episode)
                self.processed_episodes.add(episode_id)

            return episodes

        except Exception as e:
            logger.error(f"Error fetching feed {feed.feed_url}: {e}")
            return []

    def _parse_date(self, entry: Dict) -> Optional[datetime]:
        """Parse publication date from feed entry."""
        import email.utils

        # Try published_parsed first
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            import time
            return datetime.fromtimestamp(time.mktime(entry.published_parsed))

        # Try published string
        if hasattr(entry, "published"):
            try:
                parsed = email.utils.parsedate_to_datetime(entry.published)
                return parsed
            except Exception:
                pass

        # Try updated
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            import time
            return datetime.fromtimestamp(time.mktime(entry.updated_parsed))

        return None

    def _extract_audio_url(self, entry: Dict) -> Optional[str]:
        """Extract audio URL from feed entry enclosures."""
        # Check enclosures
        if hasattr(entry, "enclosures"):
            for enclosure in entry.enclosures:
                # Look for audio types
                if "audio" in enclosure.get("type", "").lower():
                    return enclosure.get("href") or enclosure.get("url")

        # Fallback to links
        if hasattr(entry, "links"):
            for link in entry.links:
                if link.get("type", "").startswith("audio/"):
                    return link.get("href")

        return None

    def _extract_duration(self, entry: Dict) -> Optional[int]:
        """Extract episode duration in seconds."""
        # Check iTunes duration
        if hasattr(entry, "itunes_duration"):
            duration_str = entry.itunes_duration
            # Parse HH:MM:SS or MM:SS or just seconds
            parts = duration_str.split(":")
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            else:
                try:
                    return int(duration_str)
                except ValueError:
                    pass

        return None

    def _generate_episode_id(self, title: str, publish_date: datetime) -> str:
        """Generate unique episode ID from title and date."""
        content = f"{title}_{publish_date.isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()

    def _deduplicate_episodes(self, episodes: List[PodcastEpisode]) -> List[PodcastEpisode]:
        """Remove duplicate episodes based on episode_id."""
        seen = set()
        unique = []

        for episode in episodes:
            if episode.episode_id not in seen:
                seen.add(episode.episode_id)
                unique.append(episode)

        return unique

    def _episode_to_dict(self, episode: PodcastEpisode) -> Dict[str, Any]:
        """Convert episode to dictionary for serialization."""
        return {
            "episode_id": episode.episode_id,
            "title": episode.title,
            "description": episode.description,
            "audio_url": episode.audio_url,
            "publish_date": episode.publish_date.isoformat(),
            "duration": episode.duration,
            "podcast_name": episode.podcast_name,
            "podcast_url": episode.podcast_url,
            "author": episode.author,
            "guid": episode.guid
        }

    def _load_feed_config(self, config_data: Any):
        """Load feed configuration from input data."""
        if isinstance(config_data, dict):
            feeds = config_data.get("feeds", [])
            for feed_config in feeds:
                feed = RSSFeed(
                    feed_url=feed_config["feed_url"],
                    feed_name=feed_config.get("feed_name", "Unknown"),
                    enabled=feed_config.get("enabled", True),
                    check_frequency_hours=feed_config.get("check_frequency_hours", 24),
                    tags=feed_config.get("tags", [])
                )
                self.feeds.append(feed)

    def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return [
            "rss_feed_monitoring",
            "podcast_episode_detection",
            "feed_parsing",
            "duplicate_detection"
        ]
