class UserQuerySetMixin:
    """
    Mixin para ViewSets que garante que o queryset retornado
    seja sempre filtrado pelo usuário logado.
    """
    def get_queryset(self):
        # Pega o queryset base definido na View (ou corre o risco de pegar tudo se não definido)
        # É seguro assumir que self.queryset ou super().get_queryset() retornará o manager padrao.
        # Mas para garantir, chamamos super se existir, senão self.queryset.
        
        # Nota: DRF ViewSets chamam get_queryset.
        qs = super().get_queryset()
        return qs.filter(user=self.request.user)
