from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('name', 'email', 'password', 'password_confirm')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "As senhas não coincidem."})
        return attrs

    def create(self, validated_data):
        # Remove o campo de confirmação antes de criar
        validated_data.pop('password_confirm')

        # Cria o usuário usando o manager customizado (faz hash da senha)
        user = User.objects.create_user(
            email=validated_data['email'],
            name=validated_data['name'],
            password=validated_data['password'],
            plan='COMMON' # Força plano comum no cadastro
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

    class Meta:
        model = User
        fields = (
            'id', 'name', 'email', 'plan', 'role', 'email_verified', 
            'cpf', 'phone_number', 'avatar_url', 'date_of_birth',
            'currency', 'theme_preference', 'language', 'monthly_income',
            'notification_settings', 'is_active', 'last_login', 'created_at'
        )
        read_only_fields = ('id', 'email', 'plan', 'role', 'email_verified', 'is_active', 'last_login', 'created_at')

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

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Customiza o payload do JWT para incluir dados extras do usuário no token
    """
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
    token = serializers.UUIDField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "As senhas não coincidem."})
        return attrs
