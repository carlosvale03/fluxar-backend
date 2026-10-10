"""
Recebimentos a dividir, revisão e geração da divisão (SALARIO-24, SALARIO-29
a SALARIO-43).

A geração (AD-026, AD-053) corre num `atomic`, com a linha do recebimento
travada: um segundo pedido para o mesmo recebimento espera o primeiro e, ao
seguir, encontra a divisão gravada (SALARIO-39). A repetição da mesma chave
devolve a divisão já gravada, sem gerar de novo (SALARIO-37, AD-007), e a
resposta é remontada do registro. As transferências saem por
`TransactionService.create_transfer` e os aportes por `GoalService.aportar`,
que soma o aporte só na meta escolhida (SALARIO-33, AD-028). Qualquer erro
desfaz o lote inteiro (SALARIO-36).

As saídas da conta do salário desde o recebimento (`saidas`, AD-057) entram
na revisão e são descontadas das partes escolhidas; cada transação leva o
que a parte ainda transfere, e as saídas descontadas ficam registradas na
divisão até ela ser desfeita (SALARIO-64 a SALARIO-70, SALARIO-72).
"""
import logging
from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.faturas import mes_anterior
from accounts.saldo import travar
from core.datas import BRASILIA, hoje
from core.fields import RECEBIMENTO_NAO_ENCONTRADO
from core.valores import dinheiro
from goals.models import Goal, GoalDeposit
from goals.services import GoalService
from reports.regras import limites_do_mes, mes_atual
from transactions.models import Transaction
from transactions.services import TransactionService

from . import plano, saidas
from .calculo import ZERO, AjustesAcimaDoRecebido, dividir
from .models import CONTA, META, DivisaoDoSalario, ItemDaDivisao, SaidaDescontada
from .serializers import conta_disponivel, meta_disponivel

logger = logging.getLogger(__name__)

JA_DIVIDIDO = 'Este salário já foi dividido.'
AJUSTES_ACIMA_DO_RECEBIDO = 'Os valores passam do salário recebido.'
AJUSTE_DE_OUTRA_PARTE = 'Ajuste de uma parte que não está no plano.'
DESTINO_FALTANDO = 'Escolha o destino de todas as partes.'
DESTINO_NAO_DISPONIVEL = 'O destino da parte {nome} não está mais disponível.'
NADA_A_GERAR = 'Nenhuma parte do plano gera transação.'
CHAVE_COM_OUTRO_SALARIO = 'Este identificador de divisão já foi usado com outro salário.'
DESCRICAO = 'Divisão do salário: {nome}'
# Prazo para desfazer, em dias depois da data da geração (SALARIO-49)
PRAZO_PARA_DESFAZER = 7


def recebimento_valido(usuario, transacao, categorias=None):
    """
    Receita efetivada, com conta, numa categoria de salário do usuário e que
    não é ajuste de saldo (SALARIO-40). A importada também vale (SALARIO-24).
    """
    if categorias is None:
        categorias = plano.categorias_de_salario(usuario)
    return (
        transacao is not None and transacao.user_id == usuario.pk and transacao.type == 'INCOME'
        and transacao.status == 'COMPLETED' and transacao.account_id is not None
        and not transacao.is_balance_adjustment and transacao.category_id in categorias
    )


def conferir_recebimento(usuario, transacao):
    """Levanta 400 no campo `receipt` se a transação não é um salário recebido (SALARIO-40)."""
    if not recebimento_valido(usuario, transacao):
        raise ValidationError({'receipt': [RECEBIMENTO_NAO_ENCONTRADO]})


def divisao_ativa(recebimento_id):
    return DivisaoDoSalario.objects.filter(recebimento_ref=recebimento_id, desfeita_em__isnull=True)


def conferir_nao_dividido(recebimento_id):
    """Levanta 400 se o recebimento já tem uma divisão ativa (SALARIO-38)."""
    if divisao_ativa(recebimento_id).exists():
        raise ValidationError({'detail': JA_DIVIDIDO})


def pendentes(usuario):
    """
    Os salários efetivados do mês atual e do anterior, no calendário de
    Brasília, sem divisão ativa, do mais recente para o mais antigo
    (SALARIO-24).
    """
    ano, mes = mes_atual()
    mes_ant, ano_ant = mes_anterior(mes, ano)
    inicio, _ = limites_do_mes(ano_ant, mes_ant)
    _, fim = limites_do_mes(ano, mes)
    dividido = DivisaoDoSalario.objects.filter(recebimento_ref=OuterRef('pk'), desfeita_em__isnull=True)
    return (
        Transaction.objects.filter(
            user=usuario, type='INCOME', status='COMPLETED', account__isnull=False,
            is_balance_adjustment=False, category_id__in=plano.categorias_de_salario(usuario),
            date__gte=inicio, date__lte=fim,
        )
        .exclude(Exists(dividido))
        .select_related('account', 'category')
        .order_by('-date', '-created_at')
    )


def recebimento_em_json(transacao):
    return {
        'id': str(transacao.pk),
        'description': transacao.description,
        'amount': dinheiro(transacao.amount),
        'date': transacao.date.isoformat(),
        'account': str(transacao.account_id),
        'account_name': transacao.account.name,
        'category': str(transacao.category_id) if transacao.category_id else None,
        'category_name': transacao.category.name if transacao.category_id else None,
        'imported': transacao.import_batch is not None,
    }


def calcular(usuario, recebimento, ajustes=None, partes=None, gastos=None):
    """
    A divisão do recebimento pelo plano salvo, com os ajustes da revisão
    (SALARIO-26 a SALARIO-30) e as saídas descontadas de cada parte
    (`gastos`, SALARIO-66). Ajuste de uma parte fora do plano ou acima do
    recebido recebe 400 no campo `adjustments`.
    """
    if partes is None:
        partes = plano.partes_do_plano(usuario)
    ajustes = {str(chave): valor for chave, valor in (ajustes or {}).items()}
    if set(ajustes) - {str(parte.pk) for parte in partes}:
        raise ValidationError({'adjustments': [AJUSTE_DE_OUTRA_PARTE]})
    try:
        return dividir(
            recebimento.amount, partes, ajustes, conta_do_recebimento=recebimento.account_id, gastos=gastos,
        )
    except AjustesAcimaDoRecebido:
        raise ValidationError({'adjustments': [AJUSTES_ACIMA_DO_RECEBIDO]})


def calcular_com_saidas(usuario, recebimento, ajustes=None, pedido=None):
    """
    A divisão com as saídas desde o recebimento (SALARIO-64 a SALARIO-67,
    SALARIO-69). Devolve `(partes, elegiveis, descontadas, resultado)`;
    `descontadas` é `[(saida, parte)]`.
    """
    partes = plano.partes_do_plano(usuario)
    lista = list(saidas.elegiveis(usuario, recebimento))
    descontadas = saidas.escolhidas(lista, partes, pedido)
    resultado = calcular(usuario, recebimento, ajustes, partes=partes, gastos=saidas.gastos_por_parte(descontadas))
    return partes, lista, descontadas, resultado


def valores_do_item(gasto, transferir, passou):
    """O já gasto, o que será transferido e quanto passou de uma parte (SALARIO-66, SALARIO-67)."""
    return {'spent': dinheiro(gasto), 'transfer': dinheiro(transferir), 'exceeded': dinheiro(passou)}


def revisao_em_json(recebimento, divisao, data, saidas_em_json=()):
    """O corpo de `POST /salary/divisions/preview/` (SALARIO-29, SALARIO-64 a SALARIO-67)."""
    origem = {'id': str(recebimento.account_id), 'name': recebimento.account.name}
    return {
        'receipt': recebimento_em_json(recebimento),
        'items': [
            {
                **plano.item_em_json(item), 'origin_account': origem,
                **valores_do_item(item.gasto, item.transferir, item.passou),
            }
            for item in divisao.itens
        ],
        'outflows': list(saidas_em_json),
        'total': dinheiro(divisao.total),
        'free': dinheiro(divisao.livre),
        'date': data.isoformat(),
    }


def revisar(usuario, recebimento, ajustes=None, pedido=None):
    """
    A revisão da divisão de um recebimento, sem gravar nada. Lista todas as
    saídas que podem ser descontadas, com a parte sugerida e a escolhida no
    `pedido`; sem pedido, nenhuma é descontada (SALARIO-64, SALARIO-65).
    """
    conferir_recebimento(usuario, recebimento)
    conferir_nao_dividido(recebimento.pk)
    partes, lista, descontadas, resultado = calcular_com_saidas(usuario, recebimento, ajustes, pedido)
    sugeridas = saidas.sugestoes(usuario, lista, partes)
    escolhida = {saida.pk: parte for saida, parte in descontadas}
    corpo = [saidas.saida_em_json(saida, *sugeridas[saida.pk], escolhida.get(saida.pk)) for saida in lista]
    return revisao_em_json(recebimento, resultado, hoje(), corpo)


# --- Geração (SALARIO-32 a SALARIO-43) ---

def pela_chave(usuario, chave, recebimento_id):
    """
    A divisão já gravada com a chave da tentativa, ou `None`. A mesma chave
    com outro recebimento recebe 400.
    """
    if chave is None:
        return None
    anterior = DivisaoDoSalario.objects.filter(user=usuario, chave=chave).first()
    if anterior is not None and str(anterior.recebimento_ref) != str(recebimento_id):
        raise ValidationError({'detail': CHAVE_COM_OUTRO_SALARIO})
    return anterior


def destino_disponivel(parte):
    """O destino ainda recebe a parte: conta ativa que não é cofrinho, ou meta ativa com cofrinho ativo."""
    if parte.tipo_de_destino == CONTA:
        return conta_disponivel(parte.conta)
    if parte.tipo_de_destino == META:
        meta = parte.meta
        return meta_disponivel(meta) and meta.account is not None and meta.account.is_active
    return True


def conferir_partes(resultado):
    """As recusas da geração, na ordem SALARIO-41, SALARIO-42 e SALARIO-43."""
    # Sem nada a transferir, a parte sem destino não precisa de um (SALARIO-67)
    if any(item.transferir > 0 and item.parte.tipo_de_destino is None for item in resultado.itens):
        raise ValidationError({'detail': DESTINO_FALTANDO})
    for item in resultado.itens:
        if item.gera_transacao and not destino_disponivel(item.parte):
            raise ValidationError({'detail': DESTINO_NAO_DISPONIVEL.format(nome=item.parte.nome)})
    if not any(item.gera_transacao for item in resultado.itens):
        raise ValidationError({'detail': NADA_A_GERAR})


def _gerar_item(usuario, recebimento, item, data, divisao):
    """
    Cria a transferência ou o aporte da parte com o que ela ainda transfere
    depois das saídas descontadas (SALARIO-66), efetivado e com a data
    `data`, e marca as duas pernas com a divisão (SALARIO-32, SALARIO-35).
    Devolve `(saida, entrada, transfer_id)`.
    """
    parte = item.parte
    descricao = DESCRICAO.format(nome=parte.nome)
    if parte.tipo_de_destino == CONTA:
        transfer_id = TransactionService.create_transfer(
            user=usuario, account_from=recebimento.account, account_to=parte.conta,
            amount=item.transferir, date=data, description=descricao,
        )
    else:
        try:
            GoalService.aportar(parte.meta, item.transferir, data, account=recebimento.account, description=descricao)
        except DjangoValidationError as erro:
            raise ValidationError({'detail': erro.messages[0]})
        registro = GoalDeposit.objects.filter(goal_id=parte.meta_id, account_id=recebimento.account_id).latest('pk')
        transfer_id = registro.transaction_id
    pernas = Transaction.objects.filter(transfer_id=transfer_id, user=usuario)
    pernas.update(divisao_do_salario=divisao.pk)
    return pernas.get(type='TRANSFER_OUT'), pernas.get(type='TRANSFER_IN'), transfer_id


@transaction.atomic
def gerar(usuario, recebimento_id, chave=None, ajustes=None, pedido=None):
    """
    Gera as transações da divisão do recebimento pelo plano salvo, com os
    ajustes da revisão e as saídas descontadas do `pedido` (SALARIO-66).
    Devolve `(divisao, criada)`; `criada` é falso quando a chave já tinha
    sido usada para esse recebimento.

    A divisão, os itens e as saídas descontadas nascem num savepoint, antes
    das transações: a restrição única parcial das saídas recusa a mesma
    saída descontada ao mesmo tempo por outra divisão, que deixou de estar
    na lista (SALARIO-64, SALARIO-69).
    """
    anterior = pela_chave(usuario, chave, recebimento_id)
    if anterior is not None:
        return anterior, False
    recebimento = Transaction.objects.select_for_update().filter(pk=recebimento_id, user=usuario).first()
    conferir_recebimento(usuario, recebimento)
    # Um pedido com a mesma chave pode ter terminado enquanto este esperava a trava
    anterior = pela_chave(usuario, chave, recebimento_id)
    if anterior is not None:
        return anterior, False
    conferir_nao_dividido(recebimento.pk)

    _, _, descontadas, resultado = calcular_com_saidas(usuario, recebimento, ajustes, pedido)
    conferir_partes(resultado)
    try:
        # Savepoint: com ATOMIC_REQUESTS, o erro de restrição sem ele
        # inutilizaria a transação da requisição
        with transaction.atomic():
            divisao = DivisaoDoSalario.objects.create(
                user=usuario, recebimento=recebimento, recebimento_ref=recebimento.pk,
                conta_de_origem_id=recebimento.account_id, chave=chave, valor_recebido=recebimento.amount,
                total=resultado.total, livre=resultado.livre,
            )
            registros = {}
            for ordem, item in enumerate(resultado.itens):
                parte = item.parte
                registros[parte.pk] = ItemDaDivisao.objects.create(
                    divisao=divisao, ordem=ordem, nome_da_parte=parte.nome,
                    tipo_de_destino=parte.tipo_de_destino or '',
                    conta=parte.conta if parte.tipo_de_destino == CONTA else None,
                    meta=parte.meta if parte.tipo_de_destino == META else None,
                    valor=item.valor, reduzida=item.reduzida,
                )
            # As saídas descontadas e em qual parte (SALARIO-68)
            SaidaDescontada.objects.bulk_create([
                SaidaDescontada(
                    divisao=divisao, item=registros[parte.pk], transacao=saida, transacao_ref=saida.pk,
                    valor=saida.amount,
                )
                for saida, parte in descontadas
            ])
    except IntegrityError:
        # A mesma chave gravada ao mesmo tempo por outro pedido (SALARIO-39)
        anterior = pela_chave(usuario, chave, recebimento_id)
        if anterior is not None:
            return anterior, False
        if divisao_ativa(recebimento.pk).exists():
            raise ValidationError({'detail': JA_DIVIDIDO})
        # Uma saída descontada ao mesmo tempo por outra divisão (SALARIO-64)
        raise ValidationError({'outflows': [saidas.SAIDA_NAO_ENCONTRADA]})

    data = hoje()
    geradas = 0
    for item in resultado.itens:
        if not item.gera_transacao:
            continue
        registro = registros[item.parte.pk]
        registro.transacao_saida, registro.transacao_entrada, registro.transfer_id = _gerar_item(
            usuario, recebimento, item, data, divisao,
        )
        registro.save(update_fields=['transacao_saida', 'transacao_entrada', 'transfer_id'])
        geradas += 1
    # Só ids e quantidades (SALARIO-18, AD-019)
    logger.info(
        'Divisão do salário gerada divisao=%s usuario=%s transacoes=%s saidas=%s',
        divisao.pk, usuario.pk, geradas, len(descontadas),
    )
    return divisao, True


def data_da_divisao(divisao):
    """O dia da geração no calendário de Brasília: a data das transações geradas."""
    return timezone.localtime(divisao.criada_em, BRASILIA).date()


def prazo_para_desfazer(divisao):
    """O último dia em que a divisão ainda pode ser desfeita (SALARIO-49)."""
    return data_da_divisao(divisao) + timedelta(days=PRAZO_PARA_DESFAZER)


def desfaziveis(usuario):
    """
    As divisões do usuário que ainda podem ser desfeitas: não desfeitas e
    geradas há no máximo `PRAZO_PARA_DESFAZER` dias no calendário de Brasília
    (`hoje() <= prazo_para_desfazer`), da mais recente para a mais antiga
    (SALARIO-45, SALARIO-49).
    """
    primeiro_dia = hoje() - timedelta(days=PRAZO_PARA_DESFAZER)
    inicio = datetime.combine(primeiro_dia, time.min, tzinfo=BRASILIA)
    return (
        DivisaoDoSalario.objects
        .filter(user=usuario, desfeita_em__isnull=True, criada_em__gte=inicio)
        .select_related('conta_de_origem', 'recebimento')
        .order_by('-criada_em', '-pk')
    )


# --- Desfazer (SALARIO-46 a SALARIO-51) ---

JA_DESFEITA = 'Esta divisão já foi desfeita.'
PRAZO_ACABOU = 'O prazo para desfazer esta divisão acabou.'
TRANSFERENCIA_MUDOU = 'A transferência para {destino} mudou.'
APORTE_MUDOU = 'O aporte em {meta} mudou.'
META_SEM_O_VALOR = 'A meta {nome} não tem mais o valor aportado pela divisão.'


def gastos_dos_itens(divisao):
    """`{id do item: soma das saídas descontadas nele}`, também nas divisões desfeitas."""
    gastos = {}
    for item_id, valor in divisao.saidas.values_list('item_id', 'valor'):
        gastos[item_id] = gastos.get(item_id, ZERO) + valor
    return gastos


def transferido(item, gastos):
    """O que o item transferiu: o valor da parte menos as saídas descontadas, sem ficar abaixo de zero."""
    return max(ZERO, item.valor - gastos.get(item.pk, ZERO))


def _item_mudou(divisao, item, data, valor):
    """
    Se as transações do item não são mais as geradas: alguma perna apagada,
    ou com valor (`valor`, o transferido), data, status, conta ou marca
    diferentes; no aporte, também o registro da meta (SALARIO-48).
    """
    pernas = {
        perna.pk: perna
        for perna in Transaction.objects.filter(pk__in=[item.transacao_saida_id, item.transacao_entrada_id])
    }
    saida, entrada = pernas.get(item.transacao_saida_id), pernas.get(item.transacao_entrada_id)
    if saida is None or entrada is None:
        return True
    if item.tipo_de_destino == META:
        if item.meta is None:
            return True
        destino = item.meta.account_id
    else:
        destino = item.conta_id
    for perna, conta in ((saida, divisao.conta_de_origem_id), (entrada, destino)):
        if (
            perna.amount != valor or perna.date != data or perna.status != 'COMPLETED'
            or perna.account_id is None or perna.account_id != conta
            or perna.transfer_id != item.transfer_id or perna.divisao_do_salario != divisao.pk
        ):
            return True
    if item.tipo_de_destino == META:
        return not GoalDeposit.objects.filter(
            goal_id=item.meta_id, type='DEPOSIT', amount=valor, transacao_entrada_id=entrada.pk,
        ).exists()
    return False


def _mensagem_de_mudanca(item):
    if item.tipo_de_destino == META:
        return APORTE_MUDOU.format(meta=item.meta.name if item.meta is not None else item.nome_da_parte)
    return TRANSFERENCIA_MUDOU.format(destino=item.conta.name if item.conta is not None else item.nome_da_parte)


@transaction.atomic
def desfazer(usuario, divisao_id):
    """
    Desfaz a divisão inteira (SALARIO-46, SALARIO-47): confere o prazo e cada
    item e só então apaga as transações uma a uma, para que os sinais
    recalculem saldos e metas e recusem uma meta negativa. Grava
    `desfeita_em`, o que libera o recebimento para uma nova divisão. Qualquer
    falha desfaz tudo (SALARIO-50). Trava a divisão, depois as contas e só
    então as metas (AD-045).
    """
    divisao = DivisaoDoSalario.objects.select_for_update().filter(pk=divisao_id, user=usuario).first()
    if divisao is None:
        raise Http404
    if divisao.desfeita_em is not None:
        raise ValidationError({'detail': JA_DESFEITA})
    if hoje() > prazo_para_desfazer(divisao):
        raise ValidationError({'detail': PRAZO_ACABOU})

    itens = [item for item in divisao.itens.select_related('conta', 'meta').order_by('ordem', 'pk') if item.transfer_id]
    contas = [divisao.conta_de_origem_id]
    contas += [item.conta_id for item in itens]
    contas += [item.meta.account_id for item in itens if item.meta is not None]
    contas += Transaction.objects.filter(
        user=usuario, divisao_do_salario=divisao.pk,
    ).values_list('account_id', flat=True)
    travar(*contas)
    metas = {
        meta.pk: meta
        for meta in Goal.objects.select_for_update().filter(
            pk__in=[item.meta_id for item in itens if item.meta_id],
        ).order_by('pk')
    }

    data = data_da_divisao(divisao)
    gastos = gastos_dos_itens(divisao)
    for item in itens:
        if _item_mudou(divisao, item, data, transferido(item, gastos)):
            raise ValidationError({'detail': _mensagem_de_mudanca(item)})
    aportado = {}
    for item in itens:
        if item.tipo_de_destino == META:
            aportado[item.meta_id] = aportado.get(item.meta_id, 0) + transferido(item, gastos)
    for meta_id, valor in aportado.items():
        meta = metas[meta_id]
        if meta.current_amount < valor:
            raise ValidationError({'detail': META_SEM_O_VALOR.format(nome=meta.name)})

    for item in itens:
        # Uma instância por vez: a parceira sai junto (sync_transfer_delete)
        Transaction.objects.get(pk=item.transacao_saida_id).delete()
    divisao.desfeita_em = timezone.now()
    divisao.save(update_fields=['desfeita_em'])
    # As saídas descontadas voltam a poder entrar numa divisão (SALARIO-70)
    liberadas = divisao.saidas.filter(ativa=True).update(ativa=False)
    # Só ids e quantidades (SALARIO-18, AD-019)
    logger.info(
        'Divisão do salário desfeita divisao=%s usuario=%s transacoes=%s saidas=%s',
        divisao.pk, usuario.pk, len(itens), liberadas,
    )
    return divisao


def divisao_em_json(divisao):
    """
    O corpo da divisão gerada, montado só do registro: a repetição da mesma
    chave recebe a mesma resposta (SALARIO-37).
    """
    itens = list(divisao.itens.select_related('conta', 'meta').order_by('ordem', 'pk'))
    origem = {
        'id': str(divisao.conta_de_origem_id) if divisao.conta_de_origem_id else None,
        'name': divisao.conta_de_origem.name if divisao.conta_de_origem_id else None,
    }
    data = data_da_divisao(divisao).isoformat()
    recebimento = divisao.recebimento
    gastos = gastos_dos_itens(divisao)
    nomes = {item.pk: item.nome_da_parte for item in itens}
    descontadas = list(divisao.saidas.select_related('transacao').order_by('pk'))

    def destino(item):
        return plano.nome_do_destino(item.tipo_de_destino, item.conta, item.meta) or item.nome_da_parte

    def valores(item):
        gasto = gastos.get(item.pk, ZERO)
        return valores_do_item(gasto, transferido(item, gastos), max(ZERO, gasto - item.valor))

    def saida_em_json(registro):
        # A saída excluída depois da divisão fica só com o id e o valor descontado
        saida = registro.transacao
        return {
            'id': str(registro.transacao_ref),
            'date': saida.date.isoformat() if saida is not None else None,
            'description': saida.description if saida is not None else None,
            'amount': dinheiro(registro.valor),
            'type': saida.type if saida is not None else None,
            'part_name': nomes.get(registro.item_id),
        }

    return {
        'id': str(divisao.pk),
        'receipt': {
            'id': str(divisao.recebimento_ref),
            'amount': dinheiro(divisao.valor_recebido),
            'account': origem['id'],
            'account_name': origem['name'],
            'date': recebimento.date.isoformat() if recebimento is not None else None,
            'description': recebimento.description if recebimento is not None else None,
        },
        'items': [
            {
                'name': item.nome_da_parte,
                'destination_type': item.tipo_de_destino or None,
                'destination_name': plano.nome_do_destino(item.tipo_de_destino, item.conta, item.meta),
                'amount': dinheiro(item.valor),
                'reduced': item.reduzida,
                'generates_transaction': item.transfer_id is not None,
                **valores(item),
            }
            for item in itens
        ],
        'outflows': [saida_em_json(registro) for registro in descontadas],
        'transactions': [
            {
                'transfer_id': str(item.transfer_id),
                'out_transaction_id': str(item.transacao_saida_id) if item.transacao_saida_id else None,
                'in_transaction_id': str(item.transacao_entrada_id) if item.transacao_entrada_id else None,
                'kind': 'GOAL_DEPOSIT' if item.tipo_de_destino == META else 'TRANSFER',
                'part_name': item.nome_da_parte,
                'origin_account': origem,
                'destination_type': item.tipo_de_destino,
                'destination_name': destino(item),
                'account': str(item.conta_id) if item.conta_id else None,
                'goal': str(item.meta_id) if item.meta_id else None,
                'amount': dinheiro(transferido(item, gastos)),
                'date': data,
            }
            for item in itens if item.transfer_id is not None
        ],
        'total': dinheiro(divisao.total),
        'free': dinheiro(divisao.livre),
        'date': data,
        'created_at': divisao.criada_em.isoformat(),
        'can_undo_until': prazo_para_desfazer(divisao).isoformat(),
        'undone_at': divisao.desfeita_em.isoformat() if divisao.desfeita_em else None,
    }
