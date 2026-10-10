"""
Saúde do sistema medida na hora, para o painel admin (ADMIN-02).

O painel mostra só o que o backend mede: a API respondeu e o banco respondeu
a um `SELECT 1`, com a latência e a versão do servidor. Um erro do banco vira
`status` "error", sem latência e sem versão, em vez de um "Operacional" fixo.
"""
import time

from django.db import DatabaseError, connection


def _versao_legivel(numero):
    """`160004` vira "16.4"; `90624` (antes do PostgreSQL 10) vira "9.6.24"."""
    if numero is None:
        return None
    if numero >= 100000:
        return f'{numero // 10000}.{numero % 10000}'
    return f'{numero // 10000}.{numero // 100 % 100}.{numero % 100}'


def saude_do_banco():
    """`{status, latency_ms, version}` do banco, medidos agora."""
    inicio = time.perf_counter()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        latencia = int((time.perf_counter() - inicio) * 1000)
        versao = _versao_legivel(getattr(connection, 'pg_version', None))
    except DatabaseError:
        return {'status': 'error', 'latency_ms': None, 'version': None}
    return {'status': 'ok', 'latency_ms': latencia, 'version': versao}


def saude():
    """A saúde da API e do banco, no formato do dashboard do admin."""
    return {'api': 'ok', 'database': saude_do_banco()}
