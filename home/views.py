from django.shortcuts import redirect
from django.urls import reverse

def redirect_to_photos(request):
    return redirect(reverse('photo-list'))
