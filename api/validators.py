from django.contrib.auth.password_validation import UserAttributeSimilarityValidator


class SenhaParecidaValidator(UserAttributeSimilarityValidator):
    """
    O validador do Django com a mensagem terminada em ponto, como as outras
    mensagens de senha. A tradução pt-BR do Django sai sem o ponto (AUTH-04).
    """

    def get_error_message(self):
        return 'A senha é muito parecida com %(verbose_name)s.'
