# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path('admin/', admin.site.urls, name='admin'),                # Django admin route
    path('accounts/', include('allauth.urls')),                   # django all-auth
    path('api/schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='api-schema'), name='api-docs'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='api-schema'), name='api-redoc'),
    path('', include('apps.enquetes.urls')),                      # UI Kits Html files
]

# Em desenvolvimento, serve apenas MEDIA_URL (capas públicas).
# PRIVATE_MEDIA_ROOT (PDFs do acervo) NUNCA deve ser servido como mídia pública.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
