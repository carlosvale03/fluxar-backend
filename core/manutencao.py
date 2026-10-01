"""
Estado do modo manutenção com cache em memória (SESSAO-24 e SESSAO-25).

Cada processo lê a `GlobalSetting` `maintenance_mode` no máximo uma vez a cada
30 segundos e guarda o valor em memória. Assim, ligar ou desligar a manutenção
vale para todos os processos em até 30 segundos, sem uma consulta ao banco em
cada requisição. `invalidar()` descarta o valor guardado.
"""
import time

from api.models import GlobalSetting

TTL = 30

_valor = False
_lido_em = None


def manutencao_ligada():
    """True quando a configuração `maintenance_mode` vale 'true', sem distinguir maiúsculas."""
    global _valor, _lido_em
    agora = time.monotonic()
    if _lido_em is None or agora - _lido_em >= TTL:
        valor = GlobalSetting.objects.filter(key='maintenance_mode').values_list('value', flat=True).first()
        _valor = (valor or '').lower() == 'true'
        _lido_em = agora
    return _valor


def invalidar():
    """Faz a próxima chamada ler o banco de novo."""
    global _lido_em
    _lido_em = None
