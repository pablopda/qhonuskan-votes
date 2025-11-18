import logging

from django.db import models
from qhonuskan_votes.models import VotesField, ObjectsWithScoresManager
from qhonuskan_votes.models import vote_changed

logger = logging.getLogger('qhonuskan_votes')


class ThreadModel(models.Model):
    """
    An example model for voting.
    """
    text = models.TextField()
    votes = VotesField()

    objects = models.Manager()
    objects_with_scores = ObjectsWithScoresManager()


def my_callback(sender, **kwargs):
    # sender is the vote instance, not the class
    logger.info(
        'vote_changed signal fired: sender=%s, instance_id=%s, voter_id=%s, value=%s',
        sender.__class__.__name__ if sender else 'Unknown',
        sender.id if sender else None,
        sender.voter_id if sender and hasattr(sender, 'voter_id') else None,
        sender.value if sender and hasattr(sender, 'value') else None
    )


vote_changed.connect(my_callback, dispatch_uid="vote_changed")
