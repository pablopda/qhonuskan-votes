"""
Django models for the qhonuskan-votes voting system.

This module provides the core data models and managers for implementing
a flexible voting system in Django applications. It uses a descriptor pattern
to dynamically create vote models for any Django model that includes a VotesField.

Key Components:
    - VotesField: A descriptor that creates vote models for any Django model
    - ObjectsWithScoresManager: Manager that annotates objects with their vote scores
    - SortByScoresManager: Manager that orders objects by their vote scores
    - vote_changed: Signal emitted when votes are created, updated, or deleted

Example Usage:
    Define a model with voting capability::

        from django.db import models
        from qhonuskan_votes.models import VotesField

        class Article(models.Model):
            title = models.CharField(max_length=200)
            content = models.TextField()
            votes = VotesField()

    This automatically creates an ArticleVote model that tracks votes on articles.

    Query objects with scores::

        from myapp.models import Article

        # Get all articles with their vote scores
        articles = Article.objects.all()
        for article in articles:
            print(f"{article.title}: {article.votes.aggregate_score()}")

Signals:
    vote_changed: Emitted whenever a vote is created, updated, or deleted.
        Sender is the Vote instance. Used for cache invalidation.

Module Attributes:
    _vote_models (dict): Registry of all dynamically created vote models.
        Maps model names (e.g., 'app.ArticleVote') to their classes.
"""

from typing import Any, Dict, Type

from django.db import models
from django.db.models.base import ModelBase
from django.db.models.query import QuerySet
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db.models import Sum
from django.db.models.functions import Coalesce

# Import signals from the centralized signals module
from qhonuskan_votes.signals import vote_changed, pre_vote, post_vote

_vote_models: Dict[str, Type[models.Model]] = {}
"""
Registry of all dynamically created vote models.

This dictionary maps fully qualified model names (e.g., 'myapp.ArticleVote')
to their corresponding vote model classes. It is populated automatically
when VotesField creates vote models during Django model initialization.

Type:
    dict[str, type]: Mapping of model names to vote model classes.
"""

# Managers --------------------------------------------------------------------


class ObjectsWithScoresManager(models.Manager[Any]):
    """
    Custom manager that annotates objects with their aggregate vote scores.

    This manager adds a 'vote_score' annotation to each object in the queryset,
    representing the sum of all vote values for that object. Objects with no
    votes will have a vote_score of 0.

    The manager automatically determines the correct vote model name based on
    the model it's attached to.

    Example:
        Add the manager to your model::

            class Article(models.Model):
                title = models.CharField(max_length=200)
                votes = VotesField()

                # Add the manager
                objects_with_scores = ObjectsWithScoresManager()

        Query objects with scores::

            # Get all articles with their vote scores
            articles = Article.objects_with_scores.all()
            for article in articles:
                print(f"{article.title}: {article.vote_score}")

            # Filter by score
            popular = Article.objects_with_scores.filter(vote_score__gte=10)

    Note:
        The vote_score annotation is computed using database aggregation,
        which is efficient but may not reflect recent cache invalidations
        until the query is re-executed.
    """

    def get_queryset(self) -> QuerySet[Any]:
        """
        Return a queryset with vote_score annotation.

        Returns:
            QuerySet: A queryset where each object has a 'vote_score' attribute
                containing the sum of all vote values for that object.
        """
        return super().get_queryset().annotate(
            vote_score=Coalesce(Sum(f'{self.model._meta.model_name}vote__value'), 0)
        )


class SortByScoresManager(models.Manager[Any]):
    """
    Custom manager that returns objects sorted by their vote scores (descending).

    This manager extends ObjectsWithScoresManager by also ordering the results
    by vote_score in descending order, making it easy to get the most popular
    items first.

    Example:
        Add the manager to your model::

            class Article(models.Model):
                title = models.CharField(max_length=200)
                votes = VotesField()

                # Add the manager
                sorted_by_score = SortByScoresManager()

        Query objects sorted by score::

            # Get articles sorted by popularity (highest score first)
            popular_articles = Article.sorted_by_score.all()

            # Get top 10 most popular articles
            top_10 = Article.sorted_by_score.all()[:10]

    Note:
        Objects with the same score are returned in their natural order
        (typically by primary key). To add secondary ordering, chain
        .order_by() after querying.
    """

    def get_queryset(self) -> QuerySet[Any]:
        """
        Return a queryset with vote_score annotation, ordered by score descending.

        Returns:
            QuerySet: A queryset where each object has a 'vote_score' attribute,
                ordered from highest to lowest score.
        """
        return super().get_queryset().annotate(
            vote_score=Coalesce(Sum(f'{self.model._meta.model_name}vote__value'), 0)
        ).order_by('-vote_score')


# Fields ----------------------------------------------------------------------


class VotesField:
    """
    Descriptor field that adds voting capability to any Django model.

    When added to a model, VotesField automatically creates a related Vote model
    that stores individual votes from users. The Vote model is dynamically named
    based on the parent model (e.g., Article -> ArticleVote).

    The field provides access to the Vote model's manager, allowing you to query
    votes on both model instances and the model class itself.

    Attributes:
        _name (str): The attribute name assigned to this field on the model.

    Example:
        Define a model with voting::

            from django.db import models
            from qhonuskan_votes.models import VotesField

            class Article(models.Model):
                title = models.CharField(max_length=200)
                content = models.TextField()
                votes = VotesField()

        Access votes on an instance::

            article = Article.objects.get(pk=1)

            # Get all votes for this article
            all_votes = article.votes.all()

            # Get vote count
            vote_count = article.votes.count()

        Access the Vote model class::

            # Get the Vote model for bulk operations
            ArticleVote = Article.votes

            # Query all votes
            all_article_votes = ArticleVote.all()

            # Get votes by a specific user
            user_votes = ArticleVote.filter(voter=user)

    Note:
        Each VotesField creates a unique database table for storing votes,
        named after the parent model (e.g., 'myapp_articlevote').
    """

    def __init__(self):
        """
        Initialize a new VotesField.

        No parameters are required. The field configures itself when
        Django processes the model class.
        """
        pass

    def contribute_to_class(self, cls, name):
        """
        Django hook called when the field is added to a model class.

        This method creates the Vote model and sets up the descriptor
        on the model class.

        Args:
            cls (type): The model class this field is being added to.
            name (str): The attribute name for this field on the model.

        Note:
            This method is called automatically by Django's model metaclass
            during model class creation. You should not call it directly.
        """
        self._name = name

        descriptor = self._create_Vote_model(cls)
        setattr(cls, self._name, descriptor)

    def _create_Vote_model(self, model):
        """
        Create a Vote model class for the given parent model.

        This method dynamically creates a Vote model with:
        - A foreign key to the voter (user)
        - A foreign key to the voted object
        - A value field for the vote (1 for upvote, -1 for downvote)
        - A timestamp for when the vote was cast

        Args:
            model (type): The parent model class to create votes for.

        Returns:
            VoteFieldDescriptor: A descriptor that provides access to the
                Vote model's manager.

        Note:
            The created Vote model is automatically registered in the
            _vote_models dictionary for later retrieval.
        """
        class VoteMeta(ModelBase):
            """
            Metaclass that gives each Vote model a unique name and table.

            This metaclass renames the Vote class to include the parent model's
            name (e.g., 'ArticleVote') and registers it in the _vote_models
            dictionary.
            """

            def __new__(c, name, bases, attrs):
                """
                Create a new Vote model class with a unique name.

                Args:
                    c: The metaclass.
                    name (str): The original class name ('Vote').
                    bases (tuple): Base classes.
                    attrs (dict): Class attributes.

                Returns:
                    type: The new Vote model class with a unique name.
                """
                # Rename class
                name = '%sVote' % model._meta.object_name

                # This attribute is required for a model to function
                # properly in Django.
                attrs['__module__'] = model.__module__

                vote_model = ModelBase.__new__(c, name, bases, attrs)

                _vote_models[vote_model.get_model_name()] = vote_model

                return vote_model

        class Vote(models.Model, metaclass=VoteMeta):
            """
            Dynamic Vote model for storing user votes on objects.

            This model is created dynamically for each model that uses VotesField.
            It stores individual votes with the voter, value, and timestamp.

            Attributes:
                voter (ForeignKey): The user who cast this vote.
                value (int): The vote value (1 for upvote, -1 for downvote).
                date (datetime): When the vote was cast (auto-set on creation).
                object (ForeignKey): The object being voted on.

            Meta:
                ordering: Ordered by date (oldest first).
                unique_together: Each user can only vote once per object.
                indexes: Optimized for querying by object and object+value.
            """

            voter = models.ForeignKey(
                settings.AUTH_USER_MODEL, verbose_name=_('voter'),
                on_delete=models.CASCADE)

            value = models.IntegerField(
                default=1,
                verbose_name=_('value'))

            date = models.DateTimeField(
                auto_now_add=True,
                db_index=True,
                verbose_name=_('voted on'))

            object = models.ForeignKey(
                model, verbose_name=_('object'), on_delete=models.CASCADE)

            class Meta:
                ordering = ('date',)
                verbose_name = _('Vote')
                verbose_name_plural = _('Votes')
                unique_together = ('voter', 'object')
                indexes = [
                    models.Index(fields=['object']),
                    models.Index(fields=['object', 'value']),
                ]

            def save(self, *args, **kwargs):
                """
                Save the vote and emit signals for the operation.

                Signals emitted:
                - pre_vote: Before the save operation
                - vote_changed: After save, for cache invalidation
                - post_vote: After save completes successfully

                Args:
                    *args: Variable length argument list passed to parent save().
                    **kwargs: Arbitrary keyword arguments passed to parent save().

                Note:
                    Signals are used for cache invalidation and other
                    post-vote processing.
                """
                orig_vote = None if not self.pk else Vote.objects.get(
                    pk=self.pk)
                is_create = not self.pk
                action = 'create' if is_create else 'update'

                # Send pre_vote signal
                pre_vote.send(sender=Vote, instance=self, action=action)

                super(Vote, self).save(*args, **kwargs)

                if is_create:
                    # On create trigger signals
                    vote_changed.send(sender=self)
                    post_vote.send(sender=Vote, instance=self, action='create', created=True)
                elif orig_vote and orig_vote.value != self.value:
                    # On update only trigger signals if value changed
                    vote_changed.send(sender=self)
                    post_vote.send(sender=Vote, instance=self, action='update', created=False)

            def delete(self, *args, **kwargs):
                """
                Delete the vote and emit signals for the operation.

                Signals emitted:
                - pre_vote: Before the delete operation
                - vote_changed: After delete, for cache invalidation
                - post_vote: After delete completes successfully

                Args:
                    *args: Variable length argument list passed to parent delete().
                    **kwargs: Arbitrary keyword arguments passed to parent delete().

                Note:
                    Signals are always emitted on deletion for cache invalidation.
                """
                # Send pre_vote signal before deletion
                pre_vote.send(sender=Vote, instance=self, action='delete')

                super(Vote, self).delete(*args, **kwargs)

                # Send signals after deletion
                vote_changed.send(sender=self)
                post_vote.send(sender=Vote, instance=self, action='delete', created=False)

            def __str__(self) -> str:
                """
                Return a human-readable string representation of the vote.

                Returns:
                    str: A string like "username likes Article" or "username hates Article".
                """
                values = {
                    'voter': self.voter.username,
                    'like': _('likes') if self.value > 0 else _('hates'),
                    'object': self.object}

                return "%(voter)s %(like)s %(object)s" % values

            @classmethod
            def get_model_name(cls):
                """
                Get the fully qualified name of this Vote model.

                Returns:
                    str: The model name in 'app_label.ModelName' format
                        (e.g., 'myapp.ArticleVote').

                Example:
                    >>> ArticleVote.get_model_name()
                    'myapp.ArticleVote'
                """
                return '%s.%s' % (cls._meta.app_label, cls._meta.object_name)

        class VoteFieldDescriptor:
            """
            Descriptor that provides access to the Vote model's manager.

            When accessed on a model instance, returns the related manager
            for that instance's votes. When accessed on the model class,
            returns the Vote model's default manager.
            """

            def __init__(self):
                """Initialize the descriptor."""
                pass

            def __get__(self, obj, objtype):
                """
                Return the appropriate manager based on access context.

                Args:
                    obj: The model instance (None if accessed on class).
                    objtype: The model class.

                Returns:
                    Manager: If obj is not None, returns the related manager
                        for that instance's votes. Otherwise, returns the
                        Vote model's default manager.

                Example:
                    On instance (returns related manager)::

                        article = Article.objects.get(pk=1)
                        votes = article.votes.all()  # Votes for this article

                    On class (returns Vote model manager)::

                        all_votes = Article.votes.all()  # All article votes
                """
                if obj:
                    return getattr(obj,
                        ('%svote_set' % model._meta.object_name).lower())
                else:
                    return Vote.objects

        return VoteFieldDescriptor()
