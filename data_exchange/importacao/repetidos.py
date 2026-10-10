"""
Linhas já importadas (IMPORT-34 a IMPORT-38).

Conta, por chave, quantas transações iguais a conta já tem e consome essa
contagem na ordem do arquivo: enquanto houver saldo, a linha é ignorada;
depois, é gravada. Assim N linhas iguais contra M existentes gravam N − M.
A consulta fica limitada às contas e ao período das linhas válidas.
"""
from collections import Counter

from transactions.models import Transaction


def chave(conta_id, data, valor, tipo, descricao):
    return (conta_id, data, valor, tipo, descricao)


def transacoes_existentes(usuario, linhas):
    """
    As transações do usuário nas contas das linhas (a origem, na
    transferência), entre a menor e a maior data delas.
    """
    if not linhas:
        return Transaction.objects.none()
    datas = [linha.data for linha in linhas]
    return Transaction.objects.filter(
        user=usuario,
        account_id__in={linha.conta.pk for linha in linhas},
        date__range=(min(datas), max(datas)),
    )


class Repetidos:
    """
    Carrega as transações existentes uma vez, a partir das linhas válidas do
    arquivo, e diz para cada linha, na ordem do arquivo, se ela é repetida.
    Deve ser criado depois da trava das contas (IMPORT-39).
    """

    def __init__(self, usuario, linhas):
        existentes = transacoes_existentes(usuario, linhas)
        self.fitids = set()      # (conta, fitid) já gravados (IMPORT-34)
        self.sem_fitid = Counter()  # chaves das gravadas sem FITID (IMPORT-35)
        self.todas = Counter()      # chaves de todas as receitas e despesas (IMPORT-36)
        self.transferencias = Counter()  # (origem, destino, data, valor) (IMPORT-37)

        # Um envio que mistura os tipos carrega os dois contadores (IMPCOMP-46)
        if any(linha.tipo == 'TRANSFER' for linha in linhas):
            self.carregar_transferencias(usuario, existentes)
        if any(linha.tipo != 'TRANSFER' for linha in linhas):
            campos = ('account_id', 'date', 'amount', 'type', 'description', 'fitid')
            for conta, data, valor, tipo, descricao, fitid in existentes.values_list(*campos):
                k = chave(conta, data, valor, tipo, descricao)
                self.todas[k] += 1
                if fitid is None:
                    self.sem_fitid[k] += 1
                else:
                    self.fitids.add((conta, fitid))

    def carregar_transferencias(self, usuario, existentes):
        saidas = list(existentes.filter(type='TRANSFER_OUT').values_list('transfer_id', 'account_id', 'date', 'amount'))
        destinos = dict(Transaction.objects.filter(
            user=usuario, type='TRANSFER_IN', transfer_id__in=[s[0] for s in saidas if s[0]],
        ).values_list('transfer_id', 'account_id'))
        for transfer_id, origem, data, valor in saidas:
            self.transferencias[(origem, destinos.get(transfer_id), data, valor)] += 1

    @staticmethod
    def consumir(contagem, k):
        if contagem[k] > 0:
            contagem[k] -= 1
            return True
        return False

    def marcar(self, linhas):
        """
        Para cada linha, na ordem, se ela seria ignorada como repetida, sem
        gravar nada; a análise usa para o estado REPETIDA (IMPCOMP-31). Consome
        a contagem: use uma instância nova para cada análise.
        """
        return [self.ignorar(linha) for linha in linhas]

    def ignorar(self, linha):
        """Se a linha é repetida, consumindo uma unidade da contagem da chave dela."""
        if linha.tipo == 'TRANSFER':
            k = (linha.conta.pk, linha.destino.pk, linha.data, linha.valor)
            return self.consumir(self.transferencias, k)

        k = chave(linha.conta.pk, linha.data, linha.valor, linha.tipo, linha.descricao)
        if not linha.ofx:
            return self.consumir(self.todas, k)

        if linha.fitid is not None:
            if (linha.conta.pk, linha.fitid) in self.fitids:
                return True
            # O mesmo FITID repetido no arquivo também é ignorado
            self.fitids.add((linha.conta.pk, linha.fitid))
        # Importações antigas não guardavam o FITID (IMPORT-35)
        return self.consumir(self.sem_fitid, k)
