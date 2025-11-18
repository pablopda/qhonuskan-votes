class QhonuskanVotesException(Exception):
    """
    Base exception for all qhonuskan_votes exceptions.

    All exceptions from qhonuskan_votes should inherit from this exception
    to allow for easy catching of all vote-related errors.
    """


class InvalidVoteModel(QhonuskanVotesException):
    """
    Raised when an invalid vote model was specified.

    This exception is raised when the vote_model parameter references
    a model that is not registered as a valid vote model.
    """


class InvalidVoteValue(QhonuskanVotesException):
    """
    Raised when an invalid vote value is provided.

    Vote values must be either 1 (upvote) or -1 (downvote).
    This exception is raised when any other value is submitted.
    """


class VoteNotFound(QhonuskanVotesException):
    """
    Raised when a requested vote record does not exist.

    This exception is raised when attempting to access, update, or delete
    a vote that cannot be found in the database.
    """


class VoteValidationError(QhonuskanVotesException):
    """
    Raised when vote data fails validation.

    This exception is raised when the submitted vote data is malformed,
    missing required fields, or contains invalid data types.
    """


class VotePermissionError(QhonuskanVotesException):
    """
    Raised when a user lacks permission to perform a vote operation.

    This exception is raised when a user attempts to vote without
    proper authentication or authorization.
    """


class VoteConflictError(QhonuskanVotesException):
    """
    Raised when a vote operation conflicts with existing data.

    This exception is raised when there are integrity conflicts,
    such as duplicate votes or concurrent modification issues.
    """
