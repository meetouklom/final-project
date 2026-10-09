from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.i18n import set_language
from accounts import views as account_views

urlpatterns = [
    path('admin/er-diagram/', account_views.admin_er_diagram, name='admin_er_diagram'),
    path('admin/er-diagram/image.svg', account_views.admin_er_diagram_image, name='admin_er_diagram_image'),
    path('admin/', admin.site.urls),
    path('', account_views.home, name='home'),
    path('', include('accounts.urls')),
    path('repairs/', include('repairs.urls')),
    path('api/', include('repairs.api_urls')),
    path('i18n/setlang/', set_language, name='set_language'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
