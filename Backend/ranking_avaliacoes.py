"""Historical salon rankings and a customer's one editable rating per visit."""
from responses import mensagem_json
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from flask import jsonify, request
from firebirdsql import DatabaseError

from application import app, conectar_banco
from funcoes import decodificar_token
from auditoria import registrar_log
from agenda_gestao import GestaoErro, _executar
from agenda_equipe import dinheiro, travar_agendamento


CRITERIOS = ('faturamento', 'atendimentos', 'avaliacao')


def periodo_solicitado():
    """Inclusive calendar dates, with the same 366-day limit as team reports."""
    from visagismo import parse_data
    inicio = parse_data(request.args['inicio']) if request.args.get('inicio') else date.today().replace(day=1)
    fim = parse_data(request.args['fim']) if request.args.get('fim') else date.today()
    if fim < inicio or (fim-inicio).days > 366 or fim == date.max:
        raise GestaoErro('Informe um período válido de até 366 dias.')
    return inicio, fim, datetime.combine(inicio, time.min), datetime.combine(fim+timedelta(days=1), time.min)


def atendimento_avaliavel(linha, agora=None):
    return bool(linha and linha[9] == 'concluido' and linha[5] <= (agora or datetime.now()))


def serializar_avaliacao(row):
    if not row: return None
    return {'nota': int(row[0]), 'comentario': row[1] or '',
            'criado_em': row[2].isoformat(), 'atualizado_em': row[3].isoformat()}


def obter_avaliacao(cursor, id_agendamento):
    cursor.execute('''SELECT NOTA,COMENTARIO,CRIADO_EM,ATUALIZADO_EM
        FROM AGENDAMENTO_AVALIACAO WHERE ID_AGENDAMENTO=?''', (id_agendamento,))
    return serializar_avaliacao(cursor.fetchone())


def dados_avaliacao(cursor, linha):
    elegivel = atendimento_avaliavel(linha)
    return {'avaliacao': obter_avaliacao(cursor, linha[0]) if elegivel else None,
            'pode_avaliar': elegivel}


def validar_avaliacao(dados):
    nota = dados.get('nota')
    if isinstance(nota, bool) or not isinstance(nota, int) or not 1 <= nota <= 5:
        raise GestaoErro('Selecione uma nota inteira entre 1 e 5.')
    comentario = dados.get('comentario', '')
    if not isinstance(comentario, str) or len(comentario) > 1000:
        raise GestaoErro('O comentário deve ser um texto de até 1000 caracteres.')
    return nota, comentario.strip()


def _erro(texto, status=400):
    return mensagem_json(texto, 'erro'), status


@app.route('/agendamentos/<int:id_agendamento>/avaliacao', methods=['GET', 'PUT'])
def avaliacao_atendimento(id_agendamento):
    usuario = decodificar_token()
    if not usuario: return _erro('Faça login para avaliar seu atendimento.', 401)
    if int(usuario.get('tipo', -1)) != 1:
        return _erro('Somente o cliente pode avaliar seu próprio atendimento.', 403)
    con = conectar_banco(); cur = con.cursor()
    try:
        if request.method == 'PUT':
            nota, comentario = validar_avaliacao(request.get_json(silent=True) or {})
            # The established salon/booking lock order also serializes concurrent ratings.
            linha = travar_agendamento(cur, id_agendamento)
        else:
            from visagismo import buscar_agendamento
            linha = buscar_agendamento(cur, id_agendamento)
        if not linha or int(linha[1]) != int(usuario['id_usuario']):
            raise GestaoErro('Atendimento não encontrado.', 404)
        if request.method == 'GET': return jsonify(dados_avaliacao(cur, linha))
        if not atendimento_avaliavel(linha):
            raise GestaoErro('A avaliação fica disponível após o término de um atendimento concluído.', 409)
        antes = obter_avaliacao(cur, id_agendamento)
        # Do not overwrite CRIADO_EM on edits; the primary key prevents duplicate votes.
        if antes:
            cur.execute('''UPDATE AGENDAMENTO_AVALIACAO SET NOTA=?,COMENTARIO=?,
                ATUALIZADO_EM=CURRENT_TIMESTAMP WHERE ID_AGENDAMENTO=?''', (nota, comentario, id_agendamento))
        else:
            cur.execute('''INSERT INTO AGENDAMENTO_AVALIACAO(ID_AGENDAMENTO,NOTA,COMENTARIO)
                VALUES(?,?,?)''', (id_agendamento, nota, comentario))
        depois = obter_avaliacao(cur, id_agendamento)
        con.commit()
        registrar_log('UPDATE' if antes else 'INSERT', 'AGENDAMENTO_AVALIACAO',
                      id_registro=id_agendamento, id_usuario=usuario['id_usuario'],
                      dados_antes=antes, dados_depois=depois)
        return jsonify(avaliacao=depois, pode_avaliar=True,
                       mensagem={'informacao': 'Avaliação salva.', 'tipo': 'sucesso'})
    except (ValueError, TypeError, KeyError) as exc:
        con.rollback(); return _erro(str(exc), getattr(exc, 'status', 400))
    except DatabaseError as exc:
        con.rollback()
        # Concurrent updates can conflict under the server's transaction isolation.
        if any(code in getattr(exc, 'gds_codes', []) for code in (335544336, 335544345, 335544451, 335544665)):
            return _erro('A avaliação foi atualizada em outra requisição. Atualize a página e tente novamente.', 409)
        raise
    finally:
        cur.close(); con.close()


def calcular_ranking(profissionais, atendimentos, criterio):
    """No current prices: only immutable booking totals, including explicit missing values."""
    if criterio not in CRITERIOS: raise GestaoErro('Critério de ranking inválido.')
    stats = {r[0]: {'id_funcionario': r[0], 'nome': r[1], 'ativo': bool(r[2]),
                  'atendimentos_realizados': 0, 'faturamento': Decimal('0.00'),
                  'sem_valor_historico': 0, 'total_avaliacoes': 0, '_notas': 0} for r in profissionais}
    sem_profissional = {'atendimentos_realizados': 0, 'faturamento': Decimal('0.00'), 'sem_valor_historico': 0}
    resumo = {'atendimentos_realizados': 0, 'faturamento': Decimal('0.00'),
              'sem_valor_historico': 0, 'total_avaliacoes': 0}
    notas = 0
    for id_fun, valor, nota in atendimentos:
        item = stats.get(id_fun, sem_profissional)
        item['atendimentos_realizados'] += 1; resumo['atendimentos_realizados'] += 1
        if valor is None:
            item['sem_valor_historico'] += 1; resumo['sem_valor_historico'] += 1
        else:
            total = dinheiro(valor); item['faturamento'] += total; resumo['faturamento'] += total
        if nota is not None:
            notas += int(nota); resumo['total_avaliacoes'] += 1
            if id_fun in stats:
                item['_notas'] += int(nota); item['total_avaliacoes'] += 1
    def valor_criterio(item):
        if criterio == 'faturamento': return item['faturamento']
        if criterio == 'atendimentos': return item['atendimentos_realizados']
        # Compare exact averages, not rounded display values; unrated comes last.
        return Decimal(item['_notas'])/item['total_avaliacoes'] if item['total_avaliacoes'] else Decimal('-1')
    ordenados = sorted(stats.values(), key=lambda item: (-valor_criterio(item), item['nome'].casefold(), item['id_funcionario']))
    ultimo = None; posicao = None
    for indice, item in enumerate(ordenados, 1):
        valor = valor_criterio(item)
        if valor != ultimo: posicao = indice
        item['posicao'] = posicao; ultimo = valor
        item['media_nota'] = round(item.pop('_notas')/item['total_avaliacoes'], 2) if item['total_avaliacoes'] else None
        item['faturamento'] = float(item['faturamento'])
    resumo['faturamento'] = float(resumo['faturamento'])
    resumo['media_nota'] = round(notas/resumo['total_avaliacoes'], 2) if resumo['total_avaliacoes'] else None
    sem_profissional['faturamento'] = float(sem_profissional['faturamento'])
    resumo['sem_profissional'] = sem_profissional
    return resumo, ordenados


@app.get('/gestao/ranking')
def ranking_profissionais():
    def handler(cur, salon, usuario):
        inicio, fim, a, b = periodo_solicitado()
        criterio = request.args.get('ordenar', 'faturamento')
        if criterio not in CRITERIOS: raise GestaoErro('Critério de ranking inválido.')
        cur.execute('SELECT ID_FUNCIONARIO,NOME,ATIVO FROM FUNCIONARIO WHERE ID_BARBEARIA=?', (salon,))
        profissionais = cur.fetchall()
        cur.execute('''SELECT A.ID_FUNCIONARIO,A.VALOR_TOTAL,V.NOTA FROM AGENDAMENTO A
            LEFT JOIN AGENDAMENTO_AVALIACAO V ON V.ID_AGENDAMENTO=A.ID_AGENDAMENTO
            WHERE A.ID_BARBEARIA=? AND A.STATUS='concluido' AND A.INICIO_EM>=?
            AND A.INICIO_EM<? AND A.FIM_EM<=?''', (salon, a, b, datetime.now()))
        resumo, ranking = calcular_ranking(profissionais, cur.fetchall(), criterio)
        return {'id_barbearia': salon, 'periodo': {'inicio': inicio.isoformat(), 'fim': fim.isoformat()},
                'criterio': criterio, 'resumo': resumo, 'profissionais': ranking}
    return _executar(handler)


def resumo_avaliacoes(cursor, salon, funcionario, inicio, fim):
    cursor.execute('''SELECT COUNT(V.NOTA),AVG(CAST(V.NOTA AS DECIMAL(8,4)))
        FROM AGENDAMENTO_AVALIACAO V JOIN AGENDAMENTO A ON A.ID_AGENDAMENTO=V.ID_AGENDAMENTO
        WHERE A.ID_BARBEARIA=? AND A.ID_FUNCIONARIO=? AND A.STATUS='concluido'
        AND A.INICIO_EM>=? AND A.INICIO_EM<? AND A.FIM_EM<=?''', (salon, funcionario, inicio, fim, datetime.now()))
    row = cursor.fetchone()
    return {'total_avaliacoes': int(row[0]), 'media_nota': round(float(row[1]), 2) if row[1] is not None else None}


@app.get('/gestao/avaliacoes')
def avaliacoes_da_equipe():
    def handler(cur, salon, usuario):
        inicio, fim, a, b = periodo_solicitado()
        try:
            pagina = int(request.args.get('pagina', '1'))
            funcionario = int(request.args['id_funcionario']) if request.args.get('id_funcionario') else None
        except (ValueError, TypeError): raise GestaoErro('Filtro de avaliações inválido.')
        if pagina < 1 or pagina > 1000000 or (funcionario is not None and funcionario < 1):
            raise GestaoErro('Filtro de avaliações inválido.')
        if funcionario:
            cur.execute('SELECT ID_FUNCIONARIO FROM FUNCIONARIO WHERE ID_FUNCIONARIO=? AND ID_BARBEARIA=?', (funcionario, salon))
            if not cur.fetchone(): raise GestaoErro('Profissional não encontrado.', 404)
        where = '''WHERE A.ID_BARBEARIA=? AND A.STATUS='concluido' AND A.INICIO_EM>=?
            AND A.INICIO_EM<? AND A.FIM_EM<=?'''
        params = [salon, a, b, datetime.now()]
        if funcionario: where += ' AND A.ID_FUNCIONARIO=?'; params.append(funcionario)
        join = 'FROM AGENDAMENTO_AVALIACAO V JOIN AGENDAMENTO A ON A.ID_AGENDAMENTO=V.ID_AGENDAMENTO '
        cur.execute(f'SELECT COUNT(*) {join} {where}', params); total = cur.fetchone()[0]
        cur.execute(f'''SELECT FIRST 20 SKIP {(pagina-1)*20} A.ID_AGENDAMENTO,A.ID_FUNCIONARIO,F.NOME,U.NOME,A.INICIO_EM,
            V.NOTA,V.COMENTARIO,V.CRIADO_EM,V.ATUALIZADO_EM {join}
            LEFT JOIN FUNCIONARIO F ON F.ID_FUNCIONARIO=A.ID_FUNCIONARIO AND F.ID_BARBEARIA=A.ID_BARBEARIA
            LEFT JOIN USUARIO U ON U.ID_USUARIO=A.ID_USUARIO {where}
            ORDER BY V.ATUALIZADO_EM DESC,A.ID_AGENDAMENTO DESC''', params)
        avaliacoes = [{'id_agendamento': row[0], 'id_funcionario': row[1], 'funcionario_nome': row[2],
                       'cliente_nome': row[3], 'inicio_em': row[4].isoformat(), **serializar_avaliacao(row[5:])} for row in cur.fetchall()]
        return {'periodo': {'inicio': inicio.isoformat(), 'fim': fim.isoformat()}, 'avaliacoes': avaliacoes,
                'pagina': pagina, 'total': total, 'paginas': (total+19)//20}
    return _executar(handler)
