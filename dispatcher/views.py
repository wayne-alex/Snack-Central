from django.shortcuts import render


# Create your views here.
def login_dispatcher(request):
    return render(request, 'login.html')


def dashboard_dispatcher(request):
    return render(request, 'dashboard-dispatcher.html')
