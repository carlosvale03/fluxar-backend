"""
Versão vigente dos termos de uso e da política de privacidade (LGPD-26 a
LGPD-31, AD-031).

A versão é publicada junto com o texto do frontend: ao mudar o texto, suba
`VERSAO_VIGENTE`, atualize `VIGENTE_DESDE` e `MUDANCAS`, e todos os usuários
precisam aceitar de novo antes de voltar a usar o app (LGPD-28, LGPD-29).
"""
import datetime

VERSAO_VIGENTE = '2.0'
VIGENTE_DESDE = datetime.date(2026, 10, 9)

# O que mudou em relação à versão anterior, em frases curtas para a tela de aceite
MUDANCAS = [
    'Os termos e a política passam a ter número de versão e data de vigência.',
    'A política lista as finalidades do uso dos dados e os serviços que os tratam.',
    'Você pode consentir, se quiser, com o uso de dados anonimizados para melhorar o '
    'produto e treinar modelos de previsão e de categorização, e retirar o consentimento '
    'a qualquer momento.',
    'Você pode excluir a sua conta pelo app, com 30 dias para desistir, e baixar os seus '
    'dados financeiros antes.',
    'CPF, telefone, data de nascimento e renda passam a ficar criptografados no banco.',
]

# Os serviços que tratam os dados, com a finalidade de cada um (LGPD-31)
SERVICOS = [
    {'name': 'Render', 'purpose': 'Hospedagem da API e do banco de dados'},
    {'name': 'Vercel', 'purpose': 'Hospedagem do site'},
    {'name': 'Resend', 'purpose': 'Envio de e-mails'},
    {'name': 'Brevo', 'purpose': 'Envio de e-mails (alternativo)'},
    {'name': 'Cloudinary', 'purpose': 'Guarda das imagens (foto de perfil e imagens das metas)'},
]


def termos_vigentes():
    """O corpo de `GET /api/terms/`."""
    return {
        'version': VERSAO_VIGENTE,
        'effective_date': VIGENTE_DESDE.isoformat(),
        'changes': list(MUDANCAS),
        'services': [dict(servico) for servico in SERVICOS],
    }


def registrar_aceite(usuario, versao=None):
    """
    Grava o aceite da versão (a vigente, por padrão) sem apagar os anteriores
    e atualiza o cache do usuário (LGPD-26, LGPD-30).
    """
    from api.models import AceiteDosTermos

    versao = versao or VERSAO_VIGENTE
    aceite = AceiteDosTermos.objects.create(user=usuario, versao=versao)
    usuario.versao_dos_termos_aceita = versao
    type(usuario).objects.filter(pk=usuario.pk).update(versao_dos_termos_aceita=versao)
    return aceite


def registrar_decisao(usuario, consentiu):
    """
    Grava a decisão sobre o consentimento de melhoria do produto, com a
    versão vigente da política, sem apagar as anteriores, e atualiza o cache
    do usuário (LGPD-33, LGPD-35).
    """
    from api.models import DecisaoDeConsentimento

    decisao = DecisaoDeConsentimento.objects.create(
        user=usuario, consentiu=consentiu, versao_da_politica=VERSAO_VIGENTE,
    )
    usuario.consentimento_melhoria = consentiu
    type(usuario).objects.filter(pk=usuario.pk).update(consentimento_melhoria=consentiu)
    return decisao


def aceitou_a_vigente(usuario):
    """True quando o usuário aceitou a versão vigente (o cache do `User`)."""
    return usuario.versao_dos_termos_aceita == VERSAO_VIGENTE
