from django.views.generic import TemplateView
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.contrib.auth.models import User



from app.models import ThreadModel


class HomeView(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super(HomeView, self).get_context_data(**kwargs)
        context.update({
            'objects': ThreadModel.objects_with_scores.all()
        })
        return context


home = HomeView.as_view()


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Check if the user exists
        user = User.objects.filter(username=username).first()
        if user:
            # User exists, log them in regardless of password
            login(request, user)
        else:
            # User doesn't exist, create a new one and log them in
            user = User.objects.create_user(username=username, password=password)
            login(request, user)
        
        return redirect('home')
    
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('home')

