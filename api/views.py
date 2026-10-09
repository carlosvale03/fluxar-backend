from rest_framework import exceptions, generics, serializers, status, permissions, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from datetime import timedelta
from decimal import Decimal
import uuid
from .serializers import (
    EMAIL_JA_CADASTRADO,
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
    GlobalSettingSerializer,
    AlteracaoDePlanoSerializer,
)
from .models import EmailVerificationToken, PasswordResetToken, SystemLog, GlobalSetting, TravaDePlano
from .cookies import (
    NOME_DO_COOKIE,
    apagar_cookie_de_renovacao,
    gravar_cookie_de_renovacao,
    origem_permitida,
)
from .sessoes import SessaoInvalida, criar_sessao, encerrar, encerrar_outras, encerrar_todas, renovar, sid_do_token
from core.throttles import (
    CadastroIPThrottle,
    EsqueciSenhaEmailThrottle,
    EsqueciSenhaIPThrottle,
    LinkIPThrottle,
    LoginFalhasEmailThrottle,
    LoginIPThrottle,
    ReenvioEmailThrottle,
    ReenvioIPThrottle,
)
from .utils.email_service import (
    _mask_email,
    send_account_deletion_email,
    send_password_reset_email,
    send_verification_email,
)
from core.manutencao import invalidar as invalidar_manutencao, manutencao_ligada
from core.filtros import PAGINACAO, ParametrosConhecidosMixin
from core.permissions import EhAdministrador
from core import travas
from core.pagination import PaginacaoPadrao
from core.valores import dinheiro
from core.uploads import com_nome_aleatorio
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class SemTransacaoPorRequisicao:
    """
    Deixa a rota fora do ATOMIC_REQUESTS (SALDO-10). Serve às rotas com limite
    de tentativas: os contadores moram no cache do banco, e o rollback de uma
    tentativa recusada apagaria a contagem (AUTH-31 a AUTH-35).
    """

    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def handle_exception(self, exc):
        # Ao tratar o erro, o DRF marca para rollback o bloco atomic mais
        # interno; este bloco vazio recebe a marca, e nada do que a rota já
        # gravou, como os contadores, é desfeito
        with transaction.atomic():
            return super().handle_exception(exc)

# --- Auth Views ---

class RegisterView(SemTransacaoPorRequisicao, generics.CreateAPIView):
    """
    Endpoint para cadastro de novos usuários.
    Cria usuário e envia e-mail de verificação.
    """
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    # Rota pública: um token vencido ou malformado não gera 401 (AUTH-40)
    authentication_classes = ()
    throttle_classes = (CadastroIPThrottle,)
    serializer_class = UserRegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # A conta nasce pendente: email_verified=False e is_active=True (AD-035)
        try:
            with transaction.atomic():
                user = serializer.save()
                token = EmailVerificationToken.objects.create(
                    user=user,
                    expires_at=timezone.now() + timedelta(hours=24)
                )
        except IntegrityError:
            # Outro cadastro gravou o mesmo e-mail depois da validação (AUTH-06)
            return Response({"email": [EMAIL_JA_CADASTRADO]}, status=status.HTTP_400_BAD_REQUEST)

        # Envio na própria requisição; a falha não desfaz o cadastro (AD-011)
        email_sent = send_verification_email(user, token)
        if email_sent:
            message = "Conta criada. Enviamos um link de verificação para o seu e-mail."
        else:
            message = (
                'Conta criada, mas não conseguimos enviar o e-mail de verificação. '
                'Use "Reenviar e-mail".'
            )
        return Response({"message": message, "email_sent": email_sent}, status=status.HTTP_201_CREATED)

class CustomLoginView(SemTransacaoPorRequisicao, TokenObtainPairView):
    """
    Login customizado que retorna JWT com dados extras do usuário no payload.
    """
    permission_classes = (permissions.AllowAny,)
    # Rota pública: um token vencido ou malformado não gera 401 (AUTH-40)
    authentication_classes = ()
    throttle_classes = (LoginIPThrottle, LoginFalhasEmailThrottle)
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        # O acesso fica no corpo e a renovação só no cookie httpOnly (SESSAO-01)
        response = super().post(request, *args, **kwargs)
        gravar_cookie_de_renovacao(response, response.data.pop('refresh'))
        return response

ORIGEM_RECUSADA = {"detail": "Origem não permitida.", "code": "origin_not_allowed"}
SESSAO_EXPIRADA = {"detail": "Sessão expirada. Entre de novo.", "code": "session_expired"}

class RenovarSessaoView(APIView):
    """
    Renova a sessão pelo cookie, com rotação do token de renovação
    (SESSAO-04, SESSAO-08 e SESSAO-09).
    """
    permission_classes = (permissions.AllowAny,)
    # O token de acesso pode estar vencido; quem vale aqui é o cookie
    authentication_classes = ()

    def post(self, request):
        if not origem_permitida(request):
            return Response(ORIGEM_RECUSADA, status=status.HTTP_403_FORBIDDEN)
        try:
            access, refresh = renovar(request.COOKIES.get(NOME_DO_COOKIE))
        except SessaoInvalida:
            response = Response(SESSAO_EXPIRADA, status=status.HTTP_401_UNAUTHORIZED)
            apagar_cookie_de_renovacao(response)
            return response
        response = Response({"access": access}, status=status.HTTP_200_OK)
        gravar_cookie_de_renovacao(response, refresh)
        return response

class LogoutView(APIView):
    """
    Encerra a sessão do cookie e apaga o cookie (SESSAO-04 e SESSAO-13).
    Responde 204 também sem cookie, para o logout ser idempotente.
    """
    permission_classes = (permissions.AllowAny,)
    # O token de acesso pode estar vencido; quem vale aqui é o cookie
    authentication_classes = ()

    def post(self, request):
        if not origem_permitida(request):
            return Response(ORIGEM_RECUSADA, status=status.HTTP_403_FORBIDDEN)
        sid = sid_do_token(request.COOKIES.get(NOME_DO_COOKIE))
        if sid:
            encerrar(sid)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        apagar_cookie_de_renovacao(response)
        return response

class VerifyEmailView(ParametrosConhecidosMixin, SemTransacaoPorRequisicao, APIView):
    """
    Verifica o e-mail do usuário através do token recebido.
    """
    permission_classes = (permissions.AllowAny,)
    # Rota pública: um token vencido ou malformado não gera 401 (AUTH-40)
    authentication_classes = ()
    throttle_classes = (LinkIPThrottle,)
    # O link de verificação traz o token (CONTRATO-14)
    parametros_permitidos = frozenset({'token'})

    @staticmethod
    def _token_valido(token_str):
        """
        Devolve o token só se ele existir, não tiver sido usado, não tiver
        vencido e for o mais recente do usuário (AUTH-09).
        """
        if not token_str:
            return None
        try:
            uuid.UUID(str(token_str))
        except ValueError:
            return None
        token = EmailVerificationToken.objects.filter(token=token_str).select_related('user').first()
        if token is None or not token.is_valid():
            return None
        mais_recente = (
            EmailVerificationToken.objects.filter(user=token.user).order_by('-created_at', '-pk').first()
        )
        if mais_recente.pk != token.pk:
            return None
        return token

    def get(self, request):
        token = self._token_valido(request.query_params.get('token'))
        if token is None:
            return Response(
                {"detail": "Link inválido ou expirado.", "code": "invalid_link"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Confirma o e-mail sem mexer em is_active: uma conta desativada pelo
        # administrador continua desativada (AD-035)
        # O link vale uma vez só, mesmo com duas aberturas simultâneas
        if not EmailVerificationToken.objects.filter(pk=token.pk, used=False).update(used=True):
            return Response(
                {"detail": "Link inválido ou expirado.", "code": "invalid_link"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = token.user
        user.email_verified = True
        user.save(update_fields=['email_verified'])

        # Registra a ação no log
        SystemLog.objects.create(
            user=user,
            action="EMAIL_VERIFIED",
            description=f"E-mail verificado com sucesso via token.",
            admin_name="Sistema"
        )

        if not user.is_active:
            # SPEC_DEVIATION: a spec não define a verificação de uma conta desativada.
            # Reason: devolver tokens daria sessão a uma conta que o administrador
            # desativou; a resposta usa a mesma mensagem do login (AUTH-16).
            return Response(
                {"detail": "Esta conta está desativada.", "code": "account_disabled"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Abre a sessão para o login automático: o acesso no corpo e a
        # renovação só no cookie httpOnly (SESSAO-01)
        access, refresh = criar_sessao(user)
        response = Response({
            "message": "E-mail verificado com sucesso! Sua conta está ativa.",
            "access": access,
        }, status=status.HTTP_200_OK)
        gravar_cookie_de_renovacao(response, refresh)
        return response

class ResendVerificationView(SemTransacaoPorRequisicao, APIView):
    """
    Envia um novo link de verificação para uma conta pendente.
    A resposta é sempre a mesma, exista ou não a conta (AUTH-11).
    """
    permission_classes = (permissions.AllowAny,)
    # Rota pública: um token vencido ou malformado não gera 401 (AUTH-40)
    authentication_classes = ()
    throttle_classes = (ReenvioIPThrottle, ReenvioEmailThrottle)

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = User.objects.get_by_natural_key(serializer.validated_data['email'])
        except User.DoesNotExist:
            user = None

        # Pendente é e-mail não verificado numa conta ativa (AD-035)
        if user is not None and user.is_active and not user.email_verified:
            with transaction.atomic():
                EmailVerificationToken.objects.filter(user=user, used=False).update(used=True)
                token = EmailVerificationToken.objects.create(
                    user=user,
                    expires_at=timezone.now() + timedelta(hours=24)
                )
            # A falha no envio fica no log do serviço de e-mail; a resposta não muda
            send_verification_email(user, token)

        return Response(
            {"message": "Se houver uma conta aguardando verificação com este e-mail, enviamos um novo link."},
            status=status.HTTP_200_OK,
        )

class ForgotPasswordView(SemTransacaoPorRequisicao, APIView):
    """
    Envia um link de redefinição de senha. A resposta é sempre a mesma,
    exista ou não a conta, e mesmo quando o envio falha (AUTH-18, AUTH-27).
    """
    permission_classes = (permissions.AllowAny,)
    # Rota pública: um token vencido ou malformado não gera 401 (AUTH-40)
    authentication_classes = ()
    throttle_classes = (EsqueciSenhaIPThrottle, EsqueciSenhaEmailThrottle)

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = User.objects.get_by_natural_key(serializer.validated_data['email'])
        except User.DoesNotExist:
            user = None

        # Vale também para a conta desativada; a redefinição não a reativa (AUTH-20)
        if user is not None:
            with transaction.atomic():
                PasswordResetToken.objects.filter(user=user, used=False).update(used=True)
                token = PasswordResetToken.objects.create(
                    user=user,
                    expires_at=timezone.now() + timedelta(hours=1)
                )
            # Envio na própria requisição (AD-011)
            if not send_password_reset_email(user, token):
                logger.warning(
                    "Redefinição de senha não enviada destinatario=%s", _mask_email(user.email),
                )

        return Response(
            {"message": "Se o e-mail estiver cadastrado, enviamos um link para redefinir a senha."},
            status=status.HTTP_200_OK,
        )

class ResetPasswordView(SemTransacaoPorRequisicao, APIView):
    """
    Redefine a senha com um link de redefinição válido (AUTH-20 a AUTH-22).
    """
    permission_classes = (permissions.AllowAny,)
    # Rota pública: um token vencido ou malformado não gera 401 (AUTH-40)
    authentication_classes = ()
    throttle_classes = (LinkIPThrottle,)

    LINK_INVALIDO = {"detail": "Link inválido ou expirado.", "code": "invalid_link"}

    @staticmethod
    def _token_valido(token_str):
        """Devolve o token só se ele existir, não tiver sido usado e não tiver vencido."""
        try:
            valor = uuid.UUID(str(token_str))
        except ValueError:
            return None
        token = PasswordResetToken.objects.filter(token=valor).select_related('user').first()
        if token is None or not token.is_valid():
            return None
        return token

    def post(self, request):
        token = self._token_valido(request.data.get('token'))
        if token is None:
            return Response(self.LINK_INVALIDO, status=status.HTTP_400_BAD_REQUEST)

        user = token.user
        serializer = ResetPasswordSerializer(data=request.data, context={'user': user})
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            # Marca o uso só se ninguém o marcou antes, para o link valer uma vez
            if not PasswordResetToken.objects.filter(pk=token.pk, used=False).update(used=True):
                return Response(self.LINK_INVALIDO, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(serializer.validated_data['new_password'])
            # Confirma o e-mail sem mexer em is_active: a conta desativada
            # continua desativada (AUTH-20, AD-035)
            user.email_verified = True
            user.save(update_fields=['password', 'email_verified'])
            # A senha nova derruba todas as sessões abertas (SESSAO-16)
            encerrar_todas(user)

        return Response({"message": "Senha redefinida com sucesso."}, status=status.HTTP_200_OK)

class MeView(ParametrosConhecidosMixin, APIView):
    """
    Gerencia o perfil do usuário logado.
    GET: Retorna dados do usuário.
    PUT: Atualiza dados permitidos (nome, avatar).
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        # Com o acesso do usuário aos recursos e limites do plano (PERM-17)
        serializer = UserProfileSerializer(request.user, context={'request': request, 'com_acesso': True})
        return Response(serializer.data)

    def put(self, request):
        user = request.user
        serializer = UserProfileSerializer(
            user, data=request.data, partial=True, context={'request': request, 'com_acesso': True},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        return self.put(request)

class PlansView(ParametrosConhecidosMixin, APIView):
    """
    Página de planos (PERM-27): o que cada plano libera, pela configuração
    atual, e o plano do usuário. Exige login, mas não exige ser admin.
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        return Response({
            "plan": request.user.plan,
            "catalog": travas.catalogo_com_valores(travas.configuracao()),
        })

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
        # Vai ao Cloudinary com nome aleatório, sem o nome original (LGPD-20)
        com_nome_aleatorio(data.get('avatar'))

        serializer = UserAvatarSerializer(user, data=data)
        
        if serializer.is_valid():
            serializer.save()
            user.refresh_from_db() # Garante que temos o estado atualizado do banco/arquivo
            
            if user.avatar:
                # Retorna URL pública
                avatar_url = request.build_absolute_uri(user.avatar.url)
                return Response({"avatar_url": avatar_url}, status=status.HTTP_200_OK)
            else:
                # Erro no formato do DRF, em português (CONTRATO-29)
                raise exceptions.APIException('Não foi possível salvar o arquivo.')
            
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
            # Derruba as outras sessões e mantém a atual (SESSAO-15)
            encerrar_outras(user, request.auth.get('sid'))
            return Response({"message": "Senha atualizada com sucesso."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

PRAZO_PARA_DESISTIR = timedelta(days=30)
SENHA_OBRIGATORIA = "Este campo é obrigatório."


def _data_na_api(valor):
    """Data e hora no mesmo formato ISO dos serializers."""
    return serializers.DateTimeField().to_representation(valor)


class PedidoDeExclusaoView(APIView):
    """
    O usuário pede a exclusão da própria conta, confirmando a senha atual
    (LGPD-03 a LGPD-06, LGPD-09, AD-018).

    A conta é desativada na hora, perde todas as sessões e fica marcada para
    a exclusão definitiva 30 dias depois. O e-mail com a data sai na própria
    requisição, e a falha no envio não desfaz o pedido (AD-011).
    """
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        user = request.user
        senha = request.data.get('password')
        if not isinstance(senha, str) or not senha:
            return Response({"password": [SENHA_OBRIGATORIA]}, status=status.HTTP_400_BAD_REQUEST)
        if not user.check_password(senha):
            return Response({"password": ["Senha incorreta."]}, status=status.HTTP_400_BAD_REQUEST)
        # O último administrador ativo não sai (LGPD-09)
        garantir_admin_restante([user])

        agora = timezone.now()
        user.is_active = False
        user.exclusao_pedida_em = agora
        user.exclusao_agendada_para = agora + PRAZO_PARA_DESISTIR
        user.save(update_fields=['is_active', 'exclusao_pedida_em', 'exclusao_agendada_para'])
        # Desconecta todos os aparelhos (LGPD-05, SESSAO-17)
        encerrar_todas(user)

        email_sent = send_account_deletion_email(user, user.exclusao_agendada_para)
        if not email_sent:
            logger.warning("Aviso de exclusão não enviado destinatario=%s", _mask_email(user.email))

        return Response({
            "deletion_scheduled_for": _data_na_api(user.exclusao_agendada_para),
            "email_sent": email_sent,
        }, status=status.HTTP_200_OK)

# --- Admin Views ---

ULTIMO_ADMIN = "O sistema precisa ter pelo menos um administrador ativo."
PROPRIA_CONTA = (
    "Você não pode remover o próprio acesso de administrador nem arquivar ou excluir "
    "a própria conta pelo painel."
)


class AcaoDeAdminRecusada(exceptions.APIException):
    """HTTP 400 com `detail` e `code` (PERM-05, PERM-06)."""
    status_code = status.HTTP_400_BAD_REQUEST


def garantir_admin_restante(afetados):
    """
    Recusa com 400 quando tirar o papel, arquivar ou excluir os usuários
    `afetados` deixaria o sistema sem nenhum administrador ativo (PERM-05).

    Trava os administradores ativos até o fim da requisição, para duas
    mudanças simultâneas não rebaixarem os dois últimos.
    """
    ids = {u.pk for u in afetados if u.role == 'ADMIN' and u.is_active}
    if not ids:
        return
    ativos = set(
        User.objects.select_for_update().filter(role='ADMIN', is_active=True).values_list('pk', flat=True)
    )
    if not ativos - ids:
        raise AcaoDeAdminRecusada(ULTIMO_ADMIN, code='last_admin')


def recusar_a_propria_conta(request, afetados):
    """
    O administrador não tira o próprio papel nem arquiva ou exclui a própria
    conta pelo painel (PERM-06). Conferido depois de `garantir_admin_restante`,
    porque o último administrador só é afetado por uma ação sobre si mesmo.
    """
    if any(u.pk == request.user.pk for u in afetados):
        raise AcaoDeAdminRecusada(PROPRIA_CONTA, code='own_account')


def recusar_remocao_de_admin(request, afetados):
    """As duas regras da remoção de um administrador, na ordem (PERM-05, PERM-06)."""
    garantir_admin_restante(afetados)
    recusar_a_propria_conta(request, afetados)

class AdminUserListView(ParametrosConhecidosMixin, generics.ListAPIView):
    """
    Lista todos os usuários cadastrados na plataforma.
    Acesso: só administradores, pelo papel (PERM-02).
    """
    queryset = User.objects.all().order_by('-created_at')
    permission_classes = (EhAdministrador,)
    serializer_class = AdminUserSerializer
    # Lista paginada (CONTRATO-02, AD-021)
    pagination_class = PaginacaoPadrao
    # Parâmetros conhecidos da lista (CONTRATO-14)
    parametros_permitidos = PAGINACAO | {'search', 'show_archived', 'role', 'plan'}
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

        # Nem o último administrador ativo nem a própria conta (PERM-05, PERM-06)
        users_to_delete = User.objects.filter(id__in=user_ids)
        recusar_remocao_de_admin(request, users_to_delete)

        users_to_delete.update(is_active=False)
        # A conta arquivada perde as sessões abertas (SESSAO-17)
        for user in users_to_delete:
            encerrar_todas(user)
        return Response({"detail": f"{users_to_delete.count()} usuários arquivados com sucesso."}, status=status.HTTP_200_OK)

class AdminUserDetailView(ParametrosConhecidosMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    Gerencia um usuário específico. Permite ao admin alterar planos, 
    roles ou desativar contas manualmente.
    Acesso: Apenas administradores.
    """
    queryset = User.objects.all()
    permission_classes = (EhAdministrador,)
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
            # A conta desativada perde as sessões abertas (SESSAO-17)
            if not new_user.is_active:
                encerrar_todas(new_user)
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
                    admin_name=_mask_email(request.user.email)
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
        # Nem o último administrador ativo nem a própria conta (PERM-05, PERM-06)
        recusar_remocao_de_admin(request, [instance])

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
            # A conta arquivada perde as sessões abertas; na exclusão, elas
            # são apagadas em cascata com a conta (SESSAO-17)
            encerrar_todas(instance)
            
            SystemLog.objects.create(
                user=instance,
                action="ARCHIVE_ACCOUNT",
                description="Conta arquivada pelo administrador.",
                admin_name=_mask_email(request.user.email)
            )
            
            return Response({"detail": "Usuário arquivado com sucesso."}, status=status.HTTP_200_OK)

    def perform_update(self, serializer):
        instance = serializer.instance
        dados = serializer.validated_data
        # Tirar o papel ou desativar a conta de um administrador (PERM-05, PERM-06)
        perde_o_acesso = dados.get('role', instance.role) != 'ADMIN' or not dados.get('is_active', instance.is_active)
        if perde_o_acesso:
            recusar_remocao_de_admin(self.request, [instance])

        serializer.save()

class AdminStatsView(ParametrosConhecidosMixin, APIView):
    """
    Endpoint para fornecer métricas globais da plataforma para o dashboard admin.
    Acesso: Apenas administradores.
    """
    permission_classes = (EhAdministrador,)

    def get(self, request):
        total_users = User.objects.count()
        premium_users = User.objects.filter(plan__in=['PREMIUM', 'PREMIUM_PLUS']).count()
        
        # Faturamento estimado (simulado com base nos planos)
        # TODO: Integrar com Stripe/Gateway real futuramente
        # Em Decimal e como texto na resposta (CONTRATO-16)
        estimated_revenue = (
            User.objects.filter(plan='PREMIUM').count() * Decimal('19.90') +
            User.objects.filter(plan='PREMIUM_PLUS').count() * Decimal('39.90')
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
            "estimated_revenue": dinheiro(estimated_revenue),
            "conversion_rate": round(conversion_rate, 2),
            "recent_users": recent_users,
            "status": "Operacional",
            "db_status": db_status,
            "db_latency": db_latency,
            "api_version": "1.2.5"
        })

class AdminSystemSettingsView(ParametrosConhecidosMixin, APIView):
    """
    Gerencia configurações globais do sistema (ex: modo manutenção).
    """
    permission_classes = (EhAdministrador,)

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

        # A liberação para testes muda só pela rota dos planos, que grava o
        # log com os valores antigo e novo (PERM-13)
        if 'testing_unlock' in settings_to_update:
            return Response(
                {"testing_unlock": ["A liberação para testes muda só em /api/admin/plans/."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
                admin_name=_mask_email(request.user.email)
            )

        invalidar_manutencao()
        return Response({"message": "Configurações atualizadas com sucesso."})

def _texto_da_trava(chave, valor):
    """O valor de uma trava como aparece no log."""
    if travas.CATALOGO[chave].tipo == travas.RECURSO:
        return 'liberado' if valor is not False else 'bloqueado'
    return 'sem limite' if valor is None else str(valor)


class AdminPlansView(ParametrosConhecidosMixin, APIView):
    """
    Configuração das travas dos planos e da liberação para testes
    (PERM-10 a PERM-13, PERM-24).

    GET devolve o catálogo com o valor de cada plano, lido do banco e não do
    cache. PATCH grava uma mudança, registra no log só quando o valor muda e
    chama `travas.invalidar()`, para valer na requisição seguinte; os outros
    processos veem a mudança em até 30 segundos.
    """
    permission_classes = (EhAdministrador,)

    def resposta(self):
        config = travas.ler_configuracao()
        return Response({
            "testing_unlock": config.testing_unlock,
            "catalog": travas.catalogo_com_valores(config),
        })

    def get(self, request):
        return self.resposta()

    def patch(self, request):
        serializer = AlteracaoDePlanoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        if 'testing_unlock' in dados:
            self.gravar_liberacao(request, dados['testing_unlock'])
        else:
            self.gravar_trava(request, dados)
        travas.invalidar()
        return self.resposta()

    def gravar_liberacao(self, request, ligada):
        setting, _ = GlobalSetting.objects.get_or_create(key='testing_unlock', defaults={'value': 'true'})
        setting = GlobalSetting.objects.select_for_update().get(pk=setting.pk)
        antes = travas.liberacao_ligada(setting.value)
        if antes == ligada:
            return
        setting.value = 'true' if ligada else 'false'
        setting.save(update_fields=['value', 'updated_at'])
        texto = {True: 'ligada', False: 'desligada'}
        SystemLog.objects.create(
            action="UPDATE_TESTING_UNLOCK",
            description=f"Liberação para testes: {texto[antes]} -> {texto[ligada]}.",
            admin_name=_mask_email(request.user.email),
        )

    def gravar_trava(self, request, dados):
        chave, plano = dados['key'], dados['plan']
        recurso = travas.CATALOGO[chave].tipo == travas.RECURSO
        # Sem a linha, os campos nulos valem liberado e sem limite (AD-044)
        linha, _ = TravaDePlano.objects.get_or_create(chave=chave, plano=plano)
        # Trava a linha: com dois admins ao mesmo tempo, vale a última
        # gravação e as duas ficam no log com o valor certo (PERM-13)
        linha = TravaDePlano.objects.select_for_update().get(pk=linha.pk)
        if recurso:
            antes, depois = linha.liberado is not False, dados['enabled']
        else:
            antes, depois = linha.limite, dados['limit']
        if antes == depois:
            return
        if recurso:
            linha.liberado = depois
        else:
            linha.limite = depois
        linha.atualizada_por = request.user
        linha.save()
        SystemLog.objects.create(
            action="UPDATE_PLAN_LOCK",
            description=(
                f"Trava '{chave}' no plano {plano}: "
                f"{_texto_da_trava(chave, antes)} -> {_texto_da_trava(chave, depois)}."
            ),
            admin_name=_mask_email(request.user.email),
        )


class AdminGlobalLogsView(ParametrosConhecidosMixin, generics.ListAPIView):
    """
    Retorna todos os logs do sistema para auditoria global.
    """
    queryset = SystemLog.objects.all().order_by('-timestamp')
    serializer_class = SystemLogSerializer
    permission_classes = (EhAdministrador,)
    # Lista paginada (CONTRATO-02, AD-021)
    pagination_class = PaginacaoPadrao
    parametros_permitidos = PAGINACAO

class AdminUserFinancialStatsView(ParametrosConhecidosMixin, APIView):
    """
    Endpoint para fornecer métricas financeiras de um usuário específico.
    Acesso: Apenas administradores.
    """
    permission_classes = (EhAdministrador,)

    def get(self, request, pk):
        from reports.services import ReportService
        user = get_object_or_404(User, pk=pk)
        stats = ReportService.get_user_financial_stats(user)
        return Response(stats)

class AdminUserLogsView(ParametrosConhecidosMixin, generics.ListAPIView):
    """
    Retorna os logs de atividade de um usuário específico.
    """
    permission_classes = (EhAdministrador,)
    serializer_class = SystemLogSerializer
    # Lista paginada (CONTRATO-02, AD-021)
    pagination_class = PaginacaoPadrao
    parametros_permitidos = PAGINACAO

    def get_queryset(self):
        user_id = self.kwargs.get('pk')
        # Pelo id interno, que continua no registro depois da exclusão (AD-030)
        return SystemLog.objects.filter(usuario_ref=user_id).order_by('-timestamp')

class AdminResetPasswordView(APIView):
    """
    Permite que um administrador redefina a senha de um usuário.
    """
    permission_classes = (EhAdministrador,)

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
            # A senha nova derruba todas as sessões do usuário (SESSAO-16)
            encerrar_todas(user)
            
            SystemLog.objects.create(
                user=user,
                action="RESET_PASSWORD",
                description="Senha redefinida pelo administrador.",
                admin_name=_mask_email(request.user.email)
            )
            
            return Response({"message": "Senha do usuário redefinida com sucesso."}, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminClearUserDataView(APIView):
    """
    Limpa todos os dados financeiros e cadastros (contas, transações, etc.) de um usuário,
    mantendo apenas o seu login, senha e assinatura.
    """
    permission_classes = (EhAdministrador,)

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        admin_password = request.data.get('admin_password')

        if not admin_password or not request.user.check_password(admin_password):
            return Response({"detail": "Senha do administrador inválida ou não fornecida."}, status=status.HTTP_403_FORBIDDEN)

        # Erro inesperado sobe e vira 500, sem o texto da exceção (CONTRATO-29)
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
            description="Todos os dados financeiros e configurações foram limpos pelo administrador.",
            admin_name=_mask_email(request.user.email)
        )

        return Response({"message": "Dados do usuário limpos com sucesso."}, status=status.HTTP_200_OK)

class AdminHardDeleteView(APIView):
    """
    Exclui um usuário e todos os seus dados permanentemente do banco de dados.
    """
    permission_classes = (EhAdministrador,)

    def delete(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        admin_password = request.data.get('admin_password')

        if not admin_password or not request.user.check_password(admin_password):
            return Response({"detail": "Senha do administrador inválida ou não fornecida."}, status=status.HTTP_403_FORBIDDEN)

        # Nem o último administrador ativo nem a própria conta (PERM-05, PERM-06)
        recusar_remocao_de_admin(request, [user])

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

# Sem transação de banco por requisição: o health responde mesmo sem acesso
# ao banco (SESSAO-23), e o ATOMIC_REQUESTS abriria a conexão antes da view
@transaction.non_atomic_requests
def health_check(request):
    """
    Endpoint simples para monitoramento de uptime (Render/Kubernetes).

    Responde 200 enquanto a aplicação estiver no ar, com ou sem manutenção
    (SESSAO-23). A página de manutenção lê o `maintenance` para voltar sozinha.
    """
    try:
        em_manutencao = manutencao_ligada()
    except DatabaseError as erro:
        # Só o tipo do erro: a mensagem do banco pode trazer o endereço dele
        logger.error("Health check sem acesso ao banco (%s).", type(erro).__name__)
        # Estado desconhecido: a página de manutenção só volta com false
        em_manutencao = None
    return JsonResponse({"status": "ok", "maintenance": em_manutencao})
