"""
Filtro de dados pessoais nos logs (LGPD-21, LGPD-22, AD-019).

`FiltroDeDadosPessoais` fica ligado a todos os handlers de `LOGGING` e troca
e-mails e CPFs da mensagem pela forma mascarada. É uma defesa a mais: a regra
principal continua sendo não escrever o dado no log.
"""
import logging
import re

from api.utils.email_service import _mask_email

EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}')
CPF = re.compile(r'(?<![\d.-])\d{3}\.?\d{3}\.?\d{3}-?(\d{2})(?![\d-])')


def mascarar(texto):
    """O texto com os e-mails e os CPFs mascarados."""
    texto = EMAIL.sub(lambda achado: _mask_email(achado.group(0)), texto)
    return CPF.sub(lambda achado: f'***.***.***-{achado.group(1)}', texto)


class FiltroDeDadosPessoais(logging.Filter):

    def filter(self, record):
        try:
            mensagem = record.getMessage()
        except (TypeError, ValueError):
            # Formato quebrado: o handler mostra o erro de formatação como sempre
            return True
        mascarada = mascarar(mensagem)
        if mascarada != mensagem:
            record.msg = mascarada
            record.args = None
        # O traceback de um erro também pode trazer o dado na mensagem da exceção;
        # o Formatter usa o exc_text já pronto em vez de formatar de novo
        if record.exc_info and not record.exc_text:
            record.exc_text = mascarar(logging.Formatter().formatException(record.exc_info))
        return True
