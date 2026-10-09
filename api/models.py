import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from cloudinary.models import CloudinaryField

from core.criptografia import DataCriptografada, DecimalCriptografado, TextoCriptografado

class UserManager(BaseUserManager):
    @classmethod
    def normalize_email(cls, email):
        # O e-mail é o mesmo em qualquer caixa e fica guardado em minúsculas (AUTH-02)
        return super().normalize_email(email).lower()

    def get_by_natural_key(self, email):
        # Busca primeiro em minúsculas; o exato cobre as contas antigas que só
        # diferem na caixa e aguardam resolução manual (AUTH-44)
        try:
            return self.get(email=email.lower())
        except self.model.DoesNotExist:
            return self.get(email=email)

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('O endereço de e-mail é obrigatório')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'ADMIN')
        extra_fields.setdefault('plan', 'PREMIUM_PLUS') # Admin tem tudo
        extra_fields.setdefault('email_verified', True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    PLAN_CHOICES = [
        ('COMMON', 'Comum'),
        ('PREMIUM', 'Premium'),
        ('PREMIUM_PLUS', 'Premium Plus'),
    ]

    ROLE_CHOICES = [
        ('USER', 'Usuário'),
        ('ADMIN', 'Administrador'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Os nomes aparecem nas mensagens do validador de senha parecida (AUTH-04)
    name = models.CharField('nome', max_length=255)
    email = models.EmailField('e-mail', unique=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='COMMON')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='USER')
    email_verified = models.BooleanField(default=False)
    
    # 1. Dados Pessoais
    avatar = CloudinaryField('image', folder='avatars', resource_type='image', use_filename=False, blank=True, null=True)
    # Criptografados no banco, sem busca por eles; o CPF deixa de ser único
    # (LGPD-15, LGPD-18, AD-020)
    cpf = TextoCriptografado(max_length=14, blank=True, null=True)
    phone_number = TextoCriptografado(max_length=20, blank=True, null=True)
    date_of_birth = DataCriptografada(blank=True, null=True)
    
    # 2. Preferências
    currency = models.CharField(max_length=3, default='BRL')
    theme_preference = models.CharField(max_length=10, default='system', choices=[('light', 'Light'), ('dark', 'Dark'), ('system', 'System')])
    language = models.CharField(max_length=10, default='pt-BR')
    
    # 3. Perfil Financeiro
    monthly_income = DecimalCriptografado(blank=True, null=True)
    
    # 4. Configurações (JSON)
    notification_settings = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # 5. Consentimento Legal
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return self.email

    @property
    def is_common(self):
        return self.plan == 'COMMON'

    @property
    def is_premium(self):
        return self.plan == 'PREMIUM'

    @property
    def is_premium_plus(self):
        return self.plan == 'PREMIUM_PLUS'

class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_tokens')
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()

class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_tokens')
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()

class SystemLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='system_logs', null=True, blank=True)
    action = models.CharField(max_length=100)
    description = models.TextField()
    admin_name = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        user_email = self.user.email if self.user else "System"
        return f"{self.action} - {user_email} - {self.timestamp}"

class Sessao(models.Model):
    """
    Uma sessão de login (AD-037). Os tokens levam o `id` dela no claim `sid`;
    `refresh_jti` é o jti do único token de renovação que ainda vale.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessoes')
    refresh_jti = models.CharField(max_length=64)
    criada_em = models.DateTimeField(auto_now_add=True)
    ultimo_uso = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    encerrada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'encerrada_em'])]

class GlobalSetting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key}: {self.value}"

class TravaDePlano(models.Model):
    """
    O valor de uma trava do catálogo (`core/travas.py`) para um plano (AD-044).

    Recursos usam `liberado`; limites usam `limite`, em que nulo é sem limite.
    Sem a linha, o recurso fica liberado e o limite fica sem limite (PERM-28).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chave = models.CharField(max_length=50)
    plano = models.CharField(max_length=20, choices=User.PLAN_CHOICES)
    liberado = models.BooleanField(null=True)
    limite = models.PositiveIntegerField(null=True)
    atualizada_em = models.DateTimeField(auto_now=True)
    atualizada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['chave', 'plano'], name='trava_unica_por_plano')]

    def __str__(self):
        return f"{self.chave} ({self.plano})"
