"""
Cofrinho de trocos (META-35 a META-45).

O usuário ativa os trocos escolhendo a meta que vai recebê-los. A partir da
ativação, cada despesa efetivada gera um troco pendente, lembrado até o
depósito. Com a meta arquivada ou excluída, os trocos ficam pausados até o
usuário escolher outra (META-44); desativar para de contar trocos novos e
mantém os pendentes (META-45).
"""
from decimal import Decimal, ROUND_CEILING

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from core.valores import dinheiro

from .models import ConfiguracaoDeTrocos, Troco

TROCOS_PAUSADOS = 'Os trocos estão pausados. Escolha outra meta.'
DESCRICAO_DO_DEPOSITO = 'Depósito dos trocos'


def configuracao_de(usuario):
    """A configuração do usuário (objeto ou id), ou `None` se ele nunca ativou os trocos."""
    return ConfiguracaoDeTrocos.objects.filter(user=usuario).select_related('meta').first()


def pausado(config):
    """Trocos ativos com a meta arquivada ou excluída (META-44)."""
    return bool(config and config.ativo and (config.meta is None or not config.meta.is_active))


def resumo(usuario):
    """A configuração e os trocos pendentes, para `GET /goals/spare-change/`."""
    config = configuracao_de(usuario)
    pendentes = Troco.objects.filter(user=usuario, status=Troco.PENDENTE).aggregate(
        total=Sum('valor'), quantidade=Count('pk'),
    )
    return {
        'active': bool(config and config.ativo),
        'goal': config.meta_id if config else None,
        'paused': pausado(config),
        'pending_total': dinheiro(pendentes['total'] or Decimal('0.00')),
        'pending_count': pendentes['quantidade'],
    }


def configurar(usuario, ativo, meta=None):
    """
    Ativa ou desativa os trocos. Ativar grava a hora da ativação (META-35);
    escolher outra meta com os trocos já ativos mantém essa hora. Desativar
    sem meta mantém a meta escolhida e os trocos pendentes (META-45).
    """
    config, _ = ConfiguracaoDeTrocos.objects.get_or_create(user=usuario)
    if ativo and not config.ativo:
        config.ativado_em = timezone.now()
    config.ativo = ativo
    if meta is not None:
        config.meta = meta
    config.save()
    return config


def _valor_do_troco(despesa):
    """
    O troco da despesa até o próximo real inteiro (META-36), ou `None` quando
    ela não gera troco: não é despesa efetivada com conta, é paga pelo
    cofrinho, é um ajuste de saldo ou o valor já é inteiro.
    """
    if despesa.type != 'EXPENSE' or despesa.status != 'COMPLETED' or despesa.account_id is None:
        return None
    # O ajuste de saldo é reconhecido pelo campo, não pela descrição (AD-046)
    if despesa.is_balance_adjustment or despesa.account.type == 'PIGGY_BANK':
        return None
    troco = despesa.amount.to_integral_value(rounding=ROUND_CEILING) - despesa.amount
    return troco if troco > 0 else None


def ao_salvar(despesa, criada):
    """
    Depois de gravar uma transação:
    - com troco pendente, recalcula o valor e a conta dele ou o remove,
      quando a despesa deixa de gerar troco (META-41);
    - com troco depositado ou descartado, não mexe em nada (META-42);
    - sem troco, gera um quando a despesa efetivada foi criada depois da
      ativação e os trocos estão ativos e sem pausa (META-35, META-36,
      META-44, META-45).
    """
    if criada and despesa.type != 'EXPENSE':
        return
    existente = None if criada else Troco.objects.filter(despesa_id=despesa.pk).first()
    if existente is not None:
        pendente = Troco.objects.filter(pk=existente.pk, status=Troco.PENDENTE)
        valor = _valor_do_troco(despesa)
        if valor is None:
            pendente.delete()
        else:
            pendente.update(valor=valor, conta_id=despesa.account_id)
        return
    valor = _valor_do_troco(despesa)
    if valor is None:
        return
    config = configuracao_de(despesa.user_id)
    if not config or not config.ativo or pausado(config) or despesa.created_at < config.ativado_em:
        return
    Troco.objects.create(user_id=despesa.user_id, despesa=despesa, conta_id=despesa.account_id, valor=valor)


def ao_excluir(despesa):
    """A despesa excluída leva junto o troco pendente; o depositado fica (META-41, META-42)."""
    Troco.objects.filter(despesa_id=despesa.pk, status=Troco.PENDENTE).delete()


@transaction.atomic
def depositar(usuario):
    """
    Deposita os trocos pendentes na meta dos trocos: um aporte por conta de
    origem, com a soma dos trocos dela, e cada troco marcado como depositado
    e ligado ao aporte (META-38). Trocos de conta excluída são descartados
    (META-43). A trava da configuração serializa pedidos simultâneos, e o
    segundo não encontra mais trocos pendentes (META-39, META-40). Com os
    trocos desativados, os pendentes continuam depositáveis (META-45); com a
    meta arquivada ou excluída, o depósito é recusado (META-44).

    Trava a configuração, as contas dos trocos e só então os trocos: a
    edição de uma despesa trava a conta dela antes do troco (AD-045).
    Devolve `{deposits: [{account_id, amount}], discarded}`.
    """
    from accounts.saldo import travar
    from core.datas import hoje
    from .models import GoalDeposit
    from .services import GoalService

    config = ConfiguracaoDeTrocos.objects.select_for_update().filter(user=usuario).first()
    resposta = {'deposits': [], 'discarded': 0}
    pendentes = Troco.objects.filter(user=usuario, status=Troco.PENDENTE)
    if config is None or not pendentes.exists():
        return resposta
    if config.meta is None or not config.meta.is_active:
        raise ValidationError(TROCOS_PAUSADOS)

    contas = travar(config.meta.account_id, *pendentes.values_list('conta_id', flat=True))
    trocos = list(pendentes.select_for_update().order_by('pk'))
    contas.update(travar(*{troco.conta_id for troco in trocos} - set(contas)))

    por_conta = {}
    for troco in trocos:
        conta = contas.get(troco.conta_id)
        if conta is None or not conta.is_active:
            resposta['discarded'] += 1
            Troco.objects.filter(pk=troco.pk).update(status=Troco.DESCARTADO)
            continue
        por_conta.setdefault(conta.pk, []).append(troco)

    for conta_id in sorted(por_conta, key=str):
        do_grupo = por_conta[conta_id]
        total = sum((troco.valor for troco in do_grupo), Decimal('0.00'))
        GoalService.aportar(config.meta, total, hoje(), account=contas[conta_id], description=DESCRICAO_DO_DEPOSITO)
        aporte = GoalDeposit.objects.filter(goal_id=config.meta_id, account_id=conta_id).latest('pk')
        Troco.objects.filter(pk__in=[troco.pk for troco in do_grupo]).update(status=Troco.DEPOSITADO, aporte=aporte)
        resposta['deposits'].append({'account_id': str(conta_id), 'amount': dinheiro(total)})
    return resposta
