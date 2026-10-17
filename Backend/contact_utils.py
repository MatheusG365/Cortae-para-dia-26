"""Normalização textual compartilhada; cada rota mantém suas validações."""


def email_sem_espacos(email):
    return email.strip().replace(' ', '')


def digitos_telefone(telefone):
    return ''.join(filter(str.isdigit, telefone))
