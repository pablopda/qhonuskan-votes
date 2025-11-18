"""
Utility functions and classes for the qhonuskan-votes voting system.

This module provides helper functions and database aggregation utilities
for working with votes and vote models.

Key Components:
    - get_vote_model: Retrieve a vote model class by its registered name
    - SumWithDefault: Custom SQL aggregate that handles NULL values
    - sum_with_default: Django ORM helper for summing with default values

Example Usage:
    Get a vote model by name::

        from qhonuskan_votes.utils import get_vote_model

        # Get the ArticleVote model
        ArticleVote = get_vote_model('myapp.ArticleVote')

        # Query all votes
        votes = ArticleVote.objects.all()

    Use sum_with_default in annotations::

        from qhonuskan_votes.utils import sum_with_default
        from myapp.models import Article

        # Get articles with their vote scores (0 for no votes)
        articles = Article.objects.annotate(
            score=sum_with_default('articlevote__value')
        )
"""

from typing import Any, Type, Union

from django.db import models
from django.db.models import Sum, aggregates
from django.db.models.functions import Coalesce
from django.db.models.expressions import Combinable

from qhonuskan_votes.models import _vote_models
from qhonuskan_votes.exceptions import InvalidVoteModel


def get_vote_model(model_name: str) -> Type[models.Model]:
    """
    Retrieve a vote model class by its registered name.

    Vote models are automatically registered when a model with a VotesField
    is loaded. This function allows you to retrieve the vote model class
    by its fully qualified name.

    Args:
        model_name (str): The fully qualified name of the vote model.
            Format: 'app_label.ModelNameVote' (e.g., 'myapp.ArticleVote').

    Returns:
        Type[models.Model]: The vote model class corresponding to the given name.

    Raises:
        InvalidVoteModel: If no vote model exists with the given name.
            This typically means either:
            - The model name is misspelled
            - The parent model doesn't have a VotesField
            - The app containing the model hasn't been loaded yet

    Example:
        Basic usage::

            from qhonuskan_votes.utils import get_vote_model

            # Get the vote model for Article
            ArticleVote = get_vote_model('myapp.ArticleVote')

            # Create a vote
            ArticleVote.objects.create(
                object_id=123,
                voter=user,
                value=1
            )

        Error handling::

            from qhonuskan_votes.utils import get_vote_model
            from qhonuskan_votes.exceptions import InvalidVoteModel

            try:
                VoteModel = get_vote_model(user_input)
            except InvalidVoteModel:
                return HttpResponseBadRequest("Invalid vote model")

    Note:
        The model name must match exactly, including case.
        Use Model.votes.model.get_model_name() to get the correct name.
    """
    if model_name in _vote_models:
        return _vote_models[model_name]
    else:
        raise InvalidVoteModel('No such vote model "%s"' % model_name)


class SumWithDefault(aggregates.Sum):
    """
    Custom Sum aggregate that returns a default value instead of NULL for empty sets.

    This aggregate extends Django's Sum to wrap results in COALESCE, ensuring
    a numeric value is always returned even when there are no matching rows.

    This is particularly useful for vote scores where an object with no votes
    should have a score of 0 rather than NULL.

    Attributes:
        name (str): The aggregate function name ('SumWithDefault').
        template (str): The SQL template using COALESCE.

    Example:
        Use in an annotation::

            from django.db.models import aggregates
            from myapp.models import Article

            # The aggregate is registered on the aggregates module
            articles = Article.objects.annotate(
                score=aggregates.SumWithDefault('articlevote__value', default=0)
            )

    Note:
        For Django 3.2+, prefer using the sum_with_default() function
        which provides a cleaner API using Coalesce.

    Warning:
        This class modifies the aggregates module by registering itself.
        This is done automatically when this module is imported.
    """
    name: str = 'SumWithDefault'
    template: str = 'COALESCE(%(function)s(%(field)s), %(default)s)'


# Register the SumWithDefault aggregation
setattr(aggregates, 'SumWithDefault', SumWithDefault)


def sum_with_default(
    field: Union[str, Combinable],
    default: int = 0
) -> Coalesce:
    """
    Create a Sum aggregate with a default value for NULL results.

    This is the recommended way to sum vote values in Django 3.2+.
    It wraps Sum in Coalesce to ensure a numeric value is always returned.

    Args:
        field (Union[str, Combinable]): The field name or expression to sum.
            Can be a string field name (e.g., 'articlevote__value') or
            a Django expression object.
        default (int): The default value to return if the sum is NULL.
            Defaults to 0. This is returned when there are no matching rows.

    Returns:
        Coalesce: A Coalesce expression wrapping the Sum aggregate.
            Can be used directly in annotate() or aggregate() calls.

    Example:
        Basic usage with field name::

            from qhonuskan_votes.utils import sum_with_default
            from myapp.models import Article

            # Get articles with their vote scores
            articles = Article.objects.annotate(
                score=sum_with_default('articlevote__value')
            )

            for article in articles:
                print(f"{article.title}: {article.score}")

        With custom default value::

            # Use -1 as default for objects with no votes
            articles = Article.objects.annotate(
                score=sum_with_default('articlevote__value', default=-1)
            )

        In aggregate queries::

            from django.db.models import F

            # Get total votes across all articles
            total = Article.objects.aggregate(
                total_score=sum_with_default('articlevote__value')
            )
            print(f"Total score: {total['total_score']}")

        With expressions::

            from django.db.models import F, Case, When, Value

            # Conditional sum
            articles = Article.objects.annotate(
                upvotes=sum_with_default(
                    Case(
                        When(articlevote__value=1, then=Value(1)),
                        default=Value(0)
                    )
                )
            )

    Note:
        This function is preferred over SumWithDefault for new code
        as it uses Django's built-in Coalesce function.
    """
    return Coalesce(Sum(field), default)
