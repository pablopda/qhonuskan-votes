import warnings
from django import template
from django.urls import reverse

register = template.Library()


def prefetch_vote_status(objects, user):
    """
    Prefetch vote status for multiple objects to avoid N+1 queries.

    Usage in views:
        from qhonuskan_votes.templatetags.qhonuskan_votes import prefetch_vote_status

        objects = MyModel.objects.all()
        prefetch_vote_status(objects, request.user)
        # Now each object has a _vote_status attribute

    Args:
        objects: A queryset or list of voteable objects
        user: The user to check votes for

    Returns:
        The objects with _vote_status attribute set on each
    """
    if not user.is_authenticated:
        for obj in objects:
            obj._vote_status = 0
        return objects

    # Get all object IDs
    object_ids = [obj.id for obj in objects]
    if not object_ids:
        return objects

    # Get the vote model from the first object
    first_obj = objects[0]
    votes_manager = first_obj.votes

    # Fetch all votes for these objects in a single query
    votes = votes_manager.model.objects.filter(
        object_id__in=object_ids,
        voter=user
    ).values('object_id', 'value')

    # Create a mapping of object_id -> vote_value
    vote_map = {v['object_id']: v['value'] for v in votes}

    # Set the _vote_status attribute on each object
    for obj in objects:
        obj._vote_status = vote_map.get(obj.id, 0)

    return objects


@register.simple_tag
def get_prefetched_vote_status(obj):
    """
    Get the vote status from a prefetched object.

    Usage in templates:
        {% get_prefetched_vote_status object as vote_status %}

    The object must have been processed by prefetch_vote_status() first.
    Falls back to 0 if not prefetched.
    """
    return getattr(obj, '_vote_status', 0)


@register.inclusion_tag('qhonuskan/voting_js.html')
def voting_script(user):
    return {"vote_url": reverse('qhonuskan_vote'),
            "handle_pending_vote": reverse('handle_pending_vote'),
            "user_is_authenticated": user.is_authenticated
            }




@register.simple_tag
def get_vote_status(object, user):
    """
    Performance wise tag, replaces is_up_voted_by and is_down_voted_by
    cutting the number of queries to half.
    """
    if not user.is_authenticated:
        return 0
    vote = object.votes.filter(voter=user).first()
    return vote.value if vote else 0


@register.filter
def is_up_voted_by(obj, user):
    """
    If user is up voted given object, it returns True.

    .. deprecated::
        Use get_vote_status tag instead to reduce database queries.
        This filter will be removed in a future version.
    """
    warnings.warn(
        "is_up_voted_by filter is deprecated. Use get_vote_status tag instead "
        "to reduce database queries. Example: {% get_vote_status object user as vote_status %}",
        DeprecationWarning,
        stacklevel=2
    )
    if user.is_authenticated:
        return obj.votes.filter(voter=user, value=1).exists()
    return False


@register.filter
def is_down_voted_by(obj, user):
    """
    If user is down voted given object, it returns True.

    .. deprecated::
        Use get_vote_status tag instead to reduce database queries.
        This filter will be removed in a future version.
    """
    warnings.warn(
        "is_down_voted_by filter is deprecated. Use get_vote_status tag instead "
        "to reduce database queries. Example: {% get_vote_status object user as vote_status %}",
        DeprecationWarning,
        stacklevel=2
    )
    if user.is_authenticated:
        return obj.votes.filter(voter=user, value=-1).exists()
    return False


@register.inclusion_tag('qhonuskan/vote_buttons.html')
def vote_buttons_for(obj, user):
    """
    Takes two parameters: the object the votes are for and the user.

    Usage::
        {% vote_buttons_for idea user %}
    """
    return {
        "object": obj,
        "vote_model": f"{obj._meta.app_label}.{obj._meta.object_name}Vote",
        "user": user
    }

