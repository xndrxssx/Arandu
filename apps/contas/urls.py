from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AlunoGestaoViewSet,
    CustomTokenRefreshView,
    EsqueciSenhaView,
    LoginView,
    MeView,
    RedefinirSenhaView,
    TurmaGestaoViewSet,
)

router = DefaultRouter()
router.register(r'gestao/alunos', AlunoGestaoViewSet, basename='gestao-alunos')
router.register(r'gestao/turmas', TurmaGestaoViewSet, basename='gestao-turmas')

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/refresh/', CustomTokenRefreshView.as_view(), name='auth-refresh'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    path('auth/esqueci-senha/', EsqueciSenhaView.as_view(), name='auth-esqueci-senha'),
    path('auth/redefinir-senha/', RedefinirSenhaView.as_view(), name='auth-redefinir-senha'),
    path('', include(router.urls)),
]
