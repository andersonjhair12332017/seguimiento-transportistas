from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # App principal
    path("", include("operaciones.urls")),

    # Rutas de autenticación de Django
    path("accounts/", include("django.contrib.auth.urls")),

    # Logout directo
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]