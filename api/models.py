import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone

class UserManager(BaseUserManager):
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
        extra_fields.setdefault('plan', 'PREMIUM_PLUS') # Admin tem tudo
        extra_fields.setdefault('email_verified', True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    PLAN_CHOICES = [
        ('COMMON', 'Comum'),
        ('PREMIUM', 'Premium'),
        ('PREMIUM_PLUS', 'Premium Plus'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='COMMON')
    email_verified = models.BooleanField(default=False)
    
    # 1. Dados Pessoais
    avatar_url = models.URLField(max_length=500, blank=True, null=True)
    cpf = models.CharField(max_length=14, unique=True, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    
    # 2. Preferências
    currency = models.CharField(max_length=3, default='BRL')
    theme_preference = models.CharField(max_length=10, default='system', choices=[('light', 'Light'), ('dark', 'Dark'), ('system', 'System')])
    language = models.CharField(max_length=10, default='pt-BR')
    
    # 3. Perfil Financeiro
    monthly_income = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    
    # 4. Configurações (JSON)
    notification_settings = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
