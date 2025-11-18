"""
Views for the qhonuskan-votes voting API.

This module provides HTTP endpoints for voting operations in Django applications.
It handles vote creation, updates, and deletion through a RESTful JSON API.

API Endpoints:
    POST /vote/
        Submit a vote for an object. See the vote() function for full details.

Authentication:
    All voting endpoints require user authentication. Unauthenticated requests
    receive a 401 response with a login URL and the vote is saved in the session
    for later processing after login.

Response Format:
    All endpoints return JSON responses with consistent structure:

    Success Response (200 OK)::

        {
            "voted_as": 1,      // 1 (upvote), -1 (downvote), or 0 (removed)
            "score": 42         // New total score for the object
        }

    Validation Error (400 Bad Request)::

        {
            "status": "error",
            "error_type": "invalid_vote_model" | "invalid_vote_value" | "validation_error",
            "message": "Error description"
        }

    Authentication Error (401 Unauthorized)::

        {
            "status": "unauthorized",
            "message": "Please log in to vote",
            "login_url": "/accounts/login/",
            "next": "/articles/123/"
        }

    Method Not Allowed (405)::

        {
            "status": "error",
            "error_type": "permission_error",
            "message": "Only POST method is allowed",
            "allowed_methods": ["POST"]
        }

Example Usage:
    Submit an upvote via JavaScript::

        fetch('/vote/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: new URLSearchParams({
                'vote_model': 'myapp.ArticleVote',
                'object_id': '123',
                'value': '1'
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log('New score:', data.score);
            console.log('User voted as:', data.voted_as);
        });

    Submit a downvote via curl::

        curl -X POST http://localhost:8000/vote/ \\
            -H "Content-Type: application/x-www-form-urlencoded" \\
            -H "Cookie: csrftoken=...; sessionid=..." \\
            -H "X-CSRFToken: ..." \\
            -d "vote_model=myapp.ArticleVote&object_id=123&value=-1"

Configuration:
    QHONUSKAN_VOTES_LOGIN_URL: Custom login URL (default: reverse('login'))

Module Attributes:
    logger: Logger instance for vote operations.
"""

from typing import Any, Callable, Optional, Type

from django.db import models, IntegrityError, DatabaseError
from django.http import HttpRequest, JsonResponse
from django.urls import reverse
from django.conf import settings
from django.utils.translation import gettext as _
from django.utils.http import url_has_allowed_host_and_scheme

from qhonuskan_votes.forms import VoteForm
from qhonuskan_votes.logutils import setup_loghandlers
from qhonuskan_votes.services import VoteService
from qhonuskan_votes.exceptions import (
    InvalidVoteModel,
    InvalidVoteValue,
    VoteValidationError,
    VotePermissionError,
    VoteNotFound,
    VoteConflictError,
)

logger = setup_loghandlers()


def get_login_url() -> str:
    """
    Get the login URL for redirecting unauthenticated users.

    This function returns the configured login URL, falling back to Django's
    default 'login' URL name if not configured.

    Returns:
        str: The login URL path (e.g., '/accounts/login/').

    Configuration:
        Set QHONUSKAN_VOTES_LOGIN_URL in Django settings to customize::

            # settings.py
            QHONUSKAN_VOTES_LOGIN_URL = '/custom/login/'

    Example:
        >>> from qhonuskan_votes.views import get_login_url
        >>> login_url = get_login_url()
        >>> print(login_url)
        '/accounts/login/'
    """
    return getattr(settings, 'QHONUSKAN_VOTES_LOGIN_URL', reverse('login'))


def _api_view(
    func: Callable[[HttpRequest, Type[models.Model], int, int], JsonResponse]
) -> Callable[[HttpRequest], JsonResponse]:
    """
    Decorator that validates vote requests and handles common API concerns.

    This decorator wraps vote view functions to provide:
    - Authentication checking (saves pending votes for unauthenticated users)
    - HTTP method validation (POST only)
    - Form validation using VoteForm
    - Consistent error responses with appropriate HTTP status codes
    - Logging for validation failures

    The decorator extracts and validates the following POST parameters:
    - vote_model: The fully qualified name of the vote model (e.g., 'myapp.ArticleVote')
    - object_id: The ID of the object being voted on (positive integer)
    - value: The vote value (1 for upvote, -1 for downvote)

    Args:
        func: The view function to wrap. Must accept (request, model, object_id, value)
            and return a JsonResponse.

    Returns:
        Callable[[HttpRequest], JsonResponse]: A wrapped view function that handles
            validation and error responses.

    Raises:
        VotePermissionError: When user is not authenticated or uses wrong HTTP method.
        InvalidVoteModel: When the vote_model parameter references an invalid model.
        InvalidVoteValue: When the vote value is not 1 or -1.
        VoteValidationError: For other validation failures.

    Example:
        Create a custom vote view::

            @_api_view
            def custom_vote(request, model, object_id, value):
                # model, object_id, and value are already validated
                # Implement custom voting logic here
                return JsonResponse({"status": "success"})
    """
    def view(request: HttpRequest) -> JsonResponse:
        try:
            # Check authentication
            if not request.user.is_authenticated:
                # Save vote intention in session
                request.session['pending_vote'] = {
                    'vote_model': request.POST.get('vote_model'),
                    'object_id': request.POST.get('object_id'),
                    'value': request.POST.get('value')
                }
                raise VotePermissionError("Authentication required to vote")

            # Check HTTP method
            if not request.method == 'POST':
                raise VotePermissionError("Only POST method is allowed")

            # Use VoteForm for validation
            form = VoteForm(request.POST)

            if not form.is_valid():
                # Log validation errors for debugging
                error_messages = []
                for field, errors in form.errors.items():
                    for error in errors:
                        error_messages.append(f"{field}: {error}")

                logger.warning(
                    'Vote validation failed: user_id=%s, errors=%s, '
                    'vote_model=%s, object_id=%s, value=%s',
                    request.user.id,
                    error_messages,
                    request.POST.get('vote_model', 'unknown'),
                    request.POST.get('object_id', 'unknown'),
                    request.POST.get('value', 'unknown')
                )

                # Determine specific exception type based on error
                if 'vote_model' in form.errors:
                    raise InvalidVoteModel(
                        f"Invalid vote model: {request.POST.get('vote_model', 'unknown')}"
                    )
                elif 'value' in form.errors:
                    raise InvalidVoteValue(
                        f"Invalid vote value: {request.POST.get('value', 'unknown')}"
                    )
                else:
                    raise VoteValidationError("; ".join(error_messages))

            # Get validated data
            model = form.get_vote_model()
            object_id = form.cleaned_data['object_id']
            value = form.cleaned_data['value']

            # Call the view
            return func(request, model, object_id, value)

        except VotePermissionError as e:
            if not request.user.is_authenticated:
                # Validate the next URL to prevent open redirect attacks
                next_url = request.GET.get('next', request.META.get('HTTP_REFERER', '/'))
                if not url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure()
                ):
                    next_url = '/'
                return JsonResponse({
                    "status": "unauthorized",
                    "message": "Please log in to vote",
                    "login_url": get_login_url(),
                    "next": next_url
                }, status=401)
            return JsonResponse({
                "status": "error",
                "error_type": "permission_error",
                "message": str(e),
                "allowed_methods": ["POST"]
            }, status=405)

        except InvalidVoteModel as e:
            logger.warning('InvalidVoteModel: %s', str(e))
            return JsonResponse({
                "status": "error",
                "error_type": "invalid_vote_model",
                "message": str(e)
            }, status=400)

        except InvalidVoteValue as e:
            logger.warning('InvalidVoteValue: %s', str(e))
            return JsonResponse({
                "status": "error",
                "error_type": "invalid_vote_value",
                "message": str(e)
            }, status=400)

        except VoteValidationError as e:
            return JsonResponse({
                "status": "error",
                "error_type": "validation_error",
                "message": str(e)
            }, status=400)

        except VoteNotFound as e:
            logger.warning('VoteNotFound: %s', str(e))
            return JsonResponse({
                "status": "error",
                "error_type": "vote_not_found",
                "message": str(e)
            }, status=404)

        except VoteConflictError as e:
            logger.warning('VoteConflictError: %s', str(e))
            return JsonResponse({
                "status": "error",
                "error_type": "vote_conflict",
                "message": str(e)
            }, status=409)

    return view

@_api_view
def vote(
    request: HttpRequest,
    model: Type[models.Model],
    object_id: int,
    value: int
) -> JsonResponse:
    """
    Submit a vote (upvote or downvote) for an object.

    This is the main voting endpoint. It handles creating, updating, and removing
    votes with toggle behavior:
    - If the user votes the same way twice, the vote is removed (toggle off)
    - If the user changes their vote, the vote is updated
    - If no vote exists, a new vote is created

    HTTP Method:
        POST

    Request Parameters (POST body, form-encoded):
        vote_model (str): The fully qualified name of the vote model.
            Format: 'app_label.ModelNameVote' (e.g., 'myapp.ArticleVote').
            Must be a registered vote model.
        object_id (int): The primary key of the object being voted on.
            Must be a positive integer.
        value (int): The vote value.
            - 1: Upvote (like)
            - -1: Downvote (dislike)

    Args:
        request (HttpRequest): The HTTP request object.
        model (Type[models.Model]): The validated vote model class.
        object_id (int): The validated object ID.
        value (int): The validated vote value (1 or -1).

    Returns:
        JsonResponse: JSON response with the vote result.

        Success (200 OK)::

            {
                "voted_as": 1,   // Current vote: 1 (up), -1 (down), 0 (removed)
                "score": 42      // New total score for the object
            }

    Response Fields:
        voted_as (int): The user's current vote state after this action.
            - 1: User has upvoted
            - -1: User has downvoted
            - 0: User's vote was removed (toggled off)
        score (int): The new aggregate score for the object (sum of all votes).

    Example:
        Upvote an article::

            POST /vote/
            Content-Type: application/x-www-form-urlencoded

            vote_model=myapp.ArticleVote&object_id=123&value=1

            Response:
            {"voted_as": 1, "score": 15}

        Toggle off the upvote (vote again with same value)::

            POST /vote/
            Content-Type: application/x-www-form-urlencoded

            vote_model=myapp.ArticleVote&object_id=123&value=1

            Response:
            {"voted_as": 0, "score": 14}

        Change to downvote::

            POST /vote/
            Content-Type: application/x-www-form-urlencoded

            vote_model=myapp.ArticleVote&object_id=123&value=-1

            Response:
            {"voted_as": -1, "score": 13}

    Note:
        This function is decorated with @_api_view which handles authentication,
        validation, and error responses. The parameters passed to this function
        are already validated.
    """
    try:
        voted_as, score = VoteService.create_or_update_vote(
            vote_model=model,
            user=request.user,
            object_id=object_id,
            value=value
        )
    except IntegrityError as e:
        logger.error(
            'Vote IntegrityError (race condition): user_id=%s, model=%s, '
            'object_id=%s, value=%s, error=%s',
            request.user.id,
            model.__name__,
            object_id,
            value,
            str(e)
        )
        return JsonResponse({
            "status": "error",
            "error_type": "conflict",
            "message": "Vote conflict - please try again"
        }, status=409)
    except DatabaseError as e:
        logger.error(
            'Vote DatabaseError: user_id=%s, model=%s, '
            'object_id=%s, value=%s, error=%s',
            request.user.id,
            model.__name__,
            object_id,
            value,
            str(e)
        )
        return JsonResponse({
            "status": "error",
            "error_type": "database_error",
            "message": "Database error occurred"
        }, status=500)

    logger.info(
        'Vote recorded: user_id=%s, model=%s, object_id=%s, '
        'vote_value=%s, voted_as=%s, new_score=%s',
        request.user.id,
        model.__name__,
        object_id,
        value,
        voted_as,
        score
    )

    return JsonResponse({
        "voted_as": voted_as,
        "score": score
    })

def process_pending_vote(request: HttpRequest) -> Optional[JsonResponse]:
    """
    Process any pending votes stored in the user's session.

    When an unauthenticated user attempts to vote, the vote data is saved in their
    session. After the user logs in, this function can be called to process that
    pending vote automatically.

    This enables a seamless user experience where users can click vote buttons
    before logging in, and their intended vote is applied after authentication.

    Args:
        request (HttpRequest): The HTTP request object. Must have an authenticated
            user and may contain a 'pending_vote' key in the session.

    Returns:
        Optional[JsonResponse]: The vote response if a pending vote was processed,
            or None if there was no pending vote or the user is not authenticated.

        Success response (when vote is processed)::

            {
                "voted_as": 1,
                "score": 42
            }

    Session Data:
        The function looks for 'pending_vote' in request.session with this structure::

            {
                "vote_model": "myapp.ArticleVote",
                "object_id": "123",
                "value": "1"
            }

        The pending vote is removed from the session after processing (success or failure).

    Example:
        Process pending vote after login::

            from qhonuskan_votes.views import process_pending_vote

            def my_login_view(request):
                # ... handle login ...

                # Process any pending vote
                vote_result = process_pending_vote(request)
                if vote_result:
                    # Vote was processed
                    messages.success(request, "Your vote has been recorded!")

                return redirect('home')

    Note:
        This function modifies request.POST and request.method to simulate a
        vote POST request. The original request object is modified in place.
    """
    pending_vote = request.session.pop('pending_vote', None)
    if pending_vote and request.user.is_authenticated:
        logger.info(
            'Processing pending vote: user_id=%s, vote_model=%s, '
            'object_id=%s, value=%s',
            request.user.id,
            pending_vote.get('vote_model'),
            pending_vote.get('object_id'),
            pending_vote.get('value')
        )
        # Simulate a POST request with the pending vote data
        request.POST = request.POST.copy()
        request.POST['vote_model'] = pending_vote['vote_model']
        request.POST['object_id'] = pending_vote['object_id']
        request.POST['value'] = pending_vote['value']
        request.method = 'POST'

        # Call the vote view function directly
        return vote(request)  # type: ignore
    return None


def handle_pending_vote(request: HttpRequest) -> JsonResponse:
    """
    HTTP endpoint to process pending votes after user authentication.

    This view can be called after login to automatically process any votes
    that were attempted while the user was unauthenticated. It provides a
    user-friendly message indicating whether a vote was processed.

    HTTP Method:
        GET or POST

    Args:
        request (HttpRequest): The HTTP request object with an authenticated user.

    Returns:
        JsonResponse: JSON response indicating the result.

        Success - vote processed (200 OK)::

            {
                "vote_message": "Your pending vote has been processed!"
            }

        Success - no pending vote (200 OK)::

            {
                "vote_message": null
            }

        Error - not authenticated (401 Unauthorized)::

            {
                "status": "error",
                "message": "Authentication required. Please log in to process pending votes.",
                "login_url": "/accounts/login/"
            }

    Example:
        Call after login redirect::

            // In your post-login JavaScript
            fetch('/handle-pending-vote/')
                .then(response => response.json())
                .then(data => {
                    if (data.vote_message) {
                        showNotification(data.vote_message);
                    }
                });

    Note:
        This is a convenience wrapper around process_pending_vote() that
        provides a standard HTTP endpoint with appropriate error handling.
    """
    if not request.user.is_authenticated:
        return JsonResponse({
            "status": "error",
            "message": "Authentication required. Please log in to process pending votes.",
            "login_url": get_login_url()
        }, status=401)

    vote_response = process_pending_vote(request)
    vote_message = None
    if vote_response:
        vote_message = _("Your pending vote has been processed!")
    return JsonResponse({'vote_message': vote_message})
