import re

from rest_framework import exceptions, serializers, status
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import update_last_login
from django.contrib.auth import password_validation
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings as jwt_settings

from core import travas
from core.throttles import LoginFalhasEmailThrottle

from .sessoes import criar_sessao

User = get_user_model()

EMAIL_JA_CADASTRADO = 'Este e-mail já está cadastrado. Se a conta é sua, use "Esqueci a senha".'
TERMOS_OBRIGATORIOS = 'É preciso aceitar os termos de uso.'
NOME_OBRIGATORIO = 'Informe o nome.'

class UserRegisterSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        max_length=255,
        error_messages={
            'required': NOME_OBRIGATORIO,
            'blank': NOME_OBRIGATORIO,
            'null': NOME_OBRIGATORIO,
            'max_length': 'O nome pode ter no máximo 255 caracteres.',
        },
    )
    # Declarado aqui para trocar o UniqueValidator do modelo, que compara com
    # a caixa exata, pela conferência sem caixa de validate_email (AUTH-02, AUTH-03)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=True)
    terms_accepted = serializers.BooleanField(
        required=True,
        error_messages={'required': TERMOS_OBRIGATORIOS, 'null': TERMOS_OBRIGATORIOS},
    )

    class Meta:
        model = User
        fields = ('name', 'email', 'password', 'password_confirm', 'terms_accepted')

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(EMAIL_JA_CADASTRADO)
        return email

    def validate_terms_accepted(self, value):
        if value is not True:
            raise serializers.ValidationError(TERMOS_OBRIGATORIOS)
        return value

    def validate_password(self, value):
        # Validada no próprio campo, para o erro da senha aparecer mesmo quando
        # outro campo também falha (AUTH-04, AUTH-07)
        confirmacao = self.initial_data.get('password_confirm')
        if confirmacao is not None and confirmacao != value:
            raise serializers.ValidationError("As senhas não coincidem.")
        # Um usuário temporário, sem gravar, para o validador comparar a senha
        # com o nome e o e-mail como vieram no pedido
        nome = self.initial_data.get('name')
        email = self.initial_data.get('email')
        candidato = User(
            name=nome if isinstance(nome, str) else '',
            email=email if isinstance(email, str) else '',
        )
        try:
            password_validation.validate_password(value, user=candidato)
        except DjangoValidationError as erro:
            raise serializers.ValidationError(list(erro.messages))
        return value

    def create(self, validated_data):
        # Remove o campo de confirmação antes de criar
        validated_data.pop('password_confirm')

        # Cria o usuário usando o manager customizado (faz hash da senha)
        from django.utils import timezone
        
        user = User.objects.create_user(
            email=validated_data['email'],
            name=validated_data['name'],
            password=validated_data['password'],
            terms_accepted=validated_data.get('terms_accepted', False),
            terms_accepted_at=timezone.now() if validated_data.get('terms_accepted') else None
        )
        return user

class UserAvatarSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['avatar']
        extra_kwargs = {'avatar': {'required': True}}
        
    def validate_avatar(self, value):
        if not value:
            raise serializers.ValidationError("Nenhum arquivo enviado.")
        # Limite de tamanho (ex: 5MB)
        limit_mb = 5
        if value.size > limit_mb * 1024 * 1024:
            raise serializers.ValidationError(f"Tamanho máximo do arquivo permitida é {limit_mb}MB.")
        return value

class PreferenciasSerializer(serializers.Serializer):
    """
    O objeto `preferences` que a tela envia; todos os campos são opcionais
    (CONTRATO-26, CONTRATO-28).
    """
    currency = serializers.ChoiceField(['BRL'], required=False)
    theme = serializers.ChoiceField(['light', 'dark', 'system'], required=False)
    language = serializers.ChoiceField(['pt-BR'], required=False)
    notifications = serializers.DictField(child=serializers.BooleanField(), required=False)


CPF_INVALIDO = 'CPF inválido.'
# 11 dígitos, com ou sem os pontos e o hífen
FORMATO_DO_CPF = re.compile(r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}')


def cpf_valido(digitos):
    """Confere os dois dígitos verificadores de um CPF com 11 dígitos (LGPD-17)."""
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    for tamanho in (9, 10):
        soma = sum(int(digito) * peso for digito, peso in zip(digitos, range(tamanho + 1, 1, -1)))
        verificador = soma * 10 % 11 % 10
        if verificador != int(digitos[tamanho]):
            return False
    return True


class UserProfileSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    emailVerified = serializers.BooleanField(source='email_verified', read_only=True)
    # Escrita no mesmo formato da leitura (CONTRATO-26)
    preferences = PreferenciasSerializer(write_only=True, required=False)
    # Os campos criptografados são texto no banco; a API mantém a data e o
    # valor com o formato de antes (LGPD-15)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    monthly_income = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
            'id', 'name', 'email', 'plan', 'role', 'emailVerified', 
            'cpf', 'phone_number', 'avatar_url', 'date_of_birth',
            'currency', 'theme_preference', 'language', 'monthly_income',
            'notification_settings', 'is_active', 'last_login', 'created_at', 'preferences',
        )
        read_only_fields = ('id', 'email', 'plan', 'role', 'is_active', 'last_login', 'created_at')

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url 
        return None

    def validate_cpf(self, value):
        # Confere só os dígitos verificadores, sem consultar outras contas, e
        # guarda só os 11 dígitos (LGPD-17, LGPD-18)
        if not value: return value
        if not FORMATO_DO_CPF.fullmatch(value.strip()):
            raise serializers.ValidationError(CPF_INVALIDO)
        digitos = ''.join(filter(str.isdigit, value))
        if not cpf_valido(digitos):
            raise serializers.ValidationError(CPF_INVALIDO)
        return digitos

    def validate_phone_number(self, value):
        if not value: return value
        # Validação simples
        if len(value) < 10:
             raise serializers.ValidationError("Telefone inválido.")
        return value

    def to_representation(self, instance):
        # Gera o JSON padrão
        ret = super().to_representation(instance)
        
        # Extrai campos de preferência para um objeto aninhado
        preferences = {
            'currency': ret.pop('currency', 'BRL'),
            'theme': ret.pop('theme_preference', 'system'),
            'language': ret.pop('language', 'pt-BR'),
            'notifications': ret.pop('notification_settings', {})
        }
        
        ret['preferences'] = preferences
        # O acesso do próprio usuário, só no /auth/me (PERM-17)
        if self.context.get('com_acesso'):
            ret['access'] = travas.acesso_na_api(instance)
        return ret
    
    def update(self, instance, validated_data):
        # O objeto `preferences` grava nos campos do modelo; as notificações
        # enviadas se juntam às que já estavam salvas (CONTRATO-26). Os campos
        # planos continuam aceitos. O to_representation cuida da saída.
        preferencias = validated_data.pop('preferences', {})
        for chave, campo in (('currency', 'currency'), ('theme', 'theme_preference'), ('language', 'language')):
            if chave in preferencias:
                validated_data[campo] = preferencias[chave]
        if 'notifications' in preferencias:
            validated_data['notification_settings'] = {
                **(instance.notification_settings or {}), **preferencias['notifications'],
            }
        return super().update(instance, validated_data)

class AdminUserSerializer(UserProfileSerializer):
    """
    Serializer para uso exclusivo do admin. 
    Permite alterar planos e roles que são read_only para o usuário comum.
    """
    # O painel não vê a data de nascimento nem a renda (LGPD-19)
    date_of_birth = None
    monthly_income = None

    class Meta(UserProfileSerializer.Meta):
        fields = tuple(
            campo for campo in UserProfileSerializer.Meta.fields
            if campo not in ('date_of_birth', 'monthly_income')
        )
        # CPF e telefone chegam mascarados e não são editados pelo painel
        read_only_fields = ('id', 'email', 'last_login', 'created_at', 'cpf', 'phone_number')

    def to_representation(self, instance):
        # CPF e telefone com só os últimos dígitos à vista (LGPD-19)
        ret = super().to_representation(instance)
        if ret.get('cpf'):
            ret['cpf'] = f"***.***.***-{ret['cpf'][-2:]}"
        if ret.get('phone_number'):
            ret['phone_number'] = mascarar_telefone(ret['phone_number'])
        return ret


def mascarar_telefone(telefone):
    """Troca por * cada dígito do telefone, menos os 4 últimos (LGPD-19)."""
    total = sum(caractere.isdigit() for caractere in telefone)
    vistos = 0
    mascarado = []
    for caractere in telefone:
        if caractere.isdigit():
            vistos += 1
            mascarado.append(caractere if vistos > total - 4 else '*')
        else:
            mascarado.append(caractere)
    return ''.join(mascarado)

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])

class LoginRecusado(exceptions.APIException):
    """
    HTTP 400 com `detail` e `code` no corpo (AD-024). Um ValidationError do
    serializer poria cada valor numa lista. `extras` entram no corpo ao lado
    dos dois.
    """
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail, code, **extras):
        super().__init__({"detail": detail, "code": code, **extras})


# O token de cancelamento da exclusão vale 15 minutos e só para o pedido em
# que foi emitido (LGPD-07, LGPD-08)
SALT_DO_CANCELAMENTO = 'fluxar.lgpd.cancelar-exclusao'
VALIDADE_DO_CANCELAMENTO = 15 * 60


def token_de_cancelamento(user):
    """Token assinado que permite cancelar a exclusão marcada da conta."""
    return signing.dumps(
        {'u': str(user.pk), 'p': user.exclusao_pedida_em.isoformat()}, salt=SALT_DO_CANCELAMENTO,
    )


def conta_do_token_de_cancelamento(token):
    """
    A conta com exclusão marcada a que o token se refere, ou None se o token
    for inválido, tiver vencido ou o pedido já não for o mesmo.
    """
    if not isinstance(token, str) or not token:
        return None
    try:
        dados = signing.loads(token, salt=SALT_DO_CANCELAMENTO, max_age=VALIDADE_DO_CANCELAMENTO)
        user = User.objects.get(pk=dados['u'])
    except (signing.BadSignature, User.DoesNotExist, KeyError, TypeError, DjangoValidationError):
        return None
    if user.exclusao_agendada_para is None or user.exclusao_pedida_em is None:
        return None
    if user.exclusao_pedida_em.isoformat() != dados.get('p'):
        return None
    return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Login por e-mail e senha, com dados extras do usuário no token.

    A senha é conferida antes do estado da conta: o aviso de conta desativada
    ou pendente só aparece com a senha correta (AUTH-13 a AUTH-16).
    """
    def validate(self, attrs):
        email = attrs[self.username_field]
        senha = attrs['password']

        try:
            user = User.objects.get_by_natural_key(email)
        except User.DoesNotExist:
            user = None

        if user is None:
            # Gera um hash à toa, para o tempo de resposta não revelar se a conta existe
            make_password(senha)
            senha_certa = False
        else:
            senha_certa = user.check_password(senha)

        if not senha_certa:
            # Só a falha conta para o limite por e-mail (AUTH-32)
            LoginFalhasEmailThrottle().registrar_falha(email)
            raise LoginRecusado("E-mail ou senha incorretos.", "invalid_credentials")

        # A conta com exclusão marcada recebe a data e a opção de cancelar,
        # sem abrir a sessão; vem antes do aviso de conta desativada (LGPD-07)
        if user.exclusao_agendada_para is not None:
            raise LoginRecusado(
                "A exclusão desta conta está marcada. Cancele a exclusão para voltar a usar o Fluxar.",
                "deletion_pending",
                deletion_scheduled_for=serializers.DateTimeField().to_representation(user.exclusao_agendada_para),
                cancel_token=token_de_cancelamento(user),
            )
        if not user.is_active:
            raise LoginRecusado("Esta conta está desativada.", "account_disabled")
        if not user.email_verified:
            raise LoginRecusado("Confirme seu e-mail para entrar.", "email_not_verified")

        self.user = user
        # Cada login abre uma sessão; a view tira o refresh do corpo e o grava no cookie (SESSAO-01)
        access, refresh = criar_sessao(user)
        if jwt_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, user)
        return {"refresh": refresh, "access": access}

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

class ResetPasswordSerializer(serializers.Serializer):
    """
    Senha nova da redefinição por link. O link é conferido na view, que passa
    o dono dele em context['user'] para o validador de senha parecida (AUTH-22).
    """
    new_password = serializers.CharField(required=True)
    new_password_confirm = serializers.CharField(required=True)

    def validate_new_password(self, value):
        confirmacao = self.initial_data.get('new_password_confirm')
        if confirmacao is not None and confirmacao != value:
            raise serializers.ValidationError("As senhas não coincidem.")
        try:
            password_validation.validate_password(value, user=self.context['user'])
        except DjangoValidationError as erro:
            raise serializers.ValidationError(list(erro.messages))
        return value

class SystemLogSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import SystemLog
        model = SystemLog
        fields = ('id', 'action', 'description', 'admin_name', 'timestamp')

class GlobalSettingSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import GlobalSetting
        model = GlobalSetting
        fields = ('key', 'value', 'description', 'updated_at')
        read_only_fields = ('updated_at',)

class AdminResetPasswordSerializer(serializers.Serializer):
    admin_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])


class LimiteDoPlanoField(serializers.Field):
    """Um inteiro maior ou igual a zero, ou nulo para sem limite (PERM-12)."""
    default_error_messages = {
        'invalid': 'Informe um número inteiro maior ou igual a zero, ou nenhum valor para sem limite.',
    }

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, int) or data < 0:
            self.fail('invalid')
        return data

    def to_representation(self, value):
        return value


class AlteracaoDePlanoSerializer(serializers.Serializer):
    """
    O PATCH de `/api/admin/plans/`: `{testing_unlock}`, `{key, plan, enabled}`
    para um recurso ou `{key, plan, limit}` para um limite (PERM-11, PERM-12).
    """
    testing_unlock = serializers.BooleanField(required=False)
    key = serializers.CharField(required=False)
    plan = serializers.ChoiceField(choices=travas.PLANOS, required=False)
    enabled = serializers.BooleanField(required=False)
    limit = LimiteDoPlanoField(required=False, allow_null=True)

    CAMPO_OBRIGATORIO = 'Este campo é obrigatório.'

    def validate(self, attrs):
        if 'testing_unlock' in attrs:
            if set(attrs) != {'testing_unlock'}:
                raise serializers.ValidationError(
                    {'testing_unlock': ['Envie a liberação para testes sozinha, sem uma trava.']}
                )
            return attrs

        erros = {}
        chave = attrs.get('key')
        trava = travas.CATALOGO.get(chave)
        if chave is None:
            erros['key'] = [self.CAMPO_OBRIGATORIO]
        elif trava is None:
            erros['key'] = ['Trava desconhecida.']
        if 'plan' not in attrs:
            erros['plan'] = [self.CAMPO_OBRIGATORIO]
        if trava is not None:
            # Cada tipo de trava aceita só o seu campo
            proprio, alheio = ('enabled', 'limit') if trava.tipo == travas.RECURSO else ('limit', 'enabled')
            if alheio in attrs:
                erros[alheio] = ['Este campo não vale para esta trava.']
            elif proprio not in attrs:
                erros[proprio] = [self.CAMPO_OBRIGATORIO]
        if erros:
            raise serializers.ValidationError(erros)
        return attrs
