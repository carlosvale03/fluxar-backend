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

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'name', 'email', 'plan', 'email_verified', 
            'cpf', 'phone_number', 'avatar_url', 'date_of_birth',
            'currency', 'theme_preference', 'language', 'monthly_income',
            'notification_settings', 'last_login', 'created_at'
        )
        read_only_fields = ('id', 'email', 'plan', 'email_verified', 'last_login', 'created_at')

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
