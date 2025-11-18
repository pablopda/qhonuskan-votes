# cache.py

from django.core.cache import cache
from qhonuskan_votes.utils import sum_with_default


class VoteCache:
    """
    Caching layer for vote scores to improve performance.

    Uses Django's cache framework to store computed vote scores,
    reducing database queries for frequently accessed objects.
    """

    # Cache timeout in seconds (1 hour default)
    CACHE_TIMEOUT = 3600

    # Cache key prefix to avoid collisions
    CACHE_PREFIX = 'qhonuskan_votes:score'

    @classmethod
    def _make_key(cls, vote_model, object_id):
        """
        Create a unique cache key for a vote model and object.

        Args:
            vote_model: The vote model class or its name string
            object_id: The ID of the object being voted on

        Returns:
            A unique cache key string
        """
        if hasattr(vote_model, 'get_model_name'):
            model_name = vote_model.get_model_name()
        elif hasattr(vote_model, '_meta'):
            model_name = f'{vote_model._meta.app_label}.{vote_model._meta.object_name}'
        else:
            model_name = str(vote_model)

        return f'{cls.CACHE_PREFIX}:{model_name}:{object_id}'

    @classmethod
    def get_score(cls, vote_model, object_id):
        """
        Get the cached score for an object, or compute and cache it.

        Args:
            vote_model: The vote model class
            object_id: The ID of the object being voted on

        Returns:
            The vote score (integer)
        """
        cache_key = cls._make_key(vote_model, object_id)

        # Try to get from cache
        score = cache.get(cache_key)

        if score is None:
            # Compute the score from database
            result = vote_model.objects.filter(
                object__id=object_id
            ).aggregate(score=sum_with_default("value", default=0))

            score = result.get('score', 0)

            # Store in cache
            cache.set(cache_key, score, cls.CACHE_TIMEOUT)

        return score

    @classmethod
    def invalidate(cls, vote_model, object_id):
        """
        Clear the cached score when a vote changes.

        Args:
            vote_model: The vote model class
            object_id: The ID of the object whose cache should be invalidated
        """
        cache_key = cls._make_key(vote_model, object_id)
        cache.delete(cache_key)

    @classmethod
    def invalidate_for_instance(cls, vote_instance):
        """
        Clear the cached score using a vote instance.

        This is a convenience method for signal handlers.

        Args:
            vote_instance: The vote model instance
        """
        vote_model = type(vote_instance)
        object_id = vote_instance.object_id
        cls.invalidate(vote_model, object_id)

    @classmethod
    def set_timeout(cls, timeout):
        """
        Set the cache timeout.

        Args:
            timeout: Timeout in seconds
        """
        cls.CACHE_TIMEOUT = timeout

    @classmethod
    def warm_cache(cls, vote_model, object_ids):
        """
        Pre-populate cache for multiple objects.

        Useful for warming cache after deployment or for
        frequently accessed objects.

        Args:
            vote_model: The vote model class
            object_ids: List of object IDs to cache
        """
        for object_id in object_ids:
            cls.get_score(vote_model, object_id)


def invalidate_vote_cache(sender, **kwargs):
    """
    Signal handler to invalidate cache when a vote changes.

    This handler automatically clears the cached vote score for an object
    whenever a vote on that object is created, updated, or deleted.

    Args:
        sender: The Vote instance that was changed.
        **kwargs: Additional keyword arguments passed by the signal.
    """
    VoteCache.invalidate_for_instance(sender)
