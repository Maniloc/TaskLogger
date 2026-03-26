from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path
from django.contrib.auth import views as auth_views
from django.views.static import serve as static_serve
from django.contrib.staticfiles.views import serve as dev_serve

def sw_view(request):
    """Serve service worker from root scope (critical for Push API)."""
    import os
    from django.http import HttpResponse, Http404
    from django.contrib.staticfiles import finders
    sw_path = finders.find('projects/sw.js')
    if not sw_path:
        raise Http404
    with open(sw_path, 'rb') as f:
        content = f.read()
    return HttpResponse(content, content_type='application/javascript')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('sw.js', sw_view, name='service_worker'),
    path('login/', auth_views.LoginView.as_view(template_name='projects/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('projects.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
