import pytest
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.contrib.auth import get_user_model

from qhonuskan_votes.utils import get_vote_model, sum_with_default
from qhonuskan_votes.exceptions import InvalidVoteModel
from qhonuskan_votes.models import vote_changed
from app.models import ThreadModel, my_callback


@pytest.fixture(autouse=True)
def disconnect_signal():
    """Disconnect the demo app's signal handler to avoid errors during tests."""
    vote_changed.disconnect(my_callback, dispatch_uid="vote_changed")
    yield
    vote_changed.connect(my_callback, dispatch_uid="vote_changed")


class TestGetVoteModel:
    """Tests for the get_vote_model utility function."""

    @pytest.mark.django_db
    def test_returns_correct_model_for_valid_name(self):
        """Test that get_vote_model returns the correct model for a valid vote model name."""
        # The ThreadModel has a VotesField, which creates a ThreadModelVote model
        vote_model = get_vote_model('app.ThreadModelVote')

        # Verify the returned model is the correct vote model
        assert vote_model is not None
        assert vote_model._meta.object_name == 'ThreadModelVote'
        assert vote_model._meta.app_label == 'app'

    @pytest.mark.django_db
    def test_raises_invalid_vote_model_for_invalid_name(self):
        """Test that get_vote_model raises InvalidVoteModel for an invalid model name."""
        with pytest.raises(InvalidVoteModel) as exc_info:
            get_vote_model('nonexistent.InvalidModel')

        assert 'No such vote model' in str(exc_info.value)
        assert 'nonexistent.InvalidModel' in str(exc_info.value)

    @pytest.mark.django_db
    def test_raises_invalid_vote_model_for_empty_string(self):
        """Test that get_vote_model raises InvalidVoteModel for an empty string."""
        with pytest.raises(InvalidVoteModel) as exc_info:
            get_vote_model('')

        assert 'No such vote model' in str(exc_info.value)

    @pytest.mark.django_db
    def test_raises_invalid_vote_model_for_partial_name(self):
        """Test that get_vote_model raises InvalidVoteModel for a partial model name."""
        with pytest.raises(InvalidVoteModel) as exc_info:
            get_vote_model('ThreadModelVote')

        assert 'No such vote model' in str(exc_info.value)


class TestSumWithDefault:
    """Tests for the sum_with_default utility function."""

    @pytest.fixture
    def user(self, db):
        """Create a test user."""
        User = get_user_model()
        return User.objects.create_user(username='testuser', password='testpass')

    @pytest.fixture
    def thread_with_votes(self, db, user):
        """Create a thread with some votes."""
        thread = ThreadModel.objects.create(text="Test Thread with Votes")
        # Create votes by directly using the vote model
        vote_model = get_vote_model('app.ThreadModelVote')
        vote_model.objects.create(voter=user, object=thread, value=1)
        return thread

    @pytest.fixture
    def thread_without_votes(self, db):
        """Create a thread without any votes."""
        return ThreadModel.objects.create(text="Test Thread without Votes")

    @pytest.mark.django_db
    def test_returns_sum_when_values_exist(self, thread_with_votes):
        """Test that sum_with_default returns the sum when values exist."""
        vote_model = get_vote_model('app.ThreadModelVote')

        # Use sum_with_default to aggregate vote values
        result = vote_model.objects.filter(
            object=thread_with_votes
        ).aggregate(
            total=sum_with_default('value', 0)
        )

        assert result['total'] == 1

    @pytest.mark.django_db
    def test_returns_default_when_no_values(self, thread_without_votes):
        """Test that sum_with_default returns the default when no values exist."""
        vote_model = get_vote_model('app.ThreadModelVote')

        # Use sum_with_default to aggregate vote values on an object with no votes
        result = vote_model.objects.filter(
            object=thread_without_votes
        ).aggregate(
            total=sum_with_default('value', 0)
        )

        assert result['total'] == 0

    @pytest.mark.django_db
    def test_returns_custom_default_when_no_values(self, thread_without_votes):
        """Test that sum_with_default returns a custom default when specified."""
        vote_model = get_vote_model('app.ThreadModelVote')

        # Use sum_with_default with a custom default value
        result = vote_model.objects.filter(
            object=thread_without_votes
        ).aggregate(
            total=sum_with_default('value', 100)
        )

        assert result['total'] == 100

    @pytest.mark.django_db
    def test_returns_sum_with_multiple_votes(self, db, user):
        """Test that sum_with_default correctly sums multiple votes."""
        User = get_user_model()
        user2 = User.objects.create_user(username='testuser2', password='testpass2')
        user3 = User.objects.create_user(username='testuser3', password='testpass3')

        thread = ThreadModel.objects.create(text="Test Thread with Multiple Votes")
        vote_model = get_vote_model('app.ThreadModelVote')

        # Create multiple votes
        vote_model.objects.create(voter=user, object=thread, value=1)
        vote_model.objects.create(voter=user2, object=thread, value=1)
        vote_model.objects.create(voter=user3, object=thread, value=-1)

        result = vote_model.objects.filter(
            object=thread
        ).aggregate(
            total=sum_with_default('value', 0)
        )

        # 1 + 1 + (-1) = 1
        assert result['total'] == 1

    @pytest.mark.django_db
    def test_sum_with_default_on_empty_queryset(self):
        """Test that sum_with_default returns default on an empty queryset."""
        vote_model = get_vote_model('app.ThreadModelVote')

        # Filter for a non-existent object ID
        result = vote_model.objects.filter(
            object_id=999999
        ).aggregate(
            total=sum_with_default('value', 42)
        )

        assert result['total'] == 42
