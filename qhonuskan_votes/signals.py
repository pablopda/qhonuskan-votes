"""
Signal definitions and handlers for the qhonuskan-votes application.

This module centralizes all signal definitions and their handlers following
Django best practices for signal organization.

Signals:
    vote_changed: Emitted when a vote is created, updated, or deleted.
    pre_vote: Emitted before a vote operation (create/update/delete).
    post_vote: Emitted after a vote operation completes successfully.

Example Usage:
    Connect a custom handler to vote signals::

        from qhonuskan_votes.signals import vote_changed, pre_vote, post_vote

        @receiver(vote_changed)
        def my_vote_handler(sender, **kwargs):
            print(f"Vote changed: {sender}")

        @receiver(pre_vote)
        def before_vote(sender, instance, action, **kwargs):
            print(f"About to {action} vote: {instance}")

        @receiver(post_vote)
        def after_vote(sender, instance, action, **kwargs):
            print(f"Completed {action} vote: {instance}")
"""

from django.dispatch import Signal, receiver

# Signal definitions --------------------------------------------------------

vote_changed = Signal()
"""
Signal emitted when a vote is created, updated, or deleted.

This signal is used for cache invalidation and can be connected to
custom handlers for additional processing when votes change.

Arguments sent with this signal:
    sender: The Vote model instance that was changed.

Example:
    Connect a custom handler::

        from qhonuskan_votes.signals import vote_changed

        def my_vote_handler(sender, **kwargs):
            print(f"Vote changed: {sender}")

        vote_changed.connect(my_vote_handler)
"""

pre_vote = Signal()
"""
Signal emitted before a vote operation is performed.

This signal allows for validation, logging, or modification of vote
operations before they are committed to the database.

Arguments sent with this signal:
    sender: The Vote model class.
    instance: The Vote instance being operated on.
    action: String indicating the action ('create', 'update', or 'delete').

Example:
    Validate votes before they are saved::

        from qhonuskan_votes.signals import pre_vote

        @receiver(pre_vote)
        def validate_vote(sender, instance, action, **kwargs):
            if action == 'create' and not instance.voter.is_active:
                raise ValidationError("Inactive users cannot vote")
"""

post_vote = Signal()
"""
Signal emitted after a vote operation completes successfully.

This signal is useful for triggering side effects after a vote has been
successfully saved or deleted, such as updating analytics or sending
notifications.

Arguments sent with this signal:
    sender: The Vote model class.
    instance: The Vote instance that was operated on.
    action: String indicating the action ('create', 'update', or 'delete').
    created: Boolean indicating if this was a new vote (for create/update).

Example:
    Send notification after a vote::

        from qhonuskan_votes.signals import post_vote

        @receiver(post_vote)
        def notify_vote(sender, instance, action, **kwargs):
            if action == 'create':
                notify_author(instance.object, instance.voter)
"""

# Signal handlers -----------------------------------------------------------

@receiver(vote_changed)
def invalidate_vote_cache(sender, **kwargs):
    """
    Signal handler to invalidate cache when a vote changes.

    This handler automatically clears the cached vote score for an object
    whenever a vote on that object is created, updated, or deleted.

    Args:
        sender: The Vote instance that was changed.
        **kwargs: Additional keyword arguments passed by the signal.
    """
    from qhonuskan_votes.cache import VoteCache
    VoteCache.invalidate_for_instance(sender)
