from rest_framework import generics, status, permissions, filters
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
    ResetPasswordSerializer,
    AdminUserSerializer,
    SystemLogSerializer,
    AdminResetPasswordSerializer,
    GlobalSettingSerializer
)
from .models import EmailVerificationToken, PasswordResetToken, SystemLog, GlobalSetting
from .utils.email_service import send_verification_email, send_password_reset_email
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

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
        # Define como inativo até confirmar e-mail
        user.is_active = False
        user.save()
        
        # Cria token de verificação e envia e-mail
        token = EmailVerificationToken.objects.create(
            user=user,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        # Envio assíncrono para evitar timeout no Render
        import threading
        email_thread = threading.Thread(
            target=send_verification_email,
            args=(user, token)
        )
        email_thread.start()
        logger.warning(
            "Thread de email de verificacao iniciada para %s (token=%s)",
            user.email,
            str(token.token)[:8],
        )

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
        user.is_active = True # Ativa a conta
        user.save()

        token.used = True
        token.save()

        # Registra a ação no log
        SystemLog.objects.create(
            user=user,
            action="EMAIL_VERIFIED",
            description=f"E-mail verificado com sucesso via token.",
            admin_name="Sistema"
        )

        # Gera tokens para login automático
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "E-mail verificado com sucesso! Sua conta está ativa.",
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        }, status=status.HTTP_200_OK)

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
                
                # Envio assíncrono para evitar timeout no Render
                import threading
                email_thread = threading.Thread(
                    target=send_password_reset_email,
                    args=(user, token)
                )
                email_thread.start()
                logger.warning(
                    "Thread de email de reset iniciada para %s (token=%s)",
                    user.email,
                    str(token.token)[:8],
                )
            except User.DoesNotExist:
                # Para não revelar emails cadastrados, fingimos sucesso
                logger.warning(
                    "Solicitacao de reset recebida para email nao cadastrado: %s",
                    email,
                )
            
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
        serializer = UserProfileSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    def put(self, request):
        user = request.user
        serializer = UserProfileSerializer(user, data=request.data, partial=True, context={'request': request})
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
        
        # Compatibilidade com frontend que envia key='file'
        if 'file' in request.FILES and 'avatar' not in request.FILES:
            # Cria um novo dict apenas com o arquivo mapeado, evitando copy() do QueryDict
            # que pode falhar com deepcopy em arquivos abertos
            data = {'avatar': request.FILES['file']}
        else:
            data = request.data
            
        serializer = UserAvatarSerializer(user, data=data)
        
        if serializer.is_valid():
            serializer.save()
            user.refresh_from_db() # Garante que temos o estado atualizado do banco/arquivo
            
            if user.avatar:
                # Retorna URL pública
                avatar_url = request.build_absolute_uri(user.avatar.url)
                return Response({"avatar_url": avatar_url}, status=status.HTTP_200_OK)
            else:
                 return Response({"error": "Erro ao salvar arquivo."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
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

# --- Admin Views ---

class AdminUserListView(generics.ListAPIView):
    """
    Lista todos os usuários cadastrados na plataforma.
    Acesso: Apenas administradores (is_staff=True ou role='ADMIN').
    """
    queryset = User.objects.all().order_by('-created_at')
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminUserSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'email']

    def get_queryset(self):
        queryset = User.objects.all().order_by('-created_at')
        show_archived = self.request.query_params.get('show_archived') == 'true'
        role = self.request.query_params.get('role')
        plan = self.request.query_params.get('plan')
        
        if show_archived:
            queryset = queryset.filter(is_active=False)
        else:
            queryset = queryset.filter(is_active=True)

        if role:
            queryset = queryset.filter(role=role)
        if plan:
            queryset = queryset.filter(plan=plan)
            
        return queryset

    def delete(self, request, *args, **kwargs):
        """Exclusão em massa"""
        admin_password = request.data.get('admin_password')
        user_ids = request.data.get('user_ids', [])

        if not admin_password:
            return Response({"detail": "Senha do administrador obrigatória."}, status=status.HTTP_400_BAD_REQUEST)
        
        if not request.user.check_password(admin_password):
            return Response({"detail": "Senha do administrador incorreta."}, status=status.HTTP_403_FORBIDDEN)

        if not user_ids:
            return Response({"detail": "Nenhum usuário selecionado."}, status=status.HTTP_400_BAD_REQUEST)

        # Verificar se está tentando excluir o último admin ou a si mesmo
        users_to_delete = User.objects.filter(id__in=user_ids)
        
        if any(u.id == request.user.id for u in users_to_delete):
             return Response({"detail": "Você não pode excluir sua própria conta em uma ação em massa."}, status=status.HTTP_400_BAD_REQUEST)

        admin_count = User.objects.filter(role='ADMIN').count()
        admins_to_delete = users_to_delete.filter(role='ADMIN').count()
        
        if admin_count - admins_to_delete < 1:
            return Response({"detail": "Ação bloqueada: O sistema deve ter pelo menos um administrador."}, status=status.HTTP_400_BAD_REQUEST)

        users_to_delete.update(is_active=False)
        return Response({"detail": f"{users_to_delete.count()} usuários arquivados com sucesso."}, status=status.HTTP_200_OK)

class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Gerencia um usuário específico. Permite ao admin alterar planos, 
    roles ou desativar contas manualmente.
    Acesso: Apenas administradores.
    """
    queryset = User.objects.all()
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminUserSerializer

    def update(self, request, *args, **kwargs):
        admin_password = request.data.get('admin_password')
        if not admin_password:
            return Response(
                {"detail": "A senha do administrador é obrigatória para esta ação."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not request.user.check_password(admin_password):
            return Response(
                {"detail": "Senha do administrador incorreta."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        old_user = User.objects.get(pk=kwargs.get('pk'))
        response = super().update(request, *args, **kwargs)
        
        if response.status_code == 200:
            new_user = self.get_object()
            changes = []
            if old_user.plan != new_user.plan:
                changes.append(f"Plano alterado de {old_user.plan} para {new_user.plan}")
            if old_user.role != new_user.role:
                changes.append(f"Cargo alterado de {old_user.role} para {new_user.role}")
            if old_user.is_active != new_user.is_active:
                status_str = "Ativado" if new_user.is_active else "Arquivado"
                changes.append(f"Status alterado para {status_str}")
            
            if changes:
                SystemLog.objects.create(
                    user=new_user,
                    action="UPDATE_PROFILE",
                    description="; ".join(changes),
                    admin_name=request.user.name
                )
        
        return response

    def destroy(self, request, *args, **kwargs):
        admin_password = request.data.get('admin_password')
        permanent = request.data.get('permanent') is True
        
        if not admin_password:
            return Response(
                {"detail": "A senha do administrador é obrigatória para esta ação."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not request.user.check_password(admin_password):
            return Response(
                {"detail": "Senha do administrador incorreta."}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        instance = self.get_object()
        
        # Evitar que o admin se arquive/exclua
        if instance.id == request.user.id:
            action = "excluir" if permanent else "arquivar"
            return Response(
                {"detail": f"Você não pode {action} sua própria conta administrativa."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar se é o último admin (ativo ou total conforme a ação)
        if instance.role == 'ADMIN':
            if permanent:
                admin_count = User.objects.filter(role='ADMIN').count()
            else:
                admin_count = User.objects.filter(role='ADMIN', is_active=True).count()
                
            if admin_count <= 1:
                status_type = "cadastrado" if permanent else "ativo"
                return Response(
                    {"detail": f"Ação bloqueada: Este é o último administrador {status_type} do sistema."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if permanent:
            user_email = instance.email
            instance.delete()
            # Log global or related? If deleted, user FK might fail if not null. 
            # But SystemLog user is ForeignKey, so we can't link to deleted user.
            # Maybe use a global log or just skip if hard delete. 
            # For now, let's just log it before delete or use a string if possible.
            # Actually, let's log as "USER_DELETED" with the email in description.
            return Response({"detail": "Usuário excluído permanentemente com sucesso."}, status=status.HTTP_200_OK)
        else:
            instance.is_active = False
            instance.save()
            
            SystemLog.objects.create(
                user=instance,
                action="ARCHIVE_ACCOUNT",
                description=f"Conta arquivada pelo administrador {request.user.name}",
                admin_name=request.user.name
            )
            
            return Response({"detail": "Usuário arquivado com sucesso."}, status=status.HTTP_200_OK)

    def perform_update(self, serializer):
        instance = self.get_object()
        new_role = self.request.data.get('role')
        
        # Impedir que o admin tire o próprio admin
        if instance.id == self.request.user.id and new_role and new_role != 'ADMIN':
             raise permissions.exceptions.PermissionDenied("Você não pode remover seu próprio papel administrativo.")

        # Impedir de demover o último admin
        if instance.role == 'ADMIN' and new_role and new_role != 'ADMIN':
            admin_count = User.objects.filter(role='ADMIN').count()
            if admin_count <= 1:
                raise permissions.exceptions.PermissionDenied("Ação bloqueada: Este é o último administrador do sistema.")

        serializer.save()

class AdminStatsView(APIView):
    """
    Endpoint para fornecer métricas globais da plataforma para o dashboard admin.
    Acesso: Apenas administradores.
    """
    permission_classes = (permissions.IsAdminUser,)

    def get(self, request):
        total_users = User.objects.count()
        premium_users = User.objects.filter(plan__in=['PREMIUM', 'PREMIUM_PLUS']).count()
        
        # Faturamento estimado (simulado com base nos planos)
        # TODO: Integrar com Stripe/Gateway real futuramente
        estimated_revenue = (
            User.objects.filter(plan='PREMIUM').count() * 19.90 +
            User.objects.filter(plan='PREMIUM_PLUS').count() * 39.90
        )

        # Taxa de conversão
        conversion_rate = (premium_users / total_users * 100) if total_users > 0 else 0

        # Usuários recentes para o feed de atividade
        recent_users_query = User.objects.all().order_by('-created_at')[:5]
        recent_users = [{
            "id": str(u.id),
            "name": u.name,
            "email": u.email,
            "created_at": u.created_at
        } for u in recent_users_query]

        # Verificação de saúde real
        import time
        from django.db import connection
        
        db_start = time.time()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db_status = "Conectado"
            db_latency = f"{int((time.time() - db_start) * 1000)}ms"
        except Exception:
            db_status = "Erro"
            db_latency = "N/A"

        return Response({
            "total_users": total_users,
            "premium_users": premium_users,
            "estimated_revenue": estimated_revenue,
            "conversion_rate": round(conversion_rate, 2),
            "recent_users": recent_users,
            "status": "Operacional",
            "db_status": db_status,
            "db_latency": db_latency,
            "api_version": "1.2.5"
        })

class AdminSystemSettingsView(APIView):
    """
    Gerencia configurações globais do sistema (ex: modo manutenção).
    """
    permission_classes = (permissions.IsAdminUser,)

    def get(self, request):
        settings = GlobalSetting.objects.all()
        # Retorna como um dicionário para facilitar no front
        data = {s.key: s.value for s in settings}
        return Response(data)

    def post(self, request):
        # Suporta múltiplos formatos: { "key": "k", "value": "v" } ou { "maintenance_mode": true }
        if 'key' in request.data:
            key = request.data.get('key')
            value = request.data.get('value')
            settings_to_update = {key: value}
        else:
            settings_to_update = request.data

        for key, value in settings_to_update.items():
            str_value = str(value).lower() if isinstance(value, bool) else str(value)
            setting, created = GlobalSetting.objects.update_or_create(
                key=key,
                defaults={'value': str_value}
            )
            
            # Log da ação
            SystemLog.objects.create(
                action="UPDATE_SETTING",
                description=f"Configuração '{key}' atualizada para '{value}'.",
                admin_name=request.user.name
            )
            
        return Response({"message": "Configurações atualizadas com sucesso."})

class AdminGlobalLogsView(generics.ListAPIView):
    """
    Retorna todos os logs do sistema para auditoria global.
    """
    queryset = SystemLog.objects.all().order_by('-timestamp')
    serializer_class = SystemLogSerializer
    permission_classes = (permissions.IsAdminUser,)

class AdminUserFinancialStatsView(APIView):
    """
    Endpoint para fornecer métricas financeiras de um usuário específico.
    Acesso: Apenas administradores.
    """
    permission_classes = (permissions.IsAdminUser,)

    def get(self, request, pk):
        from reports.services import ReportService
        user = get_object_or_404(User, pk=pk)
        stats = ReportService.get_user_financial_stats(user)
        return Response(stats)

class AdminUserLogsView(generics.ListAPIView):
    """
    Retorna os logs de atividade de um usuário específico.
    """
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = SystemLogSerializer
    pagination_class = None

    def get_queryset(self):
        user_id = self.kwargs.get('pk')
        return SystemLog.objects.filter(user_id=user_id).order_by('-timestamp')

class AdminResetPasswordView(APIView):
    """
    Permite que um administrador redefina a senha de um usuário.
    """
    permission_classes = (permissions.IsAdminUser,)

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        serializer = AdminResetPasswordSerializer(data=request.data)
        
        if serializer.is_valid():
            admin_password = serializer.validated_data['admin_password']
            new_password = serializer.validated_data['new_password']
            
            if not request.user.check_password(admin_password):
                return Response({"admin_password": ["Senha do administrador incorreta."]}, status=status.HTTP_403_FORBIDDEN)
            
            user.set_password(new_password)
            user.save()
            
            SystemLog.objects.create(
                user=user,
                action="RESET_PASSWORD",
                description=f"Senha redefinida pelo administrador {request.user.name}",
                admin_name=request.user.name
            )
            
            return Response({"message": "Senha do usuário redefinida com sucesso."}, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminClearUserDataView(APIView):
    """
    Limpa todos os dados financeiros e cadastros (contas, transações, etc.) de um usuário,
    mantendo apenas o seu login, senha e assinatura.
    """
    permission_classes = (permissions.IsAdminUser,)

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        admin_password = request.data.get('admin_password')

        if not admin_password or not request.user.check_password(admin_password):
            return Response({"detail": "Senha do administrador inválida ou não fornecida."}, status=status.HTTP_403_FORBIDDEN)

        try:
            # Apaga dados relacionados explicitamente
            user.transactions.all().delete()
            user.categories.all().delete()
            user.recurring_transactions.all().delete()
            user.tags.all().delete()
            user.focused_monitors.all().delete()
            user.goals.all().delete()
            user.budgets.all().delete()
            user.credit_cards.all().delete()
            user.accounts.all().delete()

            SystemLog.objects.create(
                user=user,
                action="CLEAR_DATA",
                description=f"Todos os dados financeiros e configurações foram limpos pelo administrador {request.user.name}",
                admin_name=request.user.name
            )

            return Response({"message": "Dados do usuário limpos com sucesso."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class AdminHardDeleteView(APIView):
    """
    Exclui um usuário e todos os seus dados permanentemente do banco de dados.
    """
    permission_classes = (permissions.IsAdminUser,)

    def delete(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        admin_password = request.data.get('admin_password')

        if not admin_password or not request.user.check_password(admin_password):
            return Response({"detail": "Senha do administrador inválida ou não fornecida."}, status=status.HTTP_403_FORBIDDEN)

        user_name = user.name
        # Delete user
        user.delete()

        # O user foi excluído, então não podemos referenciá-lo no SystemLog.
        # Vamos usar um campo de texto para registrar o alvo, ou apenas não usar o ForeignKey 'user'
        # ou, se quisermos registrar, precisamos garantir que o SystemLog permita user nulo
        # Mas para o Hard Delete, o mais seguro é não tentar registrar com ForeignKey ou registrar em uma tabela geral.
        # A atual SystemLog tem ForeignKey on_delete=CASCADE, então ao excluir o usuário, seus logs também são excluídos.
        # Portanto, não precisamos (ou não podemos) salvar um log vinculado ao usuário excluído.

        return Response({"message": f"Usuário {user_name} excluído permanentemente."}, status=status.HTTP_200_OK)

# --- System Views ---

def health_check(request):
    """
    Endpoint simples para monitoramento de uptime (Render/Kubernetes).
    """
    return JsonResponse({"status": "ok"})
