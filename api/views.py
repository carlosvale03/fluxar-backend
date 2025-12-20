from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta
from .serializers import (
    UserRegisterSerializer,
    UserProfileSerializer,
    UserAvatarSerializer,
    CustomTokenObtainPairSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer
)
from .models import EmailVerificationToken, PasswordResetToken
from .utils.email_service import send_verification_email, send_password_reset_email

User = get_user_model()

# --- Auth Views ---

class RegisterView(generics.CreateAPIView):
    """
    Endpoint para cadastro de novos usuários.
    Cria usuário e envia e-mail de verificação.
    """
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserRegisterSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        # Cria token de verificação e envia e-mail
        token = EmailVerificationToken.objects.create(
            user=user,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        send_verification_email(user, token)

class CustomLoginView(TokenObtainPairView):
    """
    Login customizado que retorna JWT com dados extras do usuário no payload.
    """
    permission_classes = (permissions.AllowAny,)
    serializer_class = CustomTokenObtainPairSerializer

class VerifyEmailView(APIView):
    """
    Verifica o e-mail do usuário através do token recebido.
    """
    permission_classes = (permissions.AllowAny,)

    def get(self, request):
        token_str = request.query_params.get('token')
        if not token_str:
            return Response({"error": "Token não fornecido."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = EmailVerificationToken.objects.get(token=token_str)
        except EmailVerificationToken.DoesNotExist:
             return Response({"error": "Token inválido."}, status=status.HTTP_400_BAD_REQUEST)

        if not token.is_valid():
            return Response({"error": "Token expirado ou já utilizado."}, status=status.HTTP_400_BAD_REQUEST)

        # Atualiza usuário e token
        user = token.user
        user.email_verified = True
        user.save()

        token.used = True
        token.save()

        return Response({"message": "E-mail verificado com sucesso!"}, status=status.HTTP_200_OK)

class ForgotPasswordView(APIView):
    """
    Solicita redefinição de senha (envia link por e-mail).
    """
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                # Invalida tokens anteriores não usados (opcional, mas boa prática)
                PasswordResetToken.objects.filter(user=user, used=False).update(used=True)

                token = PasswordResetToken.objects.create(
                    user=user,
                    expires_at=timezone.now() + timedelta(hours=1)
                )
                send_password_reset_email(user, token)
            except User.DoesNotExist:
                # Para não revelar emails cadastrados, fingimos sucesso
                pass
            
            return Response({"message": "Se o e-mail existir, um link de recuperação foi enviado."}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResetPasswordView(APIView):
    """
    Redefine a senha usando o token recebido.
    """
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            token_str = serializer.validated_data['token']
            new_password = serializer.validated_data['new_password']

            try:
                token = PasswordResetToken.objects.get(token=token_str)
            except PasswordResetToken.DoesNotExist:
                return Response({"token": ["Token inválido."]}, status=status.HTTP_400_BAD_REQUEST)

            if not token.is_valid():
                return Response({"token": ["Token expirado ou já utilizado."]}, status=status.HTTP_400_BAD_REQUEST)

            # Redefine senha
            user = token.user
            user.set_password(new_password)
            user.save()

            # Invalida token
            token.used = True
            token.save()

            return Response({"message": "Senha redefinida com sucesso."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MeView(APIView):
    """
    Gerencia o perfil do usuário logado.
    GET: Retorna dados do usuário.
    PUT: Atualiza dados permitidos (nome, avatar).
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        user = request.user
        serializer = UserProfileSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        return self.put(request)

class UserAvatarView(APIView):
    """
    Endpoint para upload de avatar do usuário.
    POST: Recebe arquivo multipart e salva no perfil.
    """
    permission_classes = (permissions.IsAuthenticated,)
    
    def post(self, request):
        user = request.user
        serializer = UserAvatarSerializer(user, data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            # Retorna URL pública
            avatar_url = request.build_absolute_uri(user.avatar.url)
            return Response({"avatar_url": avatar_url}, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(APIView):
    """
    Permite que usuário logado altere sua senha.
    Exige a senha atual para segurança.
    """
    permission_classes = (permissions.IsAuthenticated,)

    def put(self, request):
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data)

        if serializer.is_valid():
            # Verifica se a senha atual está correta
            if not user.check_password(serializer.data.get("current_password")):
                return Response({"current_password": ["Senha incorreta."]}, status=status.HTTP_400_BAD_REQUEST)

            # Define a nova senha e salva
            user.set_password(serializer.data.get("new_password"))
            user.save()
            return Response({"message": "Senha atualizada com sucesso."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# --- System Views ---

def health_check(request):
    """
    Endpoint simples para monitoramento de uptime (Render/Kubernetes).
    """
    return JsonResponse({"status": "ok"})
