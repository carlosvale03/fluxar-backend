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
        fields = ('id', 'name', 'email', 'plan', 'email_verified', 'created_at')
        read_only_fields = ('id', 'email', 'plan', 'email_verified', 'created_at')

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
