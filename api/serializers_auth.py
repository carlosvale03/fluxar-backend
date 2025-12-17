from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from core.services.plan_limits import PlanLimitsService

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Adicionar claims customizadas
        token['email'] = user.email
        token['plan'] = PlanLimitsService.get_user_plan(user)
        
        # Futuramente: Nome, Avatar, etc.
        token['name'] = getattr(user, 'name', '')

        return token

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
