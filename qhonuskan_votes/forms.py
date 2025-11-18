# forms.py

from django import forms
from django.utils.translation import gettext_lazy as _

from qhonuskan_votes.models import _vote_models
from qhonuskan_votes.exceptions import InvalidVoteModel
from qhonuskan_votes.logutils import setup_loghandlers

logger = setup_loghandlers()


class VoteForm(forms.Form):
    """
    Form for validating vote requests.

    Provides cleaner validation and better error messages for vote operations.
    """

    vote_model = forms.CharField(
        required=True,
        max_length=100,
        error_messages={
            'required': _('Vote model is required.'),
            'max_length': _('Vote model name is too long.'),
        }
    )

    object_id = forms.IntegerField(
        required=True,
        min_value=1,
        max_value=2147483647,
        error_messages={
            'required': _('Object ID is required.'),
            'invalid': _('Object ID must be a valid integer.'),
            'min_value': _('Object ID must be greater than 0.'),
            'max_value': _('Object ID is too large.'),
        }
    )

    value = forms.IntegerField(
        required=True,
        error_messages={
            'required': _('Vote value is required.'),
            'invalid': _('Vote value must be a valid integer.'),
        }
    )

    def clean_vote_model(self):
        """
        Validate that the vote_model is registered.
        """
        model_name = self.cleaned_data.get('vote_model')

        if model_name not in _vote_models:
            logger.warning(
                'Invalid vote model in form: model_name=%s, available_models=%s',
                model_name,
                list(_vote_models.keys())
            )
            raise forms.ValidationError(
                _('Invalid vote model "%(model_name)s". Model is not registered.'),
                code='invalid_model',
                params={'model_name': model_name}
            )

        return model_name

    def clean_value(self):
        """
        Validate that the vote value is either 1 (upvote) or -1 (downvote).
        """
        value = self.cleaned_data.get('value')

        if value not in (1, -1):
            logger.warning(
                'Invalid vote value in form: value=%s (must be 1 or -1)',
                value
            )
            raise forms.ValidationError(
                _('Vote value must be 1 (upvote) or -1 (downvote).'),
                code='invalid_value'
            )

        return value

    def get_vote_model(self):
        """
        Retrieve the vote model class after validation.

        Returns:
            The vote model class if the form is valid.

        Raises:
            InvalidVoteModel: If called before validation or if validation failed.
        """
        if not self.is_valid():
            logger.error(
                'get_vote_model called on invalid form: errors=%s',
                self.errors
            )
            raise InvalidVoteModel('Form validation failed. Cannot retrieve vote model.')

        model_name = self.cleaned_data['vote_model']
        return _vote_models[model_name]
