from django.shortcuts import render

# Create your views here.
def login_rider(request):
    return None


def dashboard_rider(request):
    return render(request, 'dashboard-rider.html')