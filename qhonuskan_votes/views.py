import json
from django.http import (
    HttpResponse, HttpResponseRedirect, HttpResponseForbidden,
    HttpResponseBadRequest, JsonResponse)
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db import transaction

from qhonuskan_votes.utils import get_vote_model, sum_with_default
from qhonuskan_votes.exceptions import InvalidVoteModel
from qhonuskan_votes.logutils import setup_loghandlers


logger = setup_loghandlers()


def _api_view(func):
    """
    Extracts model information from the POST dictionary and gets the vote model
    from them.
    """

    def view(request):
        if not request.user.is_authenticated:
            return HttpResponse(status=401)
        if not request.method == 'POST':
            return HttpResponseForbidden()
        model_name = request.POST.get('vote_model', None)
        object_id = request.POST.get('object_id', None)
        value = request.POST.get('value', None)
        # If any value is missing..
        if not all([model_name, object_id, value]):
            return HttpResponseBadRequest()
        try:
            value = int(value)
            object_id = int(object_id)
        except ValueError:
            return HttpResponseBadRequest()
        # You can only vote upwards or downwards
        if value not in (1, -1):
            return HttpResponseBadRequest()
        try:
            model = get_vote_model(model_name)
        except InvalidVoteModel as e:
            logger.warning(
                'Qhonuskan_votes received an unexpected value for vote_model '
                '"%s"' % model_name)
            return HttpResponseBadRequest()
        # Call the view
        return func(request, model, object_id, value)
    return view


@csrf_exempt
@login_required
@_api_view
def vote(request, model, object_id, value):
    """
    Likes or dislikes an item.
    """
    with transaction.atomic():
        vote_instance, created = model.objects.get_or_create(
            object_id=object_id,
            voter=request.user,
            defaults={'value': value}
        )
        
        if not created:
            if vote_instance.value == value:
                # Delete the vote if the user voted the same way twice
                vote_instance.delete()
                value = 0
            else:
                # If the user changes their vote, update it
                vote_instance.value = value
                vote_instance.save()

    response_dict = model.objects.filter(
        object__id=object_id
    ).aggregate(score=sum_with_default("value", default=0))
    response_dict.update({"voted_as": value})
    return JsonResponse(response_dict)
