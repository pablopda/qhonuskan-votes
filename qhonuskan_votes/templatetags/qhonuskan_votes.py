from django import template
from django.urls import reverse
from django.utils.html import mark_safe

from qhonuskan_votes.views import handle_pending_vote

register = template.Library()


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
def is_up_voted_by(object, user):
    """
    If user is up voted given object, it returns True.
    """
    if user.is_authenticated:
        return object.votes.filter(voter=user, value=1).exists()
    return False


@register.filter
def is_down_voted_by(object, user):
    """
    If user is down voted given object, it returns True.
    """
    if user.is_authenticated:
        return object.votes.filter(voter=user, value=-1).exists()
    return False


@register.simple_tag
def vote_buttons_for(obj, user, template_name='qhonuskan/vote_buttons.html'):
    """
    Takes two parameters. The first is the object the votes are for. And the second is
    the template to use. By default it uses vote_buttons.html.

    Usage::
        {% vote_buttons_for idea %}
        {% vote_buttons_for idea "app/follow_form.html" %}
    """
    t = template.loader.get_template(template_name)
    context = {
        "object": obj,
        "vote_model": f"{obj._meta.app_label}.{obj._meta.object_name}Vote",
        "user": user
    }
    return mark_safe(t.render(context))

