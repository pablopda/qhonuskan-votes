"""
Django AppConfig for the qhonuskan-votes application.

This module provides the application configuration following Django best practices
for app initialization and signal registration.
"""

from django.apps import AppConfig


class QhonuskanVotesConfig(AppConfig):
    """
    Application configuration for the qhonuskan-votes voting system.

    This AppConfig handles proper initialization of the application,
    including signal registration in the ready() method following
    Django best practices.

    Attributes:
        name: The full Python path to the application.
        verbose_name: A human-readable name for the application.
        default_auto_field: The default primary key field type.
    """

    name = 'qhonuskan_votes'
    verbose_name = 'Voting System'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        """
        Perform initialization tasks when the application is ready.

        This method is called once Django has finished loading the application.
        It imports and connects all signal handlers to ensure proper
        application behavior.

        Signal handlers are imported here to:
        1. Avoid circular imports
        2. Ensure models are fully loaded before signals are connected
        3. Follow Django's recommended pattern for signal registration
        """
        # Import signal handlers to register them
        # This import triggers the signal connections defined in signals.py
        from qhonuskan_votes import signals  # noqa: F401
