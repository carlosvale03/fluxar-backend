"""
Executor da suíte de testes (`TEST_RUNNER`).

Com o bloqueio dos termos (LGPD-29), um usuário sem o aceite da versão
vigente recebe 403 em quase todas as rotas. Nos testes, todo usuário criado
por `User.objects.create_user` já nasce com o aceite da versão vigente, como
um usuário que aceitou os termos no cadastro; os testes do bloqueio criam o
usuário sem o aceite passando `versao_dos_termos_aceita=None`.
"""
from django.test.runner import DiscoverRunner

from api.models import UserManager
from core import termos


class ExecutorDeTestes(DiscoverRunner):

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._create_user_original = UserManager.create_user

        original = self._create_user_original

        def create_user_com_aceite(manager, email, password=None, **extra_fields):
            extra_fields.setdefault('versao_dos_termos_aceita', termos.VERSAO_VIGENTE)
            return original(manager, email, password, **extra_fields)

        UserManager.create_user = create_user_com_aceite

    def teardown_test_environment(self, **kwargs):
        UserManager.create_user = self._create_user_original
        super().teardown_test_environment(**kwargs)
