import pytest
import warnings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.template import Template, Context
from django.urls import reverse

from qhonuskan_votes.templatetags.qhonuskan_votes import (
    voting_script,
    get_vote_status,
    is_up_voted_by,
    is_down_voted_by,
    vote_buttons_for,
)
from qhonuskan_votes.utils import get_vote_model
from qhonuskan_votes.models import vote_changed
from app.models import ThreadModel, my_callback


@pytest.fixture(autouse=True)
def disconnect_signal():
    """Disconnect the demo app's signal handler to avoid errors during tests."""
    vote_changed.disconnect(my_callback, dispatch_uid="vote_changed")
    yield
    vote_changed.connect(my_callback, dispatch_uid="vote_changed")


@pytest.fixture
def user(db):
    """Create a test user."""
    User = get_user_model()
    return User.objects.create_user(username='testuser', password='testpass')


@pytest.fixture
def user2(db):
    """Create a second test user."""
    User = get_user_model()
    return User.objects.create_user(username='testuser2', password='testpass2')


@pytest.fixture
def anonymous_user():
    """Create an anonymous user."""
    return AnonymousUser()


@pytest.fixture
def thread(db):
    """Create a test thread."""
    return ThreadModel.objects.create(text="Test Thread")


class TestVotingScript:
    """Tests for the voting_script template tag."""

    @pytest.mark.django_db
    def test_returns_correct_context_for_authenticated_user(self, user):
        """Test that voting_script returns correct context for an authenticated user."""
        result = voting_script(user)

        assert 'vote_url' in result
        assert 'handle_pending_vote' in result
        assert 'user_is_authenticated' in result

        assert result['vote_url'] == reverse('qhonuskan_vote')
        assert result['handle_pending_vote'] == reverse('handle_pending_vote')
        assert result['user_is_authenticated'] is True

    @pytest.mark.django_db
    def test_returns_correct_context_for_anonymous_user(self, anonymous_user):
        """Test that voting_script returns correct context for an anonymous user."""
        result = voting_script(anonymous_user)

        assert 'vote_url' in result
        assert 'handle_pending_vote' in result
        assert 'user_is_authenticated' in result

        assert result['vote_url'] == reverse('qhonuskan_vote')
        assert result['handle_pending_vote'] == reverse('handle_pending_vote')
        assert result['user_is_authenticated'] is False


class TestGetVoteStatus:
    """Tests for the get_vote_status template tag."""

    @pytest.mark.django_db
    def test_returns_zero_for_anonymous_user(self, thread, anonymous_user):
        """Test that get_vote_status returns 0 for an anonymous user."""
        result = get_vote_status(thread, anonymous_user)
        assert result == 0

    @pytest.mark.django_db
    def test_returns_zero_when_no_vote(self, thread, user):
        """Test that get_vote_status returns 0 when user has not voted."""
        result = get_vote_status(thread, user)
        assert result == 0

    @pytest.mark.django_db
    def test_returns_one_for_upvote(self, thread, user):
        """Test that get_vote_status returns 1 when user has upvoted."""
        vote_model = get_vote_model('app.ThreadModelVote')
        vote_model.objects.create(voter=user, object=thread, value=1)

        result = get_vote_status(thread, user)
        assert result == 1

    @pytest.mark.django_db
    def test_returns_negative_one_for_downvote(self, thread, user):
        """Test that get_vote_status returns -1 when user has downvoted."""
        vote_model = get_vote_model('app.ThreadModelVote')
        vote_model.objects.create(voter=user, object=thread, value=-1)

        result = get_vote_status(thread, user)
        assert result == -1

    @pytest.mark.django_db
    def test_returns_correct_value_for_different_users(self, thread, user, user2):
        """Test that get_vote_status returns correct values for different users."""
        vote_model = get_vote_model('app.ThreadModelVote')

        # User 1 upvotes
        vote_model.objects.create(voter=user, object=thread, value=1)
        # User 2 downvotes
        vote_model.objects.create(voter=user2, object=thread, value=-1)

        assert get_vote_status(thread, user) == 1
        assert get_vote_status(thread, user2) == -1


class TestIsUpVotedBy:
    """Tests for the is_up_voted_by template filter."""

    @pytest.mark.django_db
    def test_returns_false_for_anonymous_user(self, thread, anonymous_user):
        """Test that is_up_voted_by returns False for an anonymous user."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = is_up_voted_by(thread, anonymous_user)

            assert result is False
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)

    @pytest.mark.django_db
    def test_returns_false_when_no_vote(self, thread, user):
        """Test that is_up_voted_by returns False when user has not voted."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = is_up_voted_by(thread, user)
            assert result is False

    @pytest.mark.django_db
    def test_returns_true_when_upvoted(self, thread, user):
        """Test that is_up_voted_by returns True when user has upvoted."""
        vote_model = get_vote_model('app.ThreadModelVote')
        vote_model.objects.create(voter=user, object=thread, value=1)

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = is_up_voted_by(thread, user)
            assert result is True

    @pytest.mark.django_db
    def test_returns_false_when_downvoted(self, thread, user):
        """Test that is_up_voted_by returns False when user has downvoted."""
        vote_model = get_vote_model('app.ThreadModelVote')
        vote_model.objects.create(voter=user, object=thread, value=-1)

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = is_up_voted_by(thread, user)
            assert result is False

    @pytest.mark.django_db
    def test_emits_deprecation_warning(self, thread, user):
        """Test that is_up_voted_by emits a deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            is_up_voted_by(thread, user)

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert 'is_up_voted_by' in str(w[0].message)
            assert 'get_vote_status' in str(w[0].message)


class TestIsDownVotedBy:
    """Tests for the is_down_voted_by template filter."""

    @pytest.mark.django_db
    def test_returns_false_for_anonymous_user(self, thread, anonymous_user):
        """Test that is_down_voted_by returns False for an anonymous user."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = is_down_voted_by(thread, anonymous_user)

            assert result is False
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)

    @pytest.mark.django_db
    def test_returns_false_when_no_vote(self, thread, user):
        """Test that is_down_voted_by returns False when user has not voted."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = is_down_voted_by(thread, user)
            assert result is False

    @pytest.mark.django_db
    def test_returns_true_when_downvoted(self, thread, user):
        """Test that is_down_voted_by returns True when user has downvoted."""
        vote_model = get_vote_model('app.ThreadModelVote')
        vote_model.objects.create(voter=user, object=thread, value=-1)

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = is_down_voted_by(thread, user)
            assert result is True

    @pytest.mark.django_db
    def test_returns_false_when_upvoted(self, thread, user):
        """Test that is_down_voted_by returns False when user has upvoted."""
        vote_model = get_vote_model('app.ThreadModelVote')
        vote_model.objects.create(voter=user, object=thread, value=1)

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = is_down_voted_by(thread, user)
            assert result is False

    @pytest.mark.django_db
    def test_emits_deprecation_warning(self, thread, user):
        """Test that is_down_voted_by emits a deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            is_down_voted_by(thread, user)

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert 'is_down_voted_by' in str(w[0].message)
            assert 'get_vote_status' in str(w[0].message)


class TestVoteButtonsFor:
    """Tests for the vote_buttons_for template tag."""

    @pytest.mark.django_db
    def test_returns_correct_context(self, thread, user):
        """Test that vote_buttons_for returns the correct context."""
        result = vote_buttons_for(thread, user)

        assert 'object' in result
        assert 'vote_model' in result
        assert 'user' in result

        assert result['object'] == thread
        assert result['vote_model'] == 'app.ThreadModelVote'
        assert result['user'] == user

    @pytest.mark.django_db
    def test_vote_model_format(self, thread, user):
        """Test that the vote_model is in the correct format."""
        result = vote_buttons_for(thread, user)

        # Should be in format: app_label.ObjectNameVote
        vote_model = result['vote_model']
        assert '.' in vote_model
        assert vote_model.endswith('Vote')

        app_label, model_name = vote_model.split('.')
        assert app_label == thread._meta.app_label
        assert model_name == f"{thread._meta.object_name}Vote"

    @pytest.mark.django_db
    def test_renders_in_template(self, thread, user):
        """Test that vote_buttons_for can be used in a template."""
        template = Template(
            '{% load qhonuskan_votes %}'
            '{% vote_buttons_for obj user %}'
        )
        context = Context({'obj': thread, 'user': user})

        # This should not raise an exception
        rendered = template.render(context)

        # The rendered output should not be empty
        assert rendered is not None

    @pytest.mark.django_db
    def test_works_with_anonymous_user(self, thread, anonymous_user):
        """Test that vote_buttons_for works with an anonymous user."""
        result = vote_buttons_for(thread, anonymous_user)

        assert result['object'] == thread
        assert result['user'] == anonymous_user
        assert result['vote_model'] == 'app.ThreadModelVote'
