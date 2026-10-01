"""
Data de hoje no fuso de Brasília (AD-008).

O servidor roda em UTC; depois das 21h de Brasília o dia em UTC já virou, e
`hoje()` precisa continuar devolvendo o dia de Brasília.
"""
from datetime import date, datetime, timezone as dt_timezone
from unittest import mock

from django.test import SimpleTestCase

from core.datas import hoje


def relogio_em(*args):
    """Simula `timezone.now()` no instante UTC dado."""
    return mock.patch(
        'django.utils.timezone.now',
        return_value=datetime(*args, tzinfo=dt_timezone.utc),
    )


class HojeTests(SimpleTestCase):
    def test_as_2h_utc_ainda_e_o_dia_anterior_em_brasilia(self):
        with relogio_em(2026, 10, 1, 2, 0):
            self.assertEqual(hoje(), date(2026, 9, 30))

    def test_as_3h_utc_o_dia_ja_virou_em_brasilia(self):
        with relogio_em(2026, 10, 1, 3, 0):
            self.assertEqual(hoje(), date(2026, 10, 1))
