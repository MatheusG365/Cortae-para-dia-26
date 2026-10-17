"""Versioned terms, explicit account acceptance and transaction policy."""
import hashlib
import json
from flask import jsonify, request
from application import app, conectar_banco
from funcoes import decodificar_token

VERSAO = '2026-10-12.1'


class AceitePendente(ValueError):
    status = 428


def documento_termos():
    responsavel = {key: str(app.config.get(config) or '').strip() for key, config in (
        ('nome', 'TERMOS_RESPONSAVEL_NOME'), ('documento', 'TERMOS_RESPONSAVEL_DOCUMENTO'),
        ('contato', 'TERMOS_RESPONSAVEL_CONTATO'), ('endereco', 'TERMOS_RESPONSAVEL_ENDERECO'))}
    payer = app.config.get('PLATAFORMA_TAXA_PAGADOR')
    ready = all(responsavel.values()) and payer in ('cliente', 'barbearia')
    return {'versao': VERSAO, 'publicado_em': '2026-10-12', 'titulo': 'Termos de uso do Cortaê',
        'responsavel': responsavel, 'identificacao_pendente': not all(responsavel.values()),
        'estado_publicacao': 'publicado' if ready else 'rascunho', 'aceite_habilitado': ready,
        'taxa': {'percentual': 1.5, 'pagador': payer if payer in ('cliente', 'barbearia') else 'pendente',
                 'base': 'servicos_e_produtos_sem_frete', 'ativa': ready},
        'secoes': [
            {'titulo': '1. Plataforma e estabelecimentos', 'paragrafos': [
                'O Cortaê permite consultar estabelecimentos, agendar serviços e comprar produtos das lojas das barbearias. O estabelecimento identificado em cada oferta é responsável pelos serviços e produtos que disponibiliza.',
                'Confira a identificação, os detalhes da oferta, o profissional, os preços, a disponibilidade e, quando houver entrega, o endereço, o frete e o prazo apresentados antes de confirmar.']},
            {'titulo': '2. Conta e uso responsável', 'paragrafos': [
                'Informe dados corretos, mantenha seu contato atualizado e preserve sua senha. Não use contas de terceiros sem autorização, não publique conteúdo ilícito ou ofensivo e não tente acessar informações de outras contas ou estabelecimentos.',
                'Contas criadas por um administrador ou por uma barbearia não representam aceite automático do titular. O próprio usuário deve ler e aceitar a versão apresentada para realizar novas operações.']},
            {'titulo': '3. Taxa da plataforma', 'paragrafos': [
                'A taxa prevista é de 1,5% sobre o valor dos produtos ou serviços, sem incluir o frete. O cálculo ocorre uma única vez por operação, arredondando ao centavo mais próximo, com meio centavo arredondado para cima. Sobre R$ 100,00, a taxa é de R$ 1,50.',
                ('O cliente paga a taxa, acrescentada ao total de produtos ou serviços. O frete permanece separado.' if payer == 'cliente' else
                 'A barbearia é responsável pela taxa sobre seus produtos ou serviços. O preço total do cliente não recebe acréscimo por esta taxa.' if payer == 'barbearia' else
                 'O responsável pelo pagamento ainda não foi definido. Enquanto estes termos estiverem em rascunho, esta política não gera cobrança de taxa.'),
                'O resumo mostra a base de cálculo, o responsável pelo pagamento, a taxa em reais e o total antes da confirmação. O registro da taxa não significa transferência automática à plataforma.',
                'A taxa e as condições registradas na operação integram seu histórico. Uma alteração posterior de preços ou política não modifica operações anteriores.']},
            {'titulo': '4. Agendamentos', 'paragrafos': [
                'A confirmação depende da disponibilidade do profissional e da duração dos serviços. Cancelamento e reagendamento seguem os prazos informados pelo estabelecimento na reserva, respeitados os direitos legais aplicáveis.',
                'Compareça no horário escolhido. A barbearia pode registrar realização, cancelamento, reagendamento ou falta. Um reagendamento conserva o histórico da reserva; a ausência de prestação do serviço não autoriza retenções contrárias à lei.']},
            {'titulo': '5. Compras, pagamentos e entregas', 'paragrafos': [
                'Cada pedido é vinculado à loja indicada. O resumo discrimina produtos, quantidades, preço, frete e eventual taxa antes da confirmação. A criação de um pedido não significa confirmação de pagamento.',
                'O frete é calculado para o endereço informado. Prazos estimados e acompanhamento dependem da transportadora. A plataforma pode usar provedores de pagamento e de cotação ou rastreamento, conforme a operação disponibilizada.',
                'O consumidor pode exercer o direito de arrependimento nas hipóteses legais, em regra no prazo de sete dias em contratações fora do estabelecimento. Os direitos de cancelamento, devolução, garantia e restituição previstos em lei permanecem assegurados, incluindo a taxa quando a restituição integral for devida. Pedidos de cancelamento, devolução e restituição podem ser encaminhados aos contatos de atendimento informados. O estabelecimento e o suporte acompanham o pedido conforme o meio de pagamento, preservados os direitos legais.']},
            {'titulo': '6. Avaliações e dados pessoais', 'paragrafos': [
                'Avaliações devem refletir uma experiência real, sem divulgação indevida de dados pessoais. O tratamento de dados necessários à conta, aos serviços, às compras e às comunicações operacionais deve respeitar a legislação de proteção de dados.',
                'O aceite destes termos não é autorização genérica para publicidade nem consentimento irrestrito para tratar dados pessoais. Solicitações sobre dados e atendimento devem ser encaminhadas aos contatos informados pela plataforma e pelo estabelecimento.']},
            {'titulo': '7. Versões e atendimento', 'paragrafos': [
                'A versão e a data do aceite são registradas com o conteúdo apresentado. Alterações relevantes exigem novo aceite antes de novas operações. O usuário pode consultar estes termos a qualquer momento.',
                'As disposições destes termos não afastam direitos assegurados pela legislação brasileira nem impedem o acesso aos órgãos de defesa do consumidor e ao Poder Judiciário.']}
        ]}


def texto_documento():
    return json.dumps(documento_termos(), ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def versao_atual():
    # A change in identification or policy needs a new explicit acceptance too.
    return VERSAO + '-' + hashlib.sha256(texto_documento().encode()).hexdigest()[:12]


def estado_aceite(cur, id_usuario):
    cur.execute('SELECT ACEITO_EM,DOCUMENTO_HASH FROM TERMO_ACEITE WHERE ID_USUARIO=? AND VERSAO=?',
                (id_usuario, versao_atual()))
    row = cur.fetchone()
    valid = bool(row and row[1] == hashlib.sha256(texto_documento().encode()).hexdigest())
    return {'versao_atual': versao_atual(), 'aceito': valid,
            'aceite_habilitado': documento_termos()['aceite_habilitado'],
            'aceito_em': row[0].isoformat() if row and row[0] else None}


def registrar_aceite(cur, id_usuario, versao, aceito):
    if not documento_termos()['aceite_habilitado']:
        raise AceitePendente('Os termos estão em rascunho e ainda não estão disponíveis para aceite.')
    if aceito is not True or versao != versao_atual():
        raise AceitePendente('Leia e aceite a versão atual dos termos de uso.')
    cur.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? WITH LOCK', (id_usuario,))
    if not cur.fetchone():
        raise ValueError('Conta não encontrada.')
    cur.execute('SELECT VERSAO FROM TERMO_ACEITE WHERE ID_USUARIO=? AND VERSAO=?', (id_usuario, versao))
    if not cur.fetchone():
        document = texto_documento()
        cur.execute('INSERT INTO TERMO_ACEITE(ID_USUARIO,VERSAO,DOCUMENTO_HASH,DOCUMENTO) VALUES(?,?,?,?)',
                    (id_usuario, versao, hashlib.sha256(document.encode()).hexdigest(), document))


def exigir_aceite(cur, id_usuario):
    if not documento_termos()['aceite_habilitado']:
        return
    if not estado_aceite(cur, id_usuario)['aceito']:
        raise AceitePendente('Leia e aceite os termos de uso antes de continuar.')


def falha(texto, status):
    return jsonify(mensagem={'informacao': texto, 'tipo': 'erro'},
                   codigo='termos_aceite_pendente' if status == 428 else 'termos_erro',
                   termos_versao=versao_atual()), status


@app.get('/termos-uso')
def termos_publicos():
    result = documento_termos(); result['versao'] = versao_atual()
    return jsonify(result)


@app.route('/termos-uso/aceite', methods=['GET', 'POST'])
def aceitar_termos():
    user = decodificar_token()
    if not user:
        return falha('Faça login.', 401)
    con = conectar_banco(); cur = con.cursor()
    try:
        cur.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? AND ATIVO=1 AND EMAIL_CONFIRMADO=1',
                    (user['id_usuario'],))
        if not cur.fetchone():
            return falha('Faça login com uma conta ativa.', 401)
        if request.method == 'POST':
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return falha('Informe um objeto JSON válido.', 400)
            registrar_aceite(cur, user['id_usuario'], data.get('versao'), data.get('aceito'))
            con.commit()
            from auditoria import registrar_log
            registrar_log('ACEITE_TERMOS','TERMO_ACEITE',id_registro=user['id_usuario'],
                id_usuario=user['id_usuario'],campo='VERSAO',valor_depois=versao_atual())
        return jsonify(estado_aceite(cur, user['id_usuario']))
    except ValueError as exc:
        con.rollback(); return falha(str(exc), getattr(exc, 'status', 400))
    finally:
        cur.close(); con.close()
