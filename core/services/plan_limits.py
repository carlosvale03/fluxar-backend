from accounts.models import Account, CreditCard
# Futuramente importar UserProfile ou similar

class PlanLimitsService:
    # MVP: Constantes Hardcoded. Futuro: Tabela de Planos no DB.
    LIMITS = {
        'FREE': {
            'ACCOUNTS': 2,
            'CREDIT_CARDS': 1,
            'ADVANCED_CHARTS': False
        },
        'PREMIUM': {
            'ACCOUNTS': 6,
            'CREDIT_CARDS': 3,
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
        plan = 'FREE'
        if hasattr(user, 'profile') and user.profile.plan:
            plan = user.profile.plan
        # Fallback para superuser -> Premium Plus
        if user.is_superuser:
            plan = 'PREMIUM_PLUS'
        print(f"[DEBUG] User {user.email} Plan: {plan}")
        return plan

    @classmethod
    def can_add_account(cls, user):
        plan = cls.get_user_plan(user)
        limit = cls.LIMITS.get(plan, cls.LIMITS['FREE'])['ACCOUNTS']
        current_count = Account.objects.filter(user=user, is_active=True).count()
        print(f"[DEBUG] Check Account Limit: Count={current_count} Limit={limit} Allowed={current_count < limit}")
        return current_count < limit

    @classmethod
    def can_add_card(cls, user):
        plan = cls.get_user_plan(user)
        limit = cls.LIMITS.get(plan, cls.LIMITS['FREE'])['CREDIT_CARDS']
        current_count = CreditCard.objects.filter(user=user, is_active=True).count()
        return current_count < limit

    @classmethod
    def allow_advanced_charts(cls, user):
        plan = cls.get_user_plan(user)
        return cls.LIMITS.get(plan, cls.LIMITS['FREE'])['ADVANCED_CHARTS']
