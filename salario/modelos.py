"""
Modelos da literatura para começar o plano (SALARIO-01 a SALARIO-03,
SALARIO-06).

Cada modelo tem o código, o nome, a obra de origem e as partes, na ordem de
prioridade. Nos três modelos, as partes de gastar ficam na conta do salário
e as de guardar ficam sem destino, até o usuário escolher (SALARIO-06). A
referência liga a parte à classe de despesa do histórico (SALARIO-54).
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .models import CONTA_DO_SALARIO, DISPENSAVEL, ESSENCIAL, PERCENTUAL


@dataclass(frozen=True)
class ParteDoModelo:
    nome: str
    percentual: Decimal
    tipo_de_destino: Optional[str]
    referencia: str = ''


@dataclass(frozen=True)
class Modelo:
    codigo: str
    nome: str
    autor: Optional[str]
    obra: Optional[str]
    partes: tuple


def _gastar(nome, percentual, referencia=''):
    return ParteDoModelo(nome, Decimal(percentual), CONTA_DO_SALARIO, referencia)


def _guardar(nome, percentual):
    return ParteDoModelo(nome, Decimal(percentual), None)


MODELOS = (
    Modelo(
        'pague_se_primeiro', 'Pague-se primeiro', 'George S. Clason', 'O Homem Mais Rico da Babilônia',
        (_guardar('Guardar', '10'),),
    ),
    Modelo(
        '50_30_20', '50/30/20', 'Elizabeth Warren e Amelia Warren Tyagi', 'All Your Worth',
        (
            _gastar('Essenciais', '50', ESSENCIAL),
            _gastar('Dispensáveis', '30', DISPENSAVEL),
            _guardar('Guardar', '20'),
        ),
    ),
    Modelo(
        'seis_potes', 'Seis potes', 'T. Harv Eker', 'Os Segredos da Mente Milionária',
        (
            _gastar('Necessidades', '55', ESSENCIAL),
            _guardar('Liberdade financeira', '10'),
            _guardar('Poupança para gastos futuros', '10'),
            _gastar('Educação', '10'),
            _gastar('Diversão', '10', DISPENSAVEL),
            _gastar('Doações', '5'),
        ),
    ),
    Modelo('personalizado', 'Personalizado', None, None, ()),
)

POR_CODIGO = {modelo.codigo: modelo for modelo in MODELOS}
REGRA_DOS_MODELOS = PERCENTUAL
