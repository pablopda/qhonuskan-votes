===============
Qhonuskan-Votes
===============

Easy to use reddit-like voting system for Django models.

Features
--------

* Does not use GenericForeignKeys (which can complicate queries)
* Provides vote_buttons_for templatetag to generate HTML code for vote buttons
* Includes default_buttons.css for basic styling (can be overridden)
* voting_script template tag generates JavaScript code for AJAX voting requests
* Pure CSS buttons by default (no images required)
* Compatible with Django 4.2+
* Supports Python 3.9+

What's new in version 0.4.0?
----------------------------

* Updated for Django 4.2 compatibility
* Dropped support for Python 3.6, 3.7, 3.8
* Support for anonymous user voting with login redirection
* Return to original URL after login to process pending vote
* Tailwind CSS design for voting buttons
* Color change for buttons to indicate user's vote

Requirements
------------

* Python 3.8+
* Django 4.2+

Installation
------------

1. Install qhonuskan-votes:

   ::

     pip install qhonuskan-votes

2. Add qhonuskan_votes to your INSTALLED_APPS:

   ::

     INSTALLED_APPS = (
         ...
         'qhonuskan_votes',
     )

3. Add VotesField and managers to your model:

   ::

     from django.db import models
     from qhonuskan_votes.models import VotesField, ObjectsWithScoresManager, SortByScoresManager

     class MyModel(models.Model):
         votes = VotesField()
         objects = models.Manager()
         objects_with_scores = ObjectsWithScoresManager()
         sort_by_score = SortByScoresManager()
         ...

4. Run migrations:

   ::

     python manage.py migrate

5. Include qhonuskan_votes URLs in your project's urls.py:

   ::

     from django.urls import include, path

     urlpatterns = [
         ...
         path('votes/', include('qhonuskan_votes.urls')),
     ]

6. (Optional) Set the login URL for unauthenticated users:

   In your project's settings.py, you can specify a custom login URL:

   ::

     QHONUSKAN_VOTES_LOGIN_URL = '/accounts/login/'

   If not set, it will default to Django's LOGIN_URL setting.

7. In your view, you can now use:

   ::

     # Regular queryset
     items = MyModel.objects.all()

     # Queryset with vote scores
     items_with_scores = MyModel.objects_with_scores.all()

     # Queryset sorted by vote scores
     items_sorted_by_score = MyModel.sort_by_score.all()

8. In your template, load the required tags and styles:

   ::

     {% load qhonuskan_votes static %}
     {% get_static_prefix as STATIC_PREFIX %}

     <link href="{{ STATIC_PREFIX }}default_buttons.css" rel="stylesheet" type="text/css" />
     {% voting_script user %}

9. Use the vote_buttons_for template tag to create buttons:

   ::

     {% for object in objects %}
       <div class="object">
         {% vote_buttons_for object user %}
         <div class="text">
           {{ object.text }}
         </div>
       </div>
     {% endfor %}

Configuration
-------------

Add the following to your settings.py if you want to use Tailwind CSS for button styling:

.. code-block:: python

    QHONUSKAN_VOTES_USE_TAILWIND = True

Usage
-----

For anonymous voting support, ensure your login view redirects back to the original URL:

.. code-block:: python

    from django.contrib.auth.views import LoginView
    from django.urls import reverse_lazy

    class CustomLoginView(LoginView):
        def get_success_url(self):
            return self.request.GET.get('next') or reverse_lazy('home')

For more detailed information, please refer to the documentation.

Upgrading from Previous Versions
--------------------------------

If you're upgrading from a version prior to 0.3.0, please note the following:

1. Ensure your project is using Django 3.2+ and Python 3.6+.
2. Update your requirements to include the latest version of qhonuskan-votes.
3. Run `python manage.py migrate` to apply any new migrations.
4. Update your JavaScript code if you've customized the voting functionality. The new version uses vanilla JS and the Fetch API instead of jQuery.
5. If you're using custom templates, update them to use the new data attributes instead of the old x: attributes.
6. Review your views and ensure they're compatible with the new managers (ObjectsWithScoresManager and SortByScoresManager).
7. If you were relying on the old `SumWithDefault` in your custom code, replace it with the new `sum_with_default` function from `qhonuskan_votes.utils`.
8. Test your application thoroughly after upgrading, paying special attention to voting functionality and score calculations.

For any issues during upgrade, please refer to the project's issue tracker on GitHub.

Contribution
------------

Contributions are welcome! To contribute:

1. Fork the repository
2. Create a virtual environment and install dependencies:
   ::

     pip install -r requirements/development.txt

3. Make your changes, following PEP8 style guide
4. Write tests for your changes
5. Run the test suite
6. Submit a pull request

Please ensure your code adheres to the project's coding standards and is well-documented.

License
-------

This project is licensed under the GPL License.
