"""Salon-owned targets measured against completed visits and historical service totals."""
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import request
from firebirdsql import DatabaseError

from application import app
from agenda_equipe import funcionario_logado
from agenda_gestao import GestaoErro, _auditar, _executar
from responses import mensagem_json


TIPOS_META = ('atendimentos', 'faturamento')
COLUNAS_META = '''M.ID_META,M.ID_FUNCIONARIO,F.NOME,M.TIPO,M.ALVO,
    M.INICIO,M.FIM,M.ATIVO,M.CRIADO_EM,M.ATUALIZADO_EM'''


def _executar_metas(handler, **opcoes):
    try:
        return _executar(handler, **opcoes)
    except DatabaseError as exc:
        if any(code in getattr(exc, 'gds_codes', ()) for code in (335544336, 335544345, 335544451, 335544665)):
            return mensagem_json('A meta foi alterada por outra requisição. Atualize a página e tente novamente.', 'erro'), 409
        raise


def _data(valor):
    if not isinstance(valor, str): raise GestaoErro('Informe a data no formato AAAA-MM-DD.')
    try:
        resultado = date.fromisoformat(valor)
        if resultado.isoformat() != valor: raise ValueError()
        return resultado
    except ValueError as exc:
        raise GestaoErro('Informe a data no formato AAAA-MM-DD.') from exc


def periodo_metas(dados):
    hoje = date.today()
    inicio = _data(dados.get('inicio', hoje.replace(day=1).isoformat()))
    fim = _data(dados.get('fim', hoje.replace(day=monthrange(hoje.year, hoje.month)[1]).isoformat()))
    if fim < inicio or (fim-inicio).days >= 366 or fim == date.max:
        raise GestaoErro('Informe um período de até 366 dias, com fim posterior ou igual ao início.')
    return inicio, fim


def validar_meta(dados):
    if not isinstance(dados, dict): raise GestaoErro('Envie os dados da meta.')
    profissional = dados.get('id_funcionario')
    if isinstance(profissional, bool) or not isinstance(profissional, int) or not 1 <= profissional <= 2147483647:
        raise GestaoErro('Selecione um profissional válido.')
    tipo = dados.get('tipo')
    if tipo not in TIPOS_META: raise GestaoErro('Escolha atendimentos ou faturamento.')
    valor = dados.get('alvo')
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str, Decimal)):
        raise GestaoErro('Informe um valor positivo para a meta.')
    try:
        alvo = Decimal(str(valor))
        if not alvo.is_finite() or alvo <= 0 or alvo > Decimal('999999999999.99'):
            raise InvalidOperation()
        if tipo == 'atendimentos' and (alvo != alvo.to_integral_value() or alvo > 1000000):
            raise GestaoErro('A meta de atendimentos deve ser um inteiro entre 1 e 1000000.')
        arredondado = alvo.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if alvo != arredondado: raise GestaoErro('Informe no máximo duas casas decimais.')
    except InvalidOperation as exc:
        raise GestaoErro('Informe um valor positivo válido para a meta.') from exc
    inicio, fim = periodo_metas(dados)
    ativo = dados.get('ativo', True)
    if not isinstance(ativo, bool): raise GestaoErro('O campo ativo deve ser verdadeiro ou falso.')
    return profissional, tipo, alvo, inicio, fim, int(ativo)


def calcular_progresso(tipo, alvo, valores):
    """Do not infer historical revenue from today's service price or payment receipts."""
    alvo = Decimal(str(alvo))
    realizados = len(valores)
    faltantes = sum(valor is None for valor in valores)
    faturamento = sum((Decimal(str(valor)) for valor in valores if valor is not None), Decimal('0.00'))
    realizado = Decimal(realizados) if tipo == 'atendimentos' else faturamento
    percentual = (realizado*100/alvo).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return {'realizado': int(realizado) if tipo == 'atendimentos' else float(realizado),
            'percentual': float(percentual), 'restante': float(max(alvo-realizado, Decimal(0))),
            'atingida': realizado >= alvo, 'atendimentos_realizados': realizados,
            'sem_valor_historico': faltantes,
            'aviso': 'Há atendimentos sem valor histórico; eles não entram no faturamento.' if faltantes else None}


def serializar_meta(cur, salon, row):
    inicio = datetime.combine(row[5], time.min)
    fim = datetime.combine(row[6]+timedelta(days=1), time.min)
    cur.execute('''SELECT VALOR_TOTAL FROM AGENDAMENTO WHERE ID_BARBEARIA=?
        AND ID_FUNCIONARIO=? AND STATUS='concluido' AND INICIO_EM>=?
        AND INICIO_EM<? AND FIM_EM<=?''', (salon, row[1], inicio, fim, datetime.now()))
    progresso = calcular_progresso(row[3], row[4], [r[0] for r in cur.fetchall()])
    return {'id_meta': row[0], 'id_funcionario': row[1], 'nome_profissional': row[2],
            'tipo': row[3], 'alvo': int(row[4]) if row[3] == 'atendimentos' else float(row[4]),
            'inicio': row[5].isoformat(), 'fim': row[6].isoformat(), 'ativo': bool(row[7]),
            'criado_em': row[8].isoformat(), 'atualizado_em': row[9].isoformat(), **progresso}


def obter_meta(cur, salon, id_meta):
    cur.execute(f'''SELECT {COLUNAS_META} FROM META_PROFISSIONAL M
        JOIN FUNCIONARIO F ON F.ID_FUNCIONARIO=M.ID_FUNCIONARIO AND F.ID_BARBEARIA=M.ID_BARBEARIA
        WHERE M.ID_META=? AND M.ID_BARBEARIA=?''', (id_meta, salon))
    row = cur.fetchone()
    if not row: raise GestaoErro('Meta não encontrada.', 404)
    return serializar_meta(cur, salon, row)


def _profissional(cur, salon, id_funcionario, novo=False):
    cur.execute('SELECT ATIVO FROM FUNCIONARIO WHERE ID_FUNCIONARIO=? AND ID_BARBEARIA=?', (id_funcionario, salon))
    row = cur.fetchone()
    if not row: raise GestaoErro('Profissional não encontrado nesta barbearia.', 404)
    if novo and not row[0]: raise GestaoErro('Escolha um profissional ativo.')


def listar_metas(cur, salon, profissional=None):
    inicio, fim = periodo_metas(request.args)
    filtro = request.args.get('id_funcionario')
    if filtro:
        try: filtrado = int(filtro)
        except (ValueError, TypeError): raise GestaoErro('Filtro de profissional inválido.')
        if filtrado < 1 or filtrado > 2147483647: raise GestaoErro('Filtro de profissional inválido.')
        if profissional is not None and filtrado != profissional: raise GestaoErro('Sem permissão para este profissional.', 403)
        _profissional(cur, salon, filtrado); profissional = filtrado
    sql = f'''SELECT {COLUNAS_META} FROM META_PROFISSIONAL M JOIN FUNCIONARIO F
        ON F.ID_FUNCIONARIO=M.ID_FUNCIONARIO AND F.ID_BARBEARIA=M.ID_BARBEARIA
        WHERE M.ID_BARBEARIA=? AND M.INICIO<=? AND M.FIM>=?'''
    params = [salon, fim, inicio]
    if profissional is not None:
        sql += ' AND M.ID_FUNCIONARIO=?'; params.append(profissional)
    cur.execute(sql+' ORDER BY M.ATIVO DESC,M.INICIO DESC,M.ID_META DESC', params)
    rows = cur.fetchall()
    return {'id_barbearia': salon, 'periodo': {'inicio': inicio.isoformat(), 'fim': fim.isoformat()},
            'metas': [serializar_meta(cur, salon, row) for row in rows]}


@app.route('/gestao/metas', methods=['GET', 'POST'])
def metas_da_equipe():
    def handler(cur, salon, usuario):
        if request.method == 'GET': return listar_metas(cur, salon)
        valores = validar_meta(request.get_json(silent=True) or {})
        _profissional(cur, salon, valores[0], novo=True)
        cur.execute('SELECT NEXT VALUE FOR GEN_META_PROFISSIONAL FROM RDB$DATABASE')
        id_meta = cur.fetchone()[0]
        cur.execute('''INSERT INTO META_PROFISSIONAL(ID_META,ID_BARBEARIA,ID_FUNCIONARIO,TIPO,ALVO,INICIO,FIM,ATIVO)
            VALUES(?,?,?,?,?,?,?,?)''', (id_meta, salon, *valores))
        meta = obter_meta(cur, salon, id_meta)
        _auditar('INSERT', 'META_PROFISSIONAL', id_registro=id_meta, id_usuario=usuario['id_usuario'], dados_depois=meta)
        return {'meta': meta, 'mensagem': {'informacao': 'Meta cadastrada.', 'tipo': 'sucesso'}}
    return _executar_metas(handler, escrita=request.method == 'POST')


@app.route('/gestao/metas/<int:id_meta>', methods=['PUT', 'PATCH'])
def editar_meta(id_meta):
    if not 1 <= id_meta <= 2147483647:
        return mensagem_json('Meta não encontrada.', 'erro'), 404
    def handler(cur, salon, usuario):
        antes = obter_meta(cur, salon, id_meta)
        dados = request.get_json(silent=True) or {}
        if request.method == 'PATCH':
            ativo = dados.get('ativo')
            if not isinstance(ativo, bool): raise GestaoErro('O campo ativo deve ser verdadeiro ou falso.')
            if ativo: _profissional(cur, salon, antes['id_funcionario'], novo=True)
            cur.execute('''UPDATE META_PROFISSIONAL SET ATIVO=?,ATUALIZADO_EM=CURRENT_TIMESTAMP
                WHERE ID_META=? AND ID_BARBEARIA=?''', (int(ativo), id_meta, salon))
        else:
            valores = validar_meta(dados)
            _profissional(cur, salon, valores[0], novo=bool(valores[5]))
            cur.execute('''UPDATE META_PROFISSIONAL SET ID_FUNCIONARIO=?,TIPO=?,ALVO=?,INICIO=?,FIM=?,ATIVO=?,
                ATUALIZADO_EM=CURRENT_TIMESTAMP WHERE ID_META=? AND ID_BARBEARIA=?''', (*valores, id_meta, salon))
        depois = obter_meta(cur, salon, id_meta)
        _auditar('UPDATE', 'META_PROFISSIONAL', id_registro=id_meta, id_usuario=usuario['id_usuario'], dados_antes=antes, dados_depois=depois)
        return {'meta': depois, 'mensagem': {'informacao': 'Meta atualizada.', 'tipo': 'sucesso'}}
    return _executar_metas(handler, escrita=True)


@app.get('/painel-barbeiro/metas')
def metas_do_profissional():
    def handler(cur, salon, usuario):
        if int(usuario.get('tipo', -1)) != 3: raise GestaoErro('Acesso exclusivo do profissional.', 403)
        fun = funcionario_logado(cur, usuario)
        if not fun or fun[1] != salon: raise GestaoErro('Profissional indisponível.', 403)
        return listar_metas(cur, salon, profissional=fun[0])
    return _executar_metas(handler, permitir_barbeiro=True)
