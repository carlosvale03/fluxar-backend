"""
Versão do sistema em execução, lida da configuração do deploy (AD-051).

`APP_VERSION` é opcional e definida à mão no painel do Render; sem ela, vale
o commit do deploy, que o Render preenche em `RENDER_GIT_COMMIT`; sem as
duas, como no ambiente local, "desenvolvimento".
"""
import os

SEM_VERSAO = 'desenvolvimento'


def ler_versao(ambiente=None):
    """A versão do deploy a partir das variáveis de `ambiente` (padrão: `os.environ`)."""
    ambiente = os.environ if ambiente is None else ambiente
    versao = (ambiente.get('APP_VERSION') or '').strip()
    if versao:
        return versao
    commit = (ambiente.get('RENDER_GIT_COMMIT') or '').strip()
    if commit:
        return commit[:7]
    return SEM_VERSAO
