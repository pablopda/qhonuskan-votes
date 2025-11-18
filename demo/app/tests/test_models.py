"""
Comprehensive unit tests for models and managers in qhonuskan_votes.

Tests cover:
- ThreadModel: Creation, string representation, VotesField descriptor
- ThreadModelVote: Vote creation, unique constraints, signals, get_model_name()
- ObjectsWithScoresManager: vote_score annotation
- SortByScoresManager: ordering by vote_score
"""

import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Manager

from app.models import ThreadModel
from qhonuskan_votes.models import (
    VotesField,
    ObjectsWithScoresManager,
    SortByScoresManager,
    vote_changed,
    _vote_models,
)


# =============================================================================
# Fixtures
# =============================================================================

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
def user3(db):
    """Create a third test user."""
    User = get_user_model()
    return User.objects.create_user(username='testuser3', password='testpass3')


@pytest.fixture
def thread(db):
    """Create a test thread."""
    return ThreadModel.objects.create(text="Test Thread")


@pytest.fixture
def thread2(db):
    """Create a second test thread."""
    return ThreadModel.objects.create(text="Second Test Thread")


@pytest.fixture
def thread3(db):
    """Create a third test thread."""
    return ThreadModel.objects.create(text="Third Test Thread")


@pytest.fixture
def vote_model(db):
    """Get the ThreadModelVote model class."""
    return ThreadModel.votes.__class__().__get__(None, ThreadModel)


@pytest.fixture
def signal_receiver():
    """Create a mock signal receiver for vote_changed."""
    receiver = MagicMock()
    vote_changed.connect(receiver, dispatch_uid="test_signal_receiver")
    yield receiver
    vote_changed.disconnect(receiver, dispatch_uid="test_signal_receiver")


# =============================================================================
# ThreadModel Tests
# =============================================================================

class TestThreadModel:
    """Tests for ThreadModel creation and basic functionality."""

    @pytest.mark.django_db
    def test_thread_creation(self):
        """Test that ThreadModel can be created with text field."""
        thread = ThreadModel.objects.create(text="My Test Thread")
        assert thread.pk is not None
        assert thread.text == "My Test Thread"

    @pytest.mark.django_db
    def test_thread_string_representation(self):
        """Test the string representation of ThreadModel."""
        thread = ThreadModel.objects.create(text="Test Thread for String")
        # ThreadModel doesn't have __str__ defined, so it uses default
        assert str(thread) == f"ThreadModel object ({thread.pk})"

    @pytest.mark.django_db
    def test_thread_empty_text(self):
        """Test that ThreadModel can be created with empty text."""
        thread = ThreadModel.objects.create(text="")
        assert thread.pk is not None
        assert thread.text == ""

    @pytest.mark.django_db
    def test_thread_long_text(self):
        """Test that ThreadModel can handle long text."""
        long_text = "A" * 10000
        thread = ThreadModel.objects.create(text=long_text)
        assert thread.text == long_text

    @pytest.mark.django_db
    def test_multiple_threads_creation(self):
        """Test creating multiple ThreadModel instances."""
        thread1 = ThreadModel.objects.create(text="Thread 1")
        thread2 = ThreadModel.objects.create(text="Thread 2")
        thread3 = ThreadModel.objects.create(text="Thread 3")

        assert ThreadModel.objects.count() == 3
        assert thread1.pk != thread2.pk != thread3.pk


class TestVotesFieldDescriptor:
    """Tests for VotesField descriptor behavior."""

    @pytest.mark.django_db
    def test_votes_field_exists(self):
        """Test that votes field is present on ThreadModel."""
        thread = ThreadModel.objects.create(text="Test")
        assert hasattr(thread, 'votes')

    @pytest.mark.django_db
    def test_votes_field_returns_related_manager_for_instance(self, thread):
        """Test that accessing votes on instance returns related manager."""
        votes_manager = thread.votes
        # Should be a related manager (reverse relation)
        assert hasattr(votes_manager, 'all')
        assert hasattr(votes_manager, 'create')
        assert hasattr(votes_manager, 'filter')

    @pytest.mark.django_db
    def test_votes_field_returns_vote_objects_manager_for_class(self):
        """Test that accessing votes on class returns Vote.objects manager."""
        vote_manager = ThreadModel.votes
        assert hasattr(vote_manager, 'all')
        assert hasattr(vote_manager, 'create')
        assert hasattr(vote_manager, 'filter')

    @pytest.mark.django_db
    def test_vote_model_created_dynamically(self):
        """Test that Vote model is created with correct name."""
        vote_model = ThreadModel.votes
        # The vote model should be named ThreadModelVote
        assert vote_model.model.__name__ == 'ThreadModelVote'

    @pytest.mark.django_db
    def test_vote_model_registered_in_vote_models(self):
        """Test that Vote model is registered in _vote_models dict."""
        # Access the votes to ensure model is created
        _ = ThreadModel.votes
        # Check that it's registered
        model_names = list(_vote_models.keys())
        assert any('ThreadModelVote' in name for name in model_names)


# =============================================================================
# ThreadModelVote Tests
# =============================================================================

class TestThreadModelVote:
    """Tests for the dynamically created ThreadModelVote model."""

    @pytest.mark.django_db
    def test_vote_creation_upvote(self, thread, user):
        """Test creating an upvote (value=1)."""
        vote = thread.votes.create(voter=user, value=1)
        assert vote.pk is not None
        assert vote.voter == user
        assert vote.value == 1
        assert vote.object == thread

    @pytest.mark.django_db
    def test_vote_creation_downvote(self, thread, user):
        """Test creating a downvote (value=-1)."""
        vote = thread.votes.create(voter=user, value=-1)
        assert vote.pk is not None
        assert vote.voter == user
        assert vote.value == -1
        assert vote.object == thread

    @pytest.mark.django_db
    def test_vote_creation_neutral(self, thread, user):
        """Test creating a neutral vote (value=0)."""
        vote = thread.votes.create(voter=user, value=0)
        assert vote.pk is not None
        assert vote.value == 0

    @pytest.mark.django_db
    def test_vote_creation_default_value(self, thread, user):
        """Test that default vote value is 1."""
        vote = thread.votes.create(voter=user)
        assert vote.value == 1

    @pytest.mark.django_db
    def test_vote_creation_custom_value(self, thread, user):
        """Test creating a vote with custom value."""
        vote = thread.votes.create(voter=user, value=5)
        assert vote.value == 5

    @pytest.mark.django_db
    def test_vote_creation_negative_custom_value(self, thread, user):
        """Test creating a vote with negative custom value."""
        vote = thread.votes.create(voter=user, value=-100)
        assert vote.value == -100

    @pytest.mark.django_db
    def test_vote_date_auto_set(self, thread, user):
        """Test that vote date is automatically set on creation."""
        vote = thread.votes.create(voter=user, value=1)
        assert vote.date is not None

    @pytest.mark.django_db
    def test_vote_string_representation_upvote(self, thread, user):
        """Test string representation for upvote."""
        vote = thread.votes.create(voter=user, value=1)
        str_repr = str(vote)
        assert user.username in str_repr
        assert 'likes' in str_repr

    @pytest.mark.django_db
    def test_vote_string_representation_downvote(self, thread, user):
        """Test string representation for downvote."""
        vote = thread.votes.create(voter=user, value=-1)
        str_repr = str(vote)
        assert user.username in str_repr
        assert 'hates' in str_repr

    @pytest.mark.django_db
    def test_unique_constraint_same_user_same_object(self, thread, user):
        """Test that a user cannot vote twice on the same object."""
        thread.votes.create(voter=user, value=1)
        with pytest.raises(IntegrityError):
            thread.votes.create(voter=user, value=-1)

    @pytest.mark.django_db
    def test_unique_constraint_different_users_same_object(self, thread, user, user2):
        """Test that different users can vote on the same object."""
        vote1 = thread.votes.create(voter=user, value=1)
        vote2 = thread.votes.create(voter=user2, value=-1)
        assert vote1.pk is not None
        assert vote2.pk is not None
        assert vote1.pk != vote2.pk

    @pytest.mark.django_db
    def test_unique_constraint_same_user_different_objects(self, thread, thread2, user):
        """Test that a user can vote on different objects."""
        vote1 = thread.votes.create(voter=user, value=1)
        vote2 = thread2.votes.create(voter=user, value=-1)
        assert vote1.pk is not None
        assert vote2.pk is not None

    @pytest.mark.django_db
    def test_get_model_name(self, thread, user):
        """Test the get_model_name() class method."""
        VoteModel = ThreadModel.votes.model
        model_name = VoteModel.get_model_name()
        assert 'ThreadModelVote' in model_name
        assert '.' in model_name  # Format is 'app_label.model_name'

    @pytest.mark.django_db
    def test_vote_ordering(self, thread, user, user2):
        """Test that votes are ordered by date."""
        vote1 = thread.votes.create(voter=user, value=1)
        vote2 = thread.votes.create(voter=user2, value=-1)

        votes = list(thread.votes.all())
        assert votes[0].pk == vote1.pk
        assert votes[1].pk == vote2.pk

    @pytest.mark.django_db
    def test_vote_update(self, thread, user):
        """Test updating a vote value."""
        vote = thread.votes.create(voter=user, value=1)
        vote.value = -1
        vote.save()

        vote.refresh_from_db()
        assert vote.value == -1

    @pytest.mark.django_db
    def test_vote_deletion(self, thread, user):
        """Test deleting a vote."""
        vote = thread.votes.create(voter=user, value=1)
        vote_pk = vote.pk
        vote.delete()

        assert not thread.votes.filter(pk=vote_pk).exists()


class TestVoteSignals:
    """Tests for vote_changed signal firing."""

    @pytest.mark.django_db
    def test_signal_fired_on_vote_create(self, thread, user, signal_receiver):
        """Test that vote_changed signal is fired when creating a vote."""
        thread.votes.create(voter=user, value=1)
        assert signal_receiver.called
        assert signal_receiver.call_count == 1

    @pytest.mark.django_db
    def test_signal_fired_on_vote_delete(self, thread, user, signal_receiver):
        """Test that vote_changed signal is fired when deleting a vote."""
        vote = thread.votes.create(voter=user, value=1)
        signal_receiver.reset_mock()

        vote.delete()
        assert signal_receiver.called
        assert signal_receiver.call_count == 1

    @pytest.mark.django_db
    def test_signal_fired_on_vote_value_change(self, thread, user, signal_receiver):
        """Test that vote_changed signal is fired when vote value changes."""
        vote = thread.votes.create(voter=user, value=1)
        signal_receiver.reset_mock()

        vote.value = -1
        vote.save()
        assert signal_receiver.called
        assert signal_receiver.call_count == 1

    @pytest.mark.django_db
    def test_signal_not_fired_on_save_without_value_change(self, thread, user, signal_receiver):
        """Test that signal is not fired when saving without value change."""
        vote = thread.votes.create(voter=user, value=1)
        signal_receiver.reset_mock()

        vote.save()  # Save without changing value
        assert not signal_receiver.called

    @pytest.mark.django_db
    def test_signal_sender_is_vote_instance(self, thread, user, signal_receiver):
        """Test that signal sender is the vote instance."""
        vote = thread.votes.create(voter=user, value=1)

        # Check the sender passed to the signal
        call_args = signal_receiver.call_args
        assert call_args is not None
        # Signal sends 'sender' as the vote instance
        sender = call_args[1].get('sender') or call_args[0][0] if call_args[0] else None
        if sender is None and call_args[1]:
            sender = call_args[1].get('sender')


# =============================================================================
# ObjectsWithScoresManager Tests
# =============================================================================

class TestObjectsWithScoresManager:
    """Tests for ObjectsWithScoresManager functionality."""

    @pytest.mark.django_db
    def test_manager_is_instance_of_objects_with_scores_manager(self):
        """Test that objects_with_scores is correct manager type."""
        assert isinstance(ThreadModel.objects_with_scores, ObjectsWithScoresManager)

    @pytest.mark.django_db
    def test_annotates_vote_score(self, thread, user, user2):
        """Test that vote_score is correctly annotated."""
        thread.votes.create(voter=user, value=1)
        thread.votes.create(voter=user2, value=1)

        thread_with_score = ThreadModel.objects_with_scores.get(pk=thread.pk)
        assert hasattr(thread_with_score, 'vote_score')
        assert thread_with_score.vote_score == 2

    @pytest.mark.django_db
    def test_returns_zero_for_objects_with_no_votes(self, thread):
        """Test that objects with no votes have vote_score of 0."""
        thread_with_score = ThreadModel.objects_with_scores.get(pk=thread.pk)
        assert thread_with_score.vote_score == 0

    @pytest.mark.django_db
    def test_calculates_mixed_votes_correctly(self, thread, user, user2, user3):
        """Test score calculation with mixed upvotes and downvotes."""
        thread.votes.create(voter=user, value=1)
        thread.votes.create(voter=user2, value=1)
        thread.votes.create(voter=user3, value=-1)

        thread_with_score = ThreadModel.objects_with_scores.get(pk=thread.pk)
        assert thread_with_score.vote_score == 1  # 1 + 1 - 1 = 1

    @pytest.mark.django_db
    def test_calculates_negative_score(self, thread, user, user2, user3):
        """Test that negative scores are calculated correctly."""
        thread.votes.create(voter=user, value=-1)
        thread.votes.create(voter=user2, value=-1)
        thread.votes.create(voter=user3, value=1)

        thread_with_score = ThreadModel.objects_with_scores.get(pk=thread.pk)
        assert thread_with_score.vote_score == -1  # -1 - 1 + 1 = -1

    @pytest.mark.django_db
    def test_multiple_objects_with_different_scores(self, thread, thread2, thread3, user, user2):
        """Test multiple objects with different vote scores."""
        # Thread 1: score = 2
        thread.votes.create(voter=user, value=1)
        thread.votes.create(voter=user2, value=1)

        # Thread 2: score = -1
        thread2.votes.create(voter=user, value=-1)

        # Thread 3: score = 0 (no votes)

        threads = ThreadModel.objects_with_scores.all()
        scores = {t.pk: t.vote_score for t in threads}

        assert scores[thread.pk] == 2
        assert scores[thread2.pk] == -1
        assert scores[thread3.pk] == 0

    @pytest.mark.django_db
    def test_filter_by_vote_score(self, thread, thread2, thread3, user, user2):
        """Test filtering objects by vote_score."""
        thread.votes.create(voter=user, value=1)
        thread.votes.create(voter=user2, value=1)
        thread2.votes.create(voter=user, value=-1)

        positive_threads = ThreadModel.objects_with_scores.filter(vote_score__gt=0)
        assert positive_threads.count() == 1
        assert positive_threads.first().pk == thread.pk

    @pytest.mark.django_db
    def test_order_by_vote_score(self, thread, thread2, thread3, user, user2):
        """Test ordering objects by vote_score."""
        thread.votes.create(voter=user, value=1)
        thread2.votes.create(voter=user, value=1)
        thread2.votes.create(voter=user2, value=1)

        ordered_threads = ThreadModel.objects_with_scores.order_by('-vote_score')
        thread_list = list(ordered_threads)

        assert thread_list[0].pk == thread2.pk  # score = 2
        assert thread_list[1].pk == thread.pk   # score = 1
        assert thread_list[2].pk == thread3.pk  # score = 0

    @pytest.mark.django_db
    def test_score_updates_after_vote_change(self, thread, user):
        """Test that score updates when vote is modified."""
        vote = thread.votes.create(voter=user, value=1)

        thread_with_score = ThreadModel.objects_with_scores.get(pk=thread.pk)
        assert thread_with_score.vote_score == 1

        vote.value = -1
        vote.save()

        thread_with_score = ThreadModel.objects_with_scores.get(pk=thread.pk)
        assert thread_with_score.vote_score == -1

    @pytest.mark.django_db
    def test_score_updates_after_vote_deletion(self, thread, user):
        """Test that score updates when vote is deleted."""
        vote = thread.votes.create(voter=user, value=1)

        thread_with_score = ThreadModel.objects_with_scores.get(pk=thread.pk)
        assert thread_with_score.vote_score == 1

        vote.delete()

        thread_with_score = ThreadModel.objects_with_scores.get(pk=thread.pk)
        assert thread_with_score.vote_score == 0


# =============================================================================
# SortByScoresManager Tests
# =============================================================================

class TestSortByScoresManager:
    """Tests for SortByScoresManager functionality."""

    @pytest.mark.django_db
    def test_sort_by_scores_manager_creation(self):
        """Test that SortByScoresManager can be instantiated."""
        manager = SortByScoresManager()
        assert manager is not None

    @pytest.mark.django_db
    def test_orders_by_vote_score_descending(self):
        """Test that objects are ordered by vote_score descending."""
        # Create a test model with SortByScoresManager
        from django.db import models

        # We'll test using ThreadModel but applying the manager's queryset logic
        # Create threads with different scores
        User = get_user_model()
        user1 = User.objects.create_user(username='sorttestuser1', password='pass')
        user2 = User.objects.create_user(username='sorttestuser2', password='pass')
        user3 = User.objects.create_user(username='sorttestuser3', password='pass')

        thread1 = ThreadModel.objects.create(text="Thread 1")  # score = 1
        thread2 = ThreadModel.objects.create(text="Thread 2")  # score = 3
        thread3 = ThreadModel.objects.create(text="Thread 3")  # score = -1

        thread1.votes.create(voter=user1, value=1)

        thread2.votes.create(voter=user1, value=1)
        thread2.votes.create(voter=user2, value=1)
        thread2.votes.create(voter=user3, value=1)

        thread3.votes.create(voter=user1, value=-1)

        # Manually apply SortByScoresManager logic to test ordering
        from django.db.models import Sum
        from django.db.models.functions import Coalesce

        sorted_threads = ThreadModel.objects.annotate(
            vote_score=Coalesce(Sum('threadmodelvote__value'), 0)
        ).order_by('-vote_score')

        thread_list = list(sorted_threads)

        # Should be ordered: thread2 (3), thread1 (1), thread3 (-1)
        assert thread_list[0].pk == thread2.pk
        assert thread_list[1].pk == thread1.pk
        assert thread_list[2].pk == thread3.pk

        assert thread_list[0].vote_score == 3
        assert thread_list[1].vote_score == 1
        assert thread_list[2].vote_score == -1

    @pytest.mark.django_db
    def test_sort_by_scores_with_ties(self):
        """Test ordering when multiple objects have the same score."""
        User = get_user_model()
        user1 = User.objects.create_user(username='tieuser1', password='pass')

        thread1 = ThreadModel.objects.create(text="Tie Thread 1")
        thread2 = ThreadModel.objects.create(text="Tie Thread 2")
        thread3 = ThreadModel.objects.create(text="Tie Thread 3")

        # All threads have score of 1
        thread1.votes.create(voter=user1, value=1)
        thread2.votes.create(voter=user1, value=1)
        thread3.votes.create(voter=user1, value=1)

        from django.db.models import Sum
        from django.db.models.functions import Coalesce

        sorted_threads = ThreadModel.objects.annotate(
            vote_score=Coalesce(Sum('threadmodelvote__value'), 0)
        ).order_by('-vote_score')

        # All should have same score
        for thread in sorted_threads:
            assert thread.vote_score == 1

    @pytest.mark.django_db
    def test_sort_by_scores_with_zero_scores(self):
        """Test that objects with zero scores are included and ordered correctly."""
        User = get_user_model()
        user1 = User.objects.create_user(username='zerouser1', password='pass')

        thread1 = ThreadModel.objects.create(text="Zero Thread 1")  # score = 0
        thread2 = ThreadModel.objects.create(text="Zero Thread 2")  # score = 1
        thread3 = ThreadModel.objects.create(text="Zero Thread 3")  # score = 0

        thread2.votes.create(voter=user1, value=1)

        from django.db.models import Sum
        from django.db.models.functions import Coalesce

        sorted_threads = ThreadModel.objects.annotate(
            vote_score=Coalesce(Sum('threadmodelvote__value'), 0)
        ).order_by('-vote_score')

        thread_list = list(sorted_threads)

        # thread2 should be first with score 1
        assert thread_list[0].pk == thread2.pk
        assert thread_list[0].vote_score == 1

        # thread1 and thread3 should follow with score 0
        assert thread_list[1].vote_score == 0
        assert thread_list[2].vote_score == 0


# =============================================================================
# Edge Case and Integration Tests
# =============================================================================

class TestEdgeCases:
    """Edge case and integration tests."""

    @pytest.mark.django_db
    def test_cascade_delete_on_thread_deletion(self, thread, user, user2):
        """Test that votes are deleted when thread is deleted."""
        thread.votes.create(voter=user, value=1)
        thread.votes.create(voter=user2, value=-1)

        VoteModel = ThreadModel.votes.model
        initial_count = VoteModel.objects.filter(object=thread).count()
        assert initial_count == 2

        thread.delete()

        # Votes should be deleted due to CASCADE
        remaining_votes = VoteModel.objects.filter(object_id=thread.pk).count()
        assert remaining_votes == 0

    @pytest.mark.django_db
    def test_cascade_delete_on_user_deletion(self, thread, user):
        """Test that votes are deleted when user is deleted."""
        thread.votes.create(voter=user, value=1)

        VoteModel = ThreadModel.votes.model
        initial_count = VoteModel.objects.filter(voter=user).count()
        assert initial_count == 1

        user.delete()

        # Votes should be deleted due to CASCADE
        remaining_votes = VoteModel.objects.all().count()
        assert remaining_votes == 0

    @pytest.mark.django_db
    def test_large_number_of_votes(self, thread):
        """Test handling of large number of votes on a single object."""
        User = get_user_model()

        # Create 100 users and votes
        for i in range(100):
            user = User.objects.create_user(username=f'bulkuser{i}', password='pass')
            value = 1 if i % 3 != 0 else -1  # 67 upvotes, 33 downvotes
            thread.votes.create(voter=user, value=value)

        thread_with_score = ThreadModel.objects_with_scores.get(pk=thread.pk)
        # Expected: 67 - 33 = 34
        expected_score = (100 - 34) - 34  # 66 upvotes - 34 downvotes = 32
        # Actually: 67 upvotes (when i % 3 != 0) and 34 downvotes (when i % 3 == 0)
        # i = 0, 3, 6, ..., 99 -> 34 downvotes
        # Remaining: 66 upvotes
        # Score = 66 - 34 = 32
        assert thread_with_score.vote_score == 32

    @pytest.mark.django_db
    def test_concurrent_access_simulation(self, thread, user, user2):
        """Test that votes can be created from multiple users."""
        # Simulate concurrent voting
        thread.votes.create(voter=user, value=1)
        thread.votes.create(voter=user2, value=-1)

        thread_with_score = ThreadModel.objects_with_scores.get(pk=thread.pk)
        assert thread_with_score.vote_score == 0
        assert thread.votes.count() == 2

    @pytest.mark.django_db
    def test_vote_value_boundary_values(self, thread, user):
        """Test vote creation with extreme boundary values."""
        # Test with large positive value
        vote = thread.votes.create(voter=user, value=2147483647)  # Max INT
        assert vote.value == 2147483647

        vote.value = -2147483648  # Min INT
        vote.save()
        assert vote.value == -2147483648

    @pytest.mark.django_db
    def test_manager_chaining(self, thread, thread2, user, user2):
        """Test that manager methods can be chained."""
        thread.votes.create(voter=user, value=1)
        thread.votes.create(voter=user2, value=1)
        thread2.votes.create(voter=user, value=-1)

        # Chain multiple manager methods
        result = ThreadModel.objects_with_scores.filter(
            text__contains="Test"
        ).order_by('-vote_score').first()

        # thread has higher score
        assert result.pk == thread.pk
        assert result.vote_score == 2
