"""
O plano de divisão do usuário e as categorias de salário (SALARIO-04 a
SALARIO-07, SALARIO-12 a SALARIO-14).
"""
import logging

from django.db import transaction

from core.texto import normalizar
from core.valores import dinheiro
from goals.services import GoalService
from transactions.models import Category

from .models import CONTA, CONTA_DO_SALARIO, META, GestaoDoSalario, ParteDoPlano

logger = logging.getLogger(__name__)

NOME_DO_SALARIO = 'salario'
FICA_NA_CONTA_DO_SALARIO = 'Fica na conta do salário'


def gestao_de(usuario):
    """A gestão do salário do usuário, ou `None` se ele nunca configurou."""
    return GestaoDoSalario.objects.filter(user=usuario).first()


def categorias_padrao(usuario):
    """
    As categorias de receita ativas do usuário chamadas "Salário" (sem
    diferença de maiúsculas e acentos) e as subcategorias delas (SALARIO-14).
    """
    receitas = list(Category.objects.filter(user=usuario, type='INCOME', is_active=True).values('id', 'name', 'parent_id'))
    escolhidas = {c['id'] for c in receitas if normalizar(c['name']) == NOME_DO_SALARIO}
    mudou = True
    while mudou:
        novas = {c['id'] for c in receitas if c['parent_id'] in escolhidas} - escolhidas
        escolhidas |= novas
        mudou = bool(novas)
    return escolhidas


def categorias_de_salario(usuario, gestao=None):
    """Os ids das categorias de salário: as configuradas ou, sem configuração, as padrão."""
    gestao = gestao if gestao is not None else gestao_de(usuario)
    if gestao is not None and gestao.categorias_configuradas:
        return set(gestao.categorias.values_list('id', flat=True))
    return categorias_padrao(usuario)


def partes_do_plano(usuario, gestao=None):
    """As partes do plano salvo, na ordem."""
    gestao = gestao if gestao is not None else gestao_de(usuario)
    if gestao is None:
        return []
    return list(gestao.partes.select_related('conta', 'meta', 'meta__account').order_by('ordem', 'pk'))


def nome_do_destino(tipo, conta, meta):
    """O nome mostrado para o destino da parte; sem destino, `None`."""
    if tipo == CONTA_DO_SALARIO:
        return FICA_NA_CONTA_DO_SALARIO
    if tipo == CONTA and conta is not None:
        return conta.name
    if tipo == META and meta is not None:
        return meta.name
    return None


@transaction.atomic
def salvar_plano(usuario, partes, categorias=None):
    """
    Substitui as partes do plano pelas `partes`, na ordem da lista
    (SALARIO-07, SALARIO-12), e, com `categorias`, as categorias de salário
    (SALARIO-14). Cada parte é o `validated_data` do `PlanPartSerializer`.
    """
    gestao, _ = GestaoDoSalario.objects.select_for_update().get_or_create(user=usuario)
    gestao.partes.all().delete()
    ParteDoPlano.objects.bulk_create([
        ParteDoPlano(
            gestao=gestao, ordem=ordem, nome=parte['name'], tipo_de_regra=parte['rule_type'],
            valor=parte['value'], tipo_de_destino=parte.get('destination_type'),
            conta=parte.get('account'), meta=parte.get('goal'), referencia=parte.get('reference') or '',
        )
        for ordem, parte in enumerate(partes)
    ])
    gestao.plano_salvo = True
    campos = ['plano_salvo', 'atualizada_em']
    if categorias is not None:
        gestao.categorias.set(categorias)
        gestao.categorias_configuradas = True
        campos.append('categorias_configuradas')
    gestao.save(update_fields=campos)
    # Só ids e quantidades (SALARIO-18, AD-019)
    logger.info('Plano do salário salvo usuario=%s partes=%s', usuario.pk, len(partes))
    return gestao


def parte_em_json(parte):
    """Uma parte do plano salvo na resposta da API."""
    meta = parte.meta if parte.tipo_de_destino == META else None
    mensal = None
    if meta is not None and meta.target_date:
        mensal = dinheiro(GoalService.get_progress(meta)['monthly_suggestion'])
    return {
        'id': str(parte.pk),
        'name': parte.nome,
        'rule_type': parte.tipo_de_regra,
        'value': dinheiro(parte.valor),
        'destination_type': parte.tipo_de_destino,
        'destination_name': nome_do_destino(parte.tipo_de_destino, parte.conta, parte.meta),
        'account': str(parte.conta_id) if parte.tipo_de_destino == CONTA and parte.conta_id else None,
        'goal': str(parte.meta_id) if meta is not None else None,
        'reference': parte.referencia,
        # Quanto a meta pede por mês para chegar na data-alvo (SALARIO-55)
        'goal_monthly_needed': mensal,
        'goal_target_date': meta.target_date.isoformat() if meta is not None and meta.target_date else None,
    }


def plano_em_json(usuario):
    """O corpo de `GET /salary/plan/`."""
    gestao = gestao_de(usuario)
    return {
        'has_plan': bool(gestao and gestao.plano_salvo),
        'parts': [parte_em_json(parte) for parte in partes_do_plano(usuario, gestao)],
        'salary_categories': sorted(str(pk) for pk in categorias_de_salario(usuario, gestao)),
    }


def item_em_json(item):
    """Um item calculado por `dividir` na simulação e na revisão."""
    parte = item.parte
    return {
        'part_id': str(parte.id) if getattr(parte, 'id', None) is not None else None,
        'name': parte.nome,
        'destination_type': parte.tipo_de_destino,
        'destination_name': nome_do_destino(parte.tipo_de_destino, getattr(parte, 'conta', None), getattr(parte, 'meta', None)),
        'amount': dinheiro(item.valor),
        'reduced': item.reduzida,
        'adjusted': item.ajustada,
        'generates_transaction': item.gera_transacao,
    }
