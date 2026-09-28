from rest_framework import exceptions, serializers, status
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import update_last_login
from django.contrib.auth import password_validation
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings as jwt_settings

from core.throttles import LoginFalhasEmailThrottle

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

class UserProfileSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    emailVerified = serializers.BooleanField(source='email_verified', read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'name', 'email', 'plan', 'role', 'emailVerified', 
            'cpf', 'phone_number', 'avatar_url', 'date_of_birth',
            'currency', 'theme_preference', 'language', 'monthly_income',
            'notification_settings', 'is_active', 'last_login', 'created_at'
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
        if not value: return value
        # Validação simples de formato (melhorar com lib depois)
        # Manter apenas números
        clean_cpf = ''.join(filter(str.isdigit, value))
        if len(clean_cpf) != 11:
            raise serializers.ValidationError("CPF inválido. Deve conter 11 dígitos.")
        # TODO: Implementar algoritmo real de dígito verificador
        return value

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
        return ret
    
    def update(self, instance, validated_data):
        # Suporte a update via JSON aninhado 'preferences' se vier do front (opcional, mas robusto)
        # Por enquanto o serializer espera input 'flat' (ex: { "theme_preference": "dark" })
        # O to_representation cuida da saída.
        return super().update(instance, validated_data)

class AdminUserSerializer(UserProfileSerializer):
    """
    Serializer para uso exclusivo do admin. 
    Permite alterar planos e roles que são read_only para o usuário comum.
    """
    class Meta(UserProfileSerializer.Meta):
        read_only_fields = ('id', 'email', 'last_login', 'created_at')

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])

class LoginRecusado(exceptions.APIException):
    """
    HTTP 400 com `detail` e `code` no corpo (AD-024). Um ValidationError do
    serializer poria cada valor numa lista.
    """
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail, code):
        super().__init__({"detail": detail, "code": code})


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

        if not user.is_active:
            raise LoginRecusado("Esta conta está desativada.", "account_disabled")
        if not user.email_verified:
            raise LoginRecusado("Confirme seu e-mail para entrar.", "email_not_verified")

        self.user = user
        refresh = self.get_token(user)
        if jwt_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, user)
        return {"refresh": str(refresh), "access": str(refresh.access_token)}

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Adiciona claims customizadas ao token (para o front não precisar consultar /me logo de cara)
        token['name'] = user.name
        token['email'] = user.email
        token['plan'] = user.plan
        token['role'] = user.role

        return token

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
