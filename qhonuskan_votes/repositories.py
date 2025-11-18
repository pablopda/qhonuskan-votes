# repositories.py
"""
Repository pattern for data access abstraction.

This module provides a repository pattern implementation for vote data access,
encapsulating all database operations and making testing easier through
dependency injection and mocking.
"""

from typing import Optional, Tuple, Type, Any
from django.db import models, transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.contrib.auth import get_user_model

from qhonuskan_votes.logutils import setup_loghandlers

logger = setup_loghandlers()

User = get_user_model()


class VoteRepository:
    """
    Repository for Vote model operations.

    This class encapsulates all database operations related to votes,
    providing a clean interface for data access and making it easier
    to test code that depends on vote operations.

    Usage:
        from qhonuskan_votes.repositories import VoteRepository
        from qhonuskan_votes.utils import get_vote_model

        # Get the vote model for your content type
        vote_model = get_vote_model('myapp.ArticleVote')

        # Create repository instance
        repo = VoteRepository(vote_model)

        # Use repository methods
        vote = repo.get_user_vote(user, object_id)
        score = repo.get_score(object_id)
    """

    def __init__(self, vote_model: Type[models.Model]):
        """
        Initialize the repository with a vote model.

        Args:
            vote_model: The Vote model class to use for database operations.
                       This is typically obtained via get_vote_model().
        """
        self._model = vote_model

    @property
    def model(self) -> Type[models.Model]:
        """Return the underlying vote model."""
        return self._model

    def get_user_vote(self, user: Any, object_id: int) -> Optional[models.Model]:
        """
        Get a user's vote for a specific object.

        Args:
            user: The user who cast the vote.
            object_id: The ID of the object being voted on.

        Returns:
            The Vote instance if found, None otherwise.
        """
        try:
            return self._model.objects.get(
                voter=user,
                object_id=object_id
            )
        except self._model.DoesNotExist:
            return None

    def get_user_votes(self, user: Any, object_id: int) -> models.QuerySet:
        """
        Get all votes by a user for a specific object.

        This handles the edge case where multiple votes might exist
        due to race conditions or legacy data.

        Args:
            user: The user who cast the votes.
            object_id: The ID of the object being voted on.

        Returns:
            QuerySet of Vote instances.
        """
        return self._model.objects.filter(
            voter=user,
            object_id=object_id
        )

    def get_score(self, object_id: int) -> int:
        """
        Get the total vote score for an object.

        Args:
            object_id: The ID of the object to get the score for.

        Returns:
            The sum of all vote values for the object (can be negative).
        """
        result = self._model.objects.filter(
            object_id=object_id
        ).aggregate(
            score=Coalesce(Sum('value'), 0)
        )
        return result['score']

    def create_vote(self, user: Any, object_id: int, value: int) -> models.Model:
        """
        Create a new vote.

        Args:
            user: The user casting the vote.
            object_id: The ID of the object being voted on.
            value: The vote value (typically 1 for upvote, -1 for downvote).

        Returns:
            The created Vote instance.

        Raises:
            IntegrityError: If a vote already exists for this user and object.
        """
        return self._model.objects.create(
            voter=user,
            object_id=object_id,
            value=value
        )

    def update_vote(self, vote: models.Model, value: int) -> models.Model:
        """
        Update an existing vote's value.

        Args:
            vote: The Vote instance to update.
            value: The new vote value.

        Returns:
            The updated Vote instance.
        """
        vote.value = value
        vote.save()
        return vote

    def delete_votes(self, user: Any, object_id: int) -> int:
        """
        Delete all votes by a user for a specific object.

        Args:
            user: The user whose votes should be deleted.
            object_id: The ID of the object.

        Returns:
            The number of votes deleted.
        """
        deleted_count, _ = self._model.objects.filter(
            voter=user,
            object_id=object_id
        ).delete()
        return deleted_count

    def delete_vote(self, vote: models.Model) -> None:
        """
        Delete a specific vote instance.

        Args:
            vote: The Vote instance to delete.
        """
        vote.delete()

    def get_or_create_vote(
        self,
        user: Any,
        object_id: int,
        value: int
    ) -> Tuple[models.Model, bool]:
        """
        Get an existing vote or create a new one.

        Args:
            user: The user casting the vote.
            object_id: The ID of the object being voted on.
            value: The vote value to use if creating a new vote.

        Returns:
            A tuple of (vote_instance, created) where created is True
            if a new vote was created, False if an existing one was returned.
        """
        return self._model.objects.get_or_create(
            voter=user,
            object_id=object_id,
            defaults={'value': value}
        )

    def vote_exists(self, user: Any, object_id: int) -> bool:
        """
        Check if a user has voted on an object.

        Args:
            user: The user to check.
            object_id: The ID of the object.

        Returns:
            True if the user has voted, False otherwise.
        """
        return self._model.objects.filter(
            voter=user,
            object_id=object_id
        ).exists()

    def get_all_votes_for_object(self, object_id: int) -> models.QuerySet:
        """
        Get all votes for a specific object.

        Args:
            object_id: The ID of the object.

        Returns:
            QuerySet of all Vote instances for the object.
        """
        return self._model.objects.filter(object_id=object_id)

    def get_vote_counts(self, object_id: int) -> dict:
        """
        Get the count of upvotes and downvotes for an object.

        Args:
            object_id: The ID of the object.

        Returns:
            Dictionary with 'upvotes', 'downvotes', and 'total' counts.
        """
        votes = self._model.objects.filter(object_id=object_id)
        upvotes = votes.filter(value__gt=0).count()
        downvotes = votes.filter(value__lt=0).count()

        return {
            'upvotes': upvotes,
            'downvotes': downvotes,
            'total': upvotes + downvotes,
            'score': upvotes - downvotes
        }

    @transaction.atomic
    def toggle_vote(
        self,
        user: Any,
        object_id: int,
        value: int
    ) -> Tuple[int, int]:
        """
        Toggle a user's vote on an object.

        If the user hasn't voted, creates a new vote with the given value.
        If the user voted the same way, deletes all their votes.
        If the user voted differently, updates to the new value.

        This encapsulates the voting logic from views.py.

        Args:
            user: The user casting the vote.
            object_id: The ID of the object being voted on.
            value: The vote value (1 for upvote, -1 for downvote).

        Returns:
            A tuple of (voted_as, new_score) where voted_as is the
            final vote value (0 if vote was removed).
        """
        vote_instances = self.get_user_votes(user, object_id)

        if vote_instances.exists():
            vote_instance = vote_instances.first()
            if vote_instance.value == value:
                # Delete all votes if the user voted the same way
                vote_instances.delete()
                voted_as = 0
                logger.debug(
                    'Repository toggle_vote: vote removed - user_id=%s, '
                    'object_id=%s, model=%s',
                    user.id,
                    object_id,
                    self._model.__name__
                )
            else:
                # Update the first vote and delete any others
                previous_value = vote_instance.value
                vote_instance.value = value
                vote_instance.save()
                vote_instances.exclude(pk=vote_instance.pk).delete()
                voted_as = value
                logger.debug(
                    'Repository toggle_vote: vote updated - user_id=%s, '
                    'object_id=%s, model=%s, from=%s, to=%s',
                    user.id,
                    object_id,
                    self._model.__name__,
                    previous_value,
                    value
                )
        else:
            # Create a new vote
            self.create_vote(user, object_id, value)
            voted_as = value
            logger.debug(
                'Repository toggle_vote: new vote - user_id=%s, '
                'object_id=%s, model=%s, value=%s',
                user.id,
                object_id,
                self._model.__name__,
                value
            )

        new_score = self.get_score(object_id)
        return voted_as, new_score


class VoteRepositoryFactory:
    """
    Factory for creating VoteRepository instances.

    This factory provides a convenient way to create repositories
    for different vote models and can be useful for dependency injection.

    Usage:
        factory = VoteRepositoryFactory()
        repo = factory.create('myapp.ArticleVote')
    """

    def __init__(self):
        """Initialize the factory."""
        from qhonuskan_votes.models import _vote_models
        self._vote_models = _vote_models

    def create(self, model_name: str) -> VoteRepository:
        """
        Create a VoteRepository for the specified model.

        Args:
            model_name: The name of the vote model (e.g., 'myapp.ArticleVote').

        Returns:
            A VoteRepository instance for the specified model.

        Raises:
            InvalidVoteModel: If the model name is not found.
        """
        from qhonuskan_votes.exceptions import InvalidVoteModel

        if model_name not in self._vote_models:
            logger.warning(
                'Invalid vote model requested: model_name=%s, available_models=%s',
                model_name,
                list(self._vote_models.keys())
            )
            raise InvalidVoteModel(f'No such vote model "{model_name}"')

        logger.debug(
            'VoteRepository created for model: %s',
            model_name
        )
        return VoteRepository(self._vote_models[model_name])

    def get_available_models(self) -> list:
        """
        Get a list of available vote model names.

        Returns:
            List of registered vote model names.
        """
        return list(self._vote_models.keys())
