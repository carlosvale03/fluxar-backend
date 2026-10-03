from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from .models import Account, CreditCard, CreditCardInvoice
from .serializers import (
    AccountSerializer, CreditCardSerializer, 
    CreditCardInvoiceSerializer, InvoicePaymentSerializer
)
from .faturas import resposta_do_pagamento
from .services import AccountService, CreditCardService
from core.datas import hoje
from core.fields import CONTA_NAO_ENCONTRADA
from core.mixins import UserQuerySetMixin
from core.valores import ler_saldo
from transactions.models import Transaction

# Exclusão de conta (SALDO-32, SALDO-33, AD-003)
SALDO_NAO_ZERADO = 'Zere o saldo antes de excluir a conta: transfira ou ajuste o valor restante.'
COM_PENDENTES = 'Resolva as transações pendentes antes de excluir a conta: efetive, mova ou exclua cada uma.'
SALDO_JA_NESSE_VALOR = 'O saldo já está nesse valor.'

class AccountViewSet(UserQuerySetMixin, viewsets.ModelViewSet):
    """
    CRUD de Contas (Checking, Savings, Wallet, Investment).
    """
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)
        return qs

    def destroy(self, request, *args, **kwargs):
        """Só exclui a conta com saldo zero e sem transações pendentes."""
        conta = self.get_object()
        if conta.balance != 0:
            return Response({'detail': SALDO_NAO_ZERADO}, status=status.HTTP_400_BAD_REQUEST)
        if conta.transactions.filter(status='PENDING').exists():
            return Response({'detail': COM_PENDENTES}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        # Soft delete: as transações efetivadas continuam no histórico (SALDO-34)
        instance.is_active = False
        instance.save()

    @action(detail=True, methods=['post'], url_path='adjust-balance')
    def adjust_balance(self, request, pk=None):
        """
        Ajuste de saldo (SALDO-40 a SALDO-42): o usuário informa o novo saldo
        e a diferença, em decimal, vira uma transação efetivada com a data de
        hoje. A conta excluída do próprio usuário recebe 400 (SALDO-35); a de
        outro usuário, 404, como um ID inexistente (AD-010).
        """
        novo_saldo = ler_saldo(request.data.get('new_balance'))
        conta = get_object_or_404(
            Account.objects.select_for_update(), pk=pk, user=request.user,
        )
        if not conta.is_active:
            return Response({'detail': CONTA_NAO_ENCONTRADA}, status=status.HTTP_400_BAD_REQUEST)

        diferenca = novo_saldo - conta.balance
        if diferenca == 0:
            return Response({'message': SALDO_JA_NESSE_VALOR})

        Transaction.objects.create(
            user=request.user, account=conta,
            type='INCOME' if diferenca > 0 else 'EXPENSE',
            amount=abs(diferenca), status='COMPLETED', date=hoje(),
            description='Ajuste de saldo',
        )
        conta.refresh_from_db()
        return Response(self.get_serializer(conta).data, status=status.HTTP_201_CREATED)


class CreditCardViewSet(UserQuerySetMixin, viewsets.ModelViewSet):
    """
    CRUD de Cartões de Crédito.
    """
    queryset = CreditCard.objects.all()
    serializer_class = CreditCardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)

    def perform_destroy(self, instance):
        # Soft delete
        # TODO: Validar se não há faturas abertas com dívida antes de deletar
        instance.is_active = False
        instance.save()

    @action(detail=True, methods=['get'])
    def invoices(self, request, pk=None):
        """
        Lista todas as faturas de um cartão específico.
        """
        card = self.get_object()
        invoices = CreditCardInvoice.objects.filter(card=card).order_by('-year', '-month')
        serializer = CreditCardInvoiceSerializer(invoices, many=True)
        return Response(serializer.data)

class CreditCardInvoiceViewSet(UserQuerySetMixin, viewsets.ModelViewSet):
    """
    Listagem e Ações em Faturas.
    Nota: A listagem geral pode ser filtrada, ou usamos a sub-rota no CreditCardViewSet.
    Aqui servirá principalmente para actions como 'pay'.
    """
    queryset = CreditCardInvoice.objects.all()
    serializer_class = CreditCardInvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options'] # Não permitir delete/put arbitrário por enquanto

    def get_queryset(self):
        # Garante que só vê faturas dos seus cartões
        return CreditCardInvoice.objects.filter(card__user=self.request.user).order_by('-year', '-month')

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        # A fatura paga é recusada dentro do service, sob trava, depois de
        # conferir a chave: a repetição da mesma tentativa recebe a resposta
        # original (FATURA-30, FATURA-33)
        invoice = self.get_object()
        serializer = InvoicePaymentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        # Recusas viram 400 no service; erro inesperado sobe como 500 e o
        # atomic desfaz tudo (FATURA-28)
        pagamento = CreditCardService.pay_invoice(
            user=request.user,
            invoice=invoice,
            account=data['account_id'],
            amount=data['amount'],
            date=data['date'],
            chave=data.get('idempotency_key'),
        )
        return Response(resposta_do_pagamento(pagamento))

    @action(detail=True, methods=['post'])
    def unpay(self, request, pk=None):
        invoice = self.get_object()
        # Recusas viram 400 no service, sob trava (SALDO-27, FATURA-38); erro
        # inesperado sobe como 500 e o atomic desfaz tudo (FATURA-28)
        CreditCardService.unpay_invoice(request.user, invoice)
        return Response({'status': 'Pagamento estornado. Fatura reaberta.'})
