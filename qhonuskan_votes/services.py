# services.py
"""
Service layer for voting business logic.

This module provides a clean separation between HTTP concerns (views)
and business logic (services), making the code more testable, reusable,
and maintainable.
"""

from typing import Optional, Tuple

from django.db import transaction
from django.db.models import Model

from qhonuskan_votes.utils import sum_with_default
from qhonuskan_votes.cache import VoteCache
from qhonuskan_votes.logutils import setup_loghandlers

logger = setup_loghandlers()


class VoteService:
    """
    Service class for handling vote operations.

    This service encapsulates all business logic related to voting,
    providing a clean API for creating, updating, and querying votes.
    """

    @staticmethod
    def create_or_update_vote(
        vote_model: type,
        user,
        object_id: int,
        value: int
    ) -> Tuple[int, int]:
        """
        Create or update a vote for a given object by a user.

        Implements toggle behavior:
        - If the user votes the same way twice, the vote is removed
        - If the user changes their vote, the vote is updated
        - If no vote exists, a new vote is created

        Args:
            vote_model: The vote model class (e.g., ArticleVote)
            user: The user casting the vote
            object_id: The ID of the object being voted on
            value: The vote value (1 for upvote, -1 for downvote)

        Returns:
            Tuple of (voted_as, score):
                - voted_as: The resulting vote value (0 if vote was removed)
                - score: The new total score for the object
        """
        with transaction.atomic():
            vote_instances = vote_model.objects.filter(
                object_id=object_id,
                voter=user
            )

            if vote_instances.exists():
                vote_instance = vote_instances.first()
                if vote_instance.value == value:
                    # Delete all votes if the user voted the same way (toggle off)
                    vote_instances.delete()
                    voted_as = 0
                    logger.debug(
                        'Vote toggled off: user_id=%s, model=%s, object_id=%s, '
                        'previous_value=%s',
                        user.id,
                        vote_model.__name__,
                        object_id,
                        value
                    )
                else:
                    # If the user changes their vote, update the first and delete others
                    previous_value = vote_instance.value
                    vote_instance.value = value
                    vote_instance.save()
                    vote_instances.exclude(pk=vote_instance.pk).delete()
                    voted_as = value
                    logger.debug(
                        'Vote changed: user_id=%s, model=%s, object_id=%s, '
                        'previous_value=%s, new_value=%s',
                        user.id,
                        vote_model.__name__,
                        object_id,
                        previous_value,
                        value
                    )
            else:
                # Create a new vote if it doesn't exist
                vote_model.objects.create(
                    object_id=object_id,
                    voter=user,
                    value=value
                )
                voted_as = value
                logger.debug(
                    'New vote created: user_id=%s, model=%s, object_id=%s, value=%s',
                    user.id,
                    vote_model.__name__,
                    object_id,
                    value
                )

        # Calculate and return the new score
        score = VoteService.get_score(vote_model, object_id)

        return voted_as, score

    @staticmethod
    def get_score(vote_model: type, object_id: int) -> int:
        """
        Get the total score for an object.

        Uses VoteCache for improved performance. The cache is automatically
        invalidated when votes change via the vote_changed signal.

        Args:
            vote_model: The vote model class
            object_id: The ID of the object

        Returns:
            The sum of all vote values for the object (defaults to 0)
        """
        return VoteCache.get_score(vote_model, object_id)

    @staticmethod
    def get_user_vote(
        vote_model: type,
        user,
        object_id: int
    ) -> Optional[int]:
        """
        Get the current vote value for a user on an object.

        Args:
            vote_model: The vote model class
            user: The user whose vote to retrieve
            object_id: The ID of the object

        Returns:
            The vote value (1, -1) if the user has voted, None otherwise
        """
        if not user or not user.is_authenticated:
            return None

        try:
            vote = vote_model.objects.get(
                object_id=object_id,
                voter=user
            )
            return vote.value
        except vote_model.DoesNotExist:
            return None

    @staticmethod
    def delete_vote(vote_model: type, user, object_id: int) -> bool:
        """
        Delete a user's vote on an object.

        Args:
            vote_model: The vote model class
            user: The user whose vote to delete
            object_id: The ID of the object

        Returns:
            True if a vote was deleted, False otherwise
        """
        deleted_count, _ = vote_model.objects.filter(
            object_id=object_id,
            voter=user
        ).delete()

        if deleted_count > 0:
            logger.info(
                'Vote deleted: user_id=%s, model=%s, object_id=%s, count=%s',
                user.id,
                vote_model.__name__,
                object_id,
                deleted_count
            )
        else:
            logger.debug(
                'No vote to delete: user_id=%s, model=%s, object_id=%s',
                user.id,
                vote_model.__name__,
                object_id
            )

        return deleted_count > 0

    @staticmethod
    def has_voted(vote_model: type, user, object_id: int) -> bool:
        """
        Check if a user has voted on an object.

        Args:
            vote_model: The vote model class
            user: The user to check
            object_id: The ID of the object

        Returns:
            True if the user has voted, False otherwise
        """
        if not user or not user.is_authenticated:
            return False

        return vote_model.objects.filter(
            object_id=object_id,
            voter=user
        ).exists()
