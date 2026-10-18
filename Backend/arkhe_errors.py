"""Safe explanations for upstream outages; never retry financial writes here."""


def mensagem_indisponivel(status=None, criacao=False):
    codigo = f' (HTTP {status})' if isinstance(status, int) else ''
    mensagem = f'A Arkhé está temporariamente indisponível{codigo}.'
    if criacao:
        return mensagem + ' Não foi possível confirmar a geração da cobrança. Confira as cobranças na Arkhé antes de tentar novamente.'
    return mensagem + ' Tente consultar novamente mais tarde.'
