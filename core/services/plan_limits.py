from accounts.models import Account, CreditCard
# Futuramente importar UserProfile ou similar

class PlanLimitsService:
    # MVP: Constantes Hardcoded. Futuro: Tabela de Planos no DB.
    LIMITS = {
        'COMMON': {
            'ACCOUNTS': 999,
            'CREDIT_CARDS': 999,
            'ADVANCED_CHARTS': True
        },
        'PREMIUM': {
            'ACCOUNTS': 999,
            'CREDIT_CARDS': 999,
            'ADVANCED_CHARTS': True
        },
        'PREMIUM_PLUS': {
            'ACCOUNTS': 999,
            'CREDIT_CARDS': 999,
            'ADVANCED_CHARTS': True
        }
    }

    @staticmethod
    def get_user_plan(user):
        plan = 'COMMON'
        if hasattr(user, 'plan') and user.plan:
            plan = user.plan
        # Fallback para superuser -> Premium Plus
        if user.is_superuser:
            plan = 'PREMIUM_PLUS'
        print(f"[DEBUG] User {user.email} Plan: {plan}")
        return plan

    @classmethod
    def can_add_account(cls, user):
        plan = cls.get_user_plan(user)
        limit = cls.LIMITS.get(plan, cls.LIMITS['COMMON'])['ACCOUNTS']
        current_count = Account.objects.filter(user=user, is_active=True).count()
        print(f"[DEBUG] Check Account Limit: Count={current_count} Limit={limit} Allowed={current_count < limit}")
        return current_count < limit

    @classmethod
    def can_add_card(cls, user):
        plan = cls.get_user_plan(user)
        limit = cls.LIMITS.get(plan, cls.LIMITS['COMMON'])['CREDIT_CARDS']
        current_count = CreditCard.objects.filter(user=user, is_active=True).count()
        return current_count < limit

    @classmethod
    def allow_advanced_charts(cls, user):
        plan = cls.get_user_plan(user)
        return cls.LIMITS.get(plan, cls.LIMITS['COMMON'])['ADVANCED_CHARTS']
