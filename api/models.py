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

    # 6. Exclusão pedida pelo usuário: a conta fica desativada até a exclusão
    # definitiva, 30 dias depois do pedido (LGPD-05, AD-018)
    exclusao_pedida_em = models.DateTimeField(null=True, blank=True)
    exclusao_agendada_para = models.DateTimeField(null=True, blank=True, db_index=True)

    # 7. Caches do último aceite dos termos e da decisão sobre o consentimento
    # de melhoria do produto; o histórico fica em AceiteDosTermos e
    # DecisaoDeConsentimento (LGPD-29, LGPD-35, AD-031). Os campos
    # terms_accepted e terms_accepted_at ficam só como histórico.
    versao_dos_termos_aceita = models.CharField(max_length=20, null=True, blank=True)
    consentimento_melhoria = models.BooleanField(default=False)

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
    # O registro identifica o usuário pelo id interno, que fica em
    # `usuario_ref` mesmo depois de a conta sair (LGPD-22, AD-030)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='system_logs', null=True, blank=True)
    usuario_ref = models.UUIDField(null=True, blank=True, db_index=True)
    action = models.CharField(max_length=100)
    # Sem nomes nem e-mails completos (LGPD-21)
    description = models.TextField()
    # E-mail mascarado do usuário afetado; some na exclusão da conta, quando
    # fica só o `usuario_ref` (ADMIN-10, ADMIN-11)
    usuario_email = models.CharField(max_length=255, blank=True, default='')
    # E-mail mascarado do administrador, ou "Sistema" (LGPD-22)
    admin_name = models.CharField(max_length=255)
    # O id interno do administrador, que sobrevive à exclusão da conta dele (AD-049)
    admin_ref = models.UUIDField(null=True, blank=True, db_index=True)
    # Os valores de antes e de depois da mudança, quando houver (ADMIN-08, ADMIN-09)
    antes = models.JSONField(null=True, blank=True)
    depois = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def save(self, *args, **kwargs):
        if self.user_id and not self.usuario_ref:
            self.usuario_ref = self.user_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.action} - {self.usuario_ref or 'Sistema'} - {self.timestamp}"

class AceiteDosTermos(models.Model):
    """Um aceite dos termos e da política, por versão; só acumula (LGPD-26, LGPD-30)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='aceites_dos_termos')
    versao = models.CharField(max_length=20)
    aceito_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-aceito_em']

    def __str__(self):
        return f"Aceite {self.versao} - {self.user_id}"

class DecisaoDeConsentimento(models.Model):
    """
    Uma decisão sobre o uso de dados anonimizados para melhorar o produto,
    com a versão da política vigente; só acumula (LGPD-33, LGPD-35).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='decisoes_de_consentimento')
    consentiu = models.BooleanField()
    versao_da_politica = models.CharField(max_length=20)
    decidido_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-decidido_em']

    def __str__(self):
        return f"Consentimento {self.consentiu} ({self.versao_da_politica}) - {self.user_id}"

class RegistroDeExclusao(models.Model):
    """
    O que fica de uma conta excluída definitivamente (LGPD-11): o id interno,
    as datas do pedido e da exclusão e quem a executou, sem dado pessoal.
    O `usuario_id` único torna a repetição da exclusão idempotente (LGPD-12).
    """
    USUARIO = 'USUARIO'
    ROTINA = 'ROTINA'
    ADMIN = 'ADMIN'
    EXECUTORES = [(USUARIO, 'Usuário'), (ROTINA, 'Rotina diária'), (ADMIN, 'Administrador')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario_id = models.UUIDField(unique=True)
    pedida_em = models.DateTimeField(null=True, blank=True)
    excluida_em = models.DateTimeField()
    executada_por = models.CharField(max_length=10, choices=EXECUTORES)

    def __str__(self):
        return f"Exclusão {self.usuario_id} ({self.executada_por})"

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
