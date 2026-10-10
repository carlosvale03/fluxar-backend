"""
Nome das imagens enviadas ao Cloudinary (LGPD-20).

O nome original do arquivo pode conter o nome da pessoa; antes do envio, a
imagem recebe um nome aleatório com a mesma extensão.
"""
import os
import uuid

from django.core.files.uploadedfile import UploadedFile


def com_nome_aleatorio(arquivo):
    """Troca o nome do arquivo enviado por um aleatório e devolve o arquivo."""
    if isinstance(arquivo, UploadedFile):
        extensao = os.path.splitext(arquivo.name or '')[1].lower()
        arquivo.name = f'{uuid.uuid4().hex}{extensao}'
    return arquivo
