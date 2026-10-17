"""Identificação exata de um atendimento em descrições financeiras locais."""
import re

_REFERENCIA = re.compile(r'(?:^|\s)ag#(\d+)(?:\s|\||$)')


def id_agendamento_descricao(descricao):
    match = _REFERENCIA.search(str(descricao or ''))
    return int(match.group(1)) if match else None
