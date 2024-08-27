from django.db.models import Sum, aggregates
from django.db.models.functions import Coalesce
from qhonuskan_votes.models import _vote_models
from qhonuskan_votes.exceptions import InvalidVoteModel

def get_vote_model(model_name):
    if model_name in _vote_models:
        return _vote_models[model_name]
    else:
        raise InvalidVoteModel('No such vote model "%s"' % model_name)

class SumWithDefault(aggregates.Sum):
    name = 'SumWithDefault'
    template = 'COALESCE(%(function)s(%(field)s), %(default)s)'

# Register the SumWithDefault aggregation
setattr(aggregates, 'SumWithDefault', SumWithDefault)

# For Django 3.2+, you can use this function as an alternative
def sum_with_default(field, default=0):
    return Coalesce(Sum(field), default)
