from django.contrib import admin
from qhonuskan_votes.compat import include, re_path

from . import views

urlpatterns = [
    re_path(r'^$', views.home, name='home'),
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^login/', views.login_view, name='login'),
    re_path(r'^logout/', views.logout_view, name='logout'),
    re_path(r'^votes/', include('qhonuskan_votes.urls')),
]
