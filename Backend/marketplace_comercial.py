"""Commercial rules shared by catalog, checkout and owner reports.

All connections and transactions belong to marketplace.py. Costs never enter
customer snapshots or catalog responses; historical costs use a private table.
"""
import csv
import io
import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from flask import jsonify, request, Response
from gestao import dinheiro, inteiro, texto, Conflito

CENT = Decimal('0.01')
META_COLS = 'ID_FORNECEDOR,CUSTO_COMPRA,PROMOCAO_PRECO,PROMOCAO_INICIO,PROMOCAO_FIM,LANCAMENTO_ATE'
VAR_COLS = 'ID_VARIACAO,ID_PRODUTO,NOME,SKU,TAMANHO,COR,VOLUME,PRECO,CUSTO_COMPRA,ESTOQUE,ATIVO'


def day(value, optional=False):
    if optional and value in (None, ''):
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Use uma data válida no formato AAAA-MM-DD.')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('Data inválida.') from None


def cost(value):
    if value in (None, ''):
        return None
    result = dinheiro(value)
    if result < 0:
        raise ValueError('Preço de compra não pode ser negativo.')
    return result


def margin(price, purchase):
    if purchase is None:
        return None
    price = dinheiro(price, True)
    return float(((price - dinheiro(purchase)) / price * 100).quantize(CENT, rounding=ROUND_HALF_UP))


def metadata(cur, product):
    cur.execute('SELECT '+META_COLS+' FROM MP_COMERCIAL WHERE ID_PRODUTO=?', (product,))
    row = cur.fetchone()
    return dict(zip(('id_fornecedor','custo_compra','promocao_preco','promocao_inicio','promocao_fim','lancamento_ate'), row or (None,)*6))


def effective_price(price, meta, base=None, today=None):
    price = dinheiro(price, True)
    today = today or date.today()
    promo = meta.get('promocao_preco')
    start, end = meta.get('promocao_inicio'), meta.get('promocao_fim')
    if promo is None or start is None or end is None or not start <= today <= end:
        return price
    base = dinheiro(base if base is not None else price, True)
    promo = dinheiro(promo, True)
    if promo >= base:
        return price
    return max(CENT, (price * promo / base).quantize(CENT, rounding=ROUND_HALF_UP))


def save_metadata(m, cur, product, salon, data, price):
    keys = ('id_fornecedor','custo_compra','promocao_preco','promocao_inicio','promocao_fim','lancamento_ate')
    if not any(k in data for k in keys):
        # Existing promotions must remain lower than an edited base price.
        current = metadata(cur, product)
        if current['promocao_preco'] is not None and dinheiro(current['promocao_preco']) >= price:
            raise ValueError('O preço promocional deve ser menor que o preço de venda.')
        return
    result = metadata(cur, product)
    existing_supplier = result['id_fornecedor']
    result.update({k:data[k] for k in keys if k in data})
    supplier = result['id_fornecedor']
    if supplier in (None, ''):
        supplier = None
    else:
        supplier = inteiro(supplier, 'Fornecedor')
        cur.execute('SELECT ATIVO FROM MP_FORNECEDOR WHERE ID_FORNECEDOR=? AND ID_BARBEARIA=?', (supplier,salon))
        supplier_row = cur.fetchone()
        # Deactivation prevents new associations while preserving product history.
        if not supplier_row or (not supplier_row[0] and supplier != existing_supplier):
            raise ValueError('Fornecedor não encontrado ou inativo nesta barbearia.')
    purchase = cost(result['custo_compra'])
    promo = dinheiro(result['promocao_preco'],True) if result['promocao_preco'] not in (None,'') else None
    def parse(v):
        return v if isinstance(v,date) else day(v,True)
    start, end, launch = (parse(result[k]) for k in ('promocao_inicio','promocao_fim','lancamento_ate'))
    if promo is not None and (not start or not end or end < start or promo >= price):
        raise ValueError('Promoção exige período válido e preço inferior ao preço de venda.')
    if promo is None:
        start = end = None
    cur.execute('UPDATE OR INSERT INTO MP_COMERCIAL(ID_PRODUTO,'+META_COLS+') VALUES(?,?,?,?,?,?,?) MATCHING(ID_PRODUTO)', (product,supplier,purchase,promo,start,end,launch))


def variants(cur, product):
    cur.execute('SELECT '+VAR_COLS+' FROM MP_VARIACAO WHERE ID_PRODUTO=? ORDER BY ID_VARIACAO', (product,))
    return [dict(zip(('id_variacao','id_produto','nome','sku','tamanho','cor','volume','preco','custo_compra','estoque','ativo'),r)) for r in cur.fetchall()]


def variant_json(v, meta, base, owner=False):
    result = {k:v[k] for k in ('id_variacao','id_produto','nome','sku','tamanho','cor','volume','estoque')}
    result.update(ativo=bool(v['ativo']),preco_original=float(v['preco']),preco=float(effective_price(v['preco'],meta,base)))
    result['em_promocao'] = result['preco'] < result['preco_original']
    if owner:
        result.update(custo_compra=float(v['custo_compra']) if v['custo_compra'] is not None else None,
                      margem_lucro_percentual=margin(result['preco'],v['custo_compra']))
    return result


def enrich_product(cur, product, owner=False):
    meta = metadata(cur,product['id_produto'])
    base = product['preco']
    price = effective_price(base,meta)
    all_variants = variants(cur,product['id_produto'])
    product.update(preco_original=base,preco=float(price),em_promocao=price<dinheiro(base),
                   lancamento=bool(meta['lancamento_ate'] and date.today()<=meta['lancamento_ate']),
                   tem_variacoes=bool(all_variants),
                   variacoes=[variant_json(v,meta,base,owner) for v in all_variants if owner or v['ativo']])
    if all_variants:
        active = [v for v in all_variants if v['ativo']]
        product['estoque'] = sum(v['estoque'] for v in active)
        if active:
            cheapest = min(active,key=lambda v:effective_price(v['preco'],meta,base))
            product.update(preco=float(effective_price(cheapest['preco'],meta,base)),preco_original=float(cheapest['preco']))
            product['em_promocao'] = product['preco'] < product['preco_original']
    if owner:
        for k,v in meta.items():
            product[k] = v.isoformat() if isinstance(v,date) else float(v) if isinstance(v,Decimal) else v
        product['preco_cadastro'] = base
        product['margem_lucro_percentual'] = margin(effective_price(base,meta),meta['custo_compra'])
        product['fornecedor'] = None
        if meta['id_fornecedor']:
            cur.execute('SELECT NOME FROM MP_FORNECEDOR WHERE ID_FORNECEDOR=?', (meta['id_fornecedor'],))
            row = cur.fetchone()
            product['fornecedor'] = row[0] if row else None
    return product


def coupon_code(value):
    code = texto(value,40,'Cupom').upper()
    if code and not re.fullmatch(r'[A-Z0-9_-]{2,40}',code):
        raise ValueError('Código do cupom deve conter 2 a 40 letras, números, hífen ou sublinhado.')
    return code


def discount(total, kind, value):
    total = dinheiro(total,True)
    value = dinheiro(value,True)
    if kind not in ('fixo','percentual') or (kind=='percentual' and value>100):
        raise ValueError('Desconto inválido.')
    result = value if kind=='fixo' else (total*value/100).quantize(CENT,rounding=ROUND_HALF_UP)
    return min(result,max(Decimal('0.00'),total-CENT))


def apply_coupon(cur, salon, code, subtotal):
    code = coupon_code(code)
    if not code:
        return None,Decimal('0.00'),''
    cur.execute('SELECT ID_CUPOM,TIPO,VALOR,INICIO,FIM,LIMITE_USOS,ATIVO FROM MP_CUPOM WHERE ID_BARBEARIA=? AND CODIGO=?', (salon,code))
    row = cur.fetchone()
    today = date.today()
    if not row or not row[6] or not row[3]<=today<=row[4]:
        raise ValueError('Cupom inválido, inativo ou fora do período de validade.')
    cur.execute('SELECT COUNT(*) FROM MP_CUPOM_USO WHERE ID_CUPOM=? AND ATIVO=1',(row[0],))
    if cur.fetchone()[0]>=row[5]:
        raise Conflito('O limite de utilizações deste cupom foi atingido.')
    return row[0],discount(subtotal,row[1],row[2]),code


def csv_cell(value):
    value = str(value if value is not None else '')
    return "'"+value if value.startswith(('\t','\r','\n')) or value.lstrip().startswith(('=','+','-','@')) else value


def allocate_discount(totals, rebate):
    """Distribute exact cents by largest remainder, bounded by each line total."""
    gross=sum(totals,Decimal(0))
    if not gross or not rebate:return [Decimal(0)]*len(totals)
    precise=[rebate*total/gross for total in totals]
    allocated=[value.quantize(CENT,rounding=ROUND_DOWN) for value in precise]
    missing=int((rebate-sum(allocated,Decimal(0)))/CENT)
    ranking=sorted(range(len(totals)),key=lambda i:precise[i]-allocated[i],reverse=True)
    for index in ranking[:missing]:allocated[index]+=CENT
    return allocated


def sales_report(m,cur,salon,start,end,group):
    if group not in ('dia','mes'):
        raise ValueError('Agrupamento inválido.')
    cur.execute('SELECT ID_PEDIDO,STATUS,PAGAMENTO_STATUS,SUBTOTAL,FRETE,TOTAL,ITENS,CRIADO_EM FROM MP_PEDIDO WHERE ID_BARBEARIA=? AND CRIADO_EM>=? AND CRIADO_EM<? ORDER BY ID_PEDIDO',(salon,start,end+timedelta(days=1)))
    rows = cur.fetchall()
    indicators = dict(faturamento=Decimal(0),quantidade_pedidos=len(rows),quantidade_pagos=0,ticket_medio=0,frete=Decimal(0),descontos=Decimal(0),custo_produtos=Decimal(0),lucro_bruto=Decimal(0),custos_incompletos=False)
    products, periods = {},{}
    for row in rows:
        if row[2]!='pago' or row[1]=='cancelado':
            continue
        indicators['quantidade_pagos'] += 1
        indicators['faturamento'] += row[3]
        indicators['frete'] += row[4]
        cur.execute('SELECT DESCONTO,CUSTOS FROM MP_PEDIDO_COMERCIAL WHERE ID_PEDIDO=?',(row[0],))
        commercial = cur.fetchone()
        rebate = commercial[0] if commercial else Decimal(0)
        costs = m.loads(commercial[1],[]) if commercial else []
        indicators['descontos'] += rebate
        period = row[7].strftime('%Y-%m' if group=='mes' else '%Y-%m-%d')
        p = periods.setdefault(period,dict(periodo=period,faturamento=Decimal(0),quantidade_pagos=0,ticket_medio=0,frete=Decimal(0),descontos=Decimal(0)))
        p['faturamento']+=row[3];p['quantidade_pagos']+=1;p['frete']+=row[4];p['descontos']+=rebate
        items=m.loads(row[6],[])
        portions=allocate_discount([dinheiro(i['total']) for i in items],rebate)
        for index,item in enumerate(items):
            amount=dinheiro(item['total'])
            portion=portions[index]
            entry=products.setdefault(item['id_produto'],dict(id_produto=item['id_produto'],nome=item['nome'],quantidade=0,faturamento=Decimal(0),custo_produtos=Decimal(0),lucro_bruto=Decimal(0),custos_incompletos=False))
            entry['quantidade']+=item['quantidade'];entry['faturamento']+=amount-portion
            snapshot=costs[index] if index<len(costs) else None
            if snapshot is None:
                entry['custos_incompletos']=indicators['custos_incompletos']=True
            else:
                purchase=dinheiro(snapshot)*item['quantidade'];entry['custo_produtos']+=purchase;indicators['custo_produtos']+=purchase
    for p in periods.values():
        p['ticket_medio']=(p['faturamento']/p['quantidade_pagos']).quantize(CENT,rounding=ROUND_HALF_UP)
    for p in products.values():
        p['lucro_bruto']=None if p['custos_incompletos'] else p['faturamento']-p['custo_produtos']
    indicators['ticket_medio']=(indicators['faturamento']/indicators['quantidade_pagos']).quantize(CENT,rounding=ROUND_HALF_UP) if indicators['quantidade_pagos'] else Decimal(0)
    indicators['lucro_bruto']=None if indicators['custos_incompletos'] else indicators['faturamento']-indicators['custo_produtos']
    def numbers(obj):
        return {k:float(v) if isinstance(v,Decimal) else v for k,v in obj.items()}
    return dict(indicadores=numbers(indicators),produtos=[numbers(p) for p in products.values()],periodos=[numbers(periods[k]) for k in sorted(periods)],inicio=start.isoformat(),fim=end.isoformat(),agrupamento=group,aviso='Receitas de mercadorias pagas, após cupons. Frete separado. Lucro bruto não inclui taxas ou outras despesas; pedidos sem custo registrado não têm lucro estimado.')


def register(m):
    """Register with explicit module dependency; avoids circular imports."""
    app=m.app

    @app.route('/gestao/marketplace/fornecedores',methods=['GET','POST'])
    @app.put('/gestao/marketplace/fornecedores/<int:id_fornecedor>')
    @app.patch('/gestao/marketplace/fornecedores/<int:id_fornecedor>/ativo')
    @m.protected('owner')
    def suppliers(user,salon,cur,con,id_fornecedor=None):
        columns='ID_FORNECEDOR,NOME,DOCUMENTO,EMAIL,TELEFONE,OBSERVACOES,ATIVO'
        def serialize(row):
            result=dict(zip(('id_fornecedor','nome','documento','email','telefone','observacoes','ativo'),row));result['ativo']=bool(result['ativo']);return result
        if request.method=='GET':
            cur.execute('SELECT '+columns+' FROM MP_FORNECEDOR WHERE ID_BARBEARIA=? ORDER BY NOME',(salon,));return jsonify(fornecedores=[serialize(r) for r in cur.fetchall()])
        data=m.body();m.lock_user(cur,salon)
        if id_fornecedor:
            cur.execute('SELECT '+columns+' FROM MP_FORNECEDOR WHERE ID_FORNECEDOR=? AND ID_BARBEARIA=?',(id_fornecedor,salon));row=cur.fetchone()
            if not row:return m.erro('Fornecedor não encontrado.',404)
        if request.method=='PATCH':
            cur.execute('UPDATE MP_FORNECEDOR SET ATIVO=? WHERE ID_FORNECEDOR=? AND ID_BARBEARIA=?',(int(m.boolean(data.get('ativo'))),id_fornecedor,salon))
        else:
            fields={k:texto(data.get(k),n,k,k!='nome') for k,n in (('nome',160),('documento',30),('email',200),('telefone',30),('observacoes',2000))}
            if fields['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',fields['email']):raise ValueError('E-mail do fornecedor inválido.')
            fields['ativo']=int(m.boolean(data.get('ativo',True)))
            if id_fornecedor:
                cur.execute('UPDATE MP_FORNECEDOR SET '+','.join(k+'=?' for k in fields)+' WHERE ID_FORNECEDOR=? AND ID_BARBEARIA=?',[*fields.values(),id_fornecedor,salon])
            else:
                id_fornecedor=m.next_id(cur,'SEQ_MP_FORNECEDOR');cur.execute('INSERT INTO MP_FORNECEDOR(ID_FORNECEDOR,ID_BARBEARIA,'+','.join(fields)+') VALUES('+','.join('?' for _ in range(len(fields)+2))+')',[id_fornecedor,salon,*fields.values()])
        con.commit();cur.execute('SELECT '+columns+' FROM MP_FORNECEDOR WHERE ID_FORNECEDOR=?',(id_fornecedor,));return jsonify(fornecedor=serialize(cur.fetchone())),201 if request.method=='POST' else 200

    @app.route('/gestao/marketplace/cupons',methods=['GET','POST'])
    @app.put('/gestao/marketplace/cupons/<int:id_cupom>')
    @app.patch('/gestao/marketplace/cupons/<int:id_cupom>/ativo')
    @m.protected('owner')
    def coupons(user,salon,cur,con,id_cupom=None):
        cols='ID_CUPOM,CODIGO,TIPO,VALOR,INICIO,FIM,LIMITE_USOS,ATIVO'
        def serialize(r):
            item=dict(zip(('id_cupom','codigo','tipo','valor','inicio','fim','limite_usos','ativo'),r));item.update(valor=float(r[3]),inicio=r[4].isoformat(),fim=r[5].isoformat(),ativo=bool(r[7]))
            cur.execute('SELECT COUNT(*) FROM MP_CUPOM_USO WHERE ID_CUPOM=? AND ATIVO=1',(r[0],));item['usos']=cur.fetchone()[0];return item
        if request.method=='GET':
            cur.execute('SELECT '+cols+' FROM MP_CUPOM WHERE ID_BARBEARIA=? ORDER BY ID_CUPOM DESC',(salon,));return jsonify(cupons=[serialize(r) for r in cur.fetchall()])
        data=m.body();m.lock_user(cur,salon)
        if id_cupom:
            cur.execute('SELECT ID_CUPOM FROM MP_CUPOM WHERE ID_CUPOM=? AND ID_BARBEARIA=?',(id_cupom,salon))
            if not cur.fetchone():return m.erro('Cupom não encontrado.',404)
        if request.method=='PATCH':
            cur.execute('UPDATE MP_CUPOM SET ATIVO=? WHERE ID_CUPOM=?',(int(m.boolean(data.get('ativo'))),id_cupom))
        else:
            code=coupon_code(data.get('codigo'))
            if not code:raise ValueError('Informe o código do cupom.')
            kind=data.get('tipo');value=dinheiro(data.get('valor'),True);discount(Decimal(100),kind,value)
            start,end=day(data.get('inicio')),day(data.get('fim'))
            if end<start:raise ValueError('Fim da validade deve ser igual ou posterior ao início.')
            limit=m.qty(data.get('limite_usos'));active=int(m.boolean(data.get('ativo',True)))
            cur.execute('SELECT ID_CUPOM FROM MP_CUPOM WHERE ID_BARBEARIA=? AND CODIGO=?',(salon,code));duplicate=cur.fetchone()
            if duplicate and duplicate[0]!=id_cupom:raise Conflito('Já existe um cupom com este código nesta loja.')
            values=(code,kind,value,start,end,limit,active)
            if id_cupom:
                cur.execute('UPDATE MP_CUPOM SET CODIGO=?,TIPO=?,VALOR=?,INICIO=?,FIM=?,LIMITE_USOS=?,ATIVO=? WHERE ID_CUPOM=?',(*values,id_cupom))
            else:
                id_cupom=m.next_id(cur,'SEQ_MP_CUPOM');cur.execute('INSERT INTO MP_CUPOM(ID_CUPOM,ID_BARBEARIA,'+cols.split(',',1)[1]+') VALUES(?,?,?,?,?,?,?,?,?)',(id_cupom,salon,*values))
        con.commit();cur.execute('SELECT '+cols+' FROM MP_CUPOM WHERE ID_CUPOM=?',(id_cupom,));return jsonify(cupom=serialize(cur.fetchone())),201 if request.method=='POST' else 200

    @app.route('/gestao/marketplace/produtos/<int:id_produto>/variacoes',methods=['GET','POST'])
    @app.put('/gestao/marketplace/produtos/<int:id_produto>/variacoes/<int:id_variacao>')
    @app.patch('/gestao/marketplace/produtos/<int:id_produto>/variacoes/<int:id_variacao>/ativo')
    @m.protected('owner')
    def product_variants(user,salon,cur,con,id_produto,id_variacao=None):
        if request.method!='GET':m.lock_user(cur,salon)
        product=m.get_product(cur,id_produto,salon)
        if not product:return m.erro('Produto não encontrado.',404)
        meta=metadata(cur,id_produto)
        all_=variants(cur,id_produto)
        if request.method=='GET':return jsonify(variacoes=[variant_json(v,meta,product[8],True) for v in all_])
        data=m.body()
        if id_variacao and not any(v['id_variacao']==id_variacao for v in all_):return m.erro('Variação não encontrada.',404)
        if request.method=='PATCH':
            cur.execute('UPDATE MP_VARIACAO SET ATIVO=? WHERE ID_VARIACAO=?',(int(m.boolean(data.get('ativo'))),id_variacao))
        else:
            fields={k:texto(data.get(k),n,k,k!='nome') for k,n in (('nome',160),('sku',100),('tamanho',80),('cor',80),('volume',80))}
            fields.update(preco=dinheiro(data.get('preco'),True),custo_compra=cost(data.get('custo_compra')),ativo=int(m.boolean(data.get('ativo',True))))
            if fields['sku']:
                cur.execute('SELECT V.ID_VARIACAO FROM MP_VARIACAO V JOIN MP_PRODUTO P ON P.ID_PRODUTO=V.ID_PRODUTO WHERE P.ID_BARBEARIA=? AND UPPER(V.SKU)=UPPER(?)',(salon,fields['sku']))
                if any(r[0]!=id_variacao for r in cur.fetchall()):raise Conflito('SKU já cadastrado nesta loja.')
            if id_variacao:
                cur.execute('UPDATE MP_VARIACAO SET '+','.join(k+'=?' for k in fields)+' WHERE ID_VARIACAO=?',[*fields.values(),id_variacao])
            else:
                amount=m.qty(data.get('estoque',0),True)
                id_variacao=m.next_id(cur,'SEQ_MP_VARIACAO');fields['estoque']=amount
                cur.execute('INSERT INTO MP_VARIACAO(ID_VARIACAO,ID_PRODUTO,'+','.join(fields)+') VALUES('+','.join('?' for _ in range(len(fields)+2))+')',[id_variacao,id_produto,*fields.values()])
                if amount:m.stock_move(cur,id_produto,user['id_usuario'],amount,'entrada','Estoque inicial da variação',variation=id_variacao)
        con.commit();v=next(v for v in variants(cur,id_produto) if v['id_variacao']==id_variacao)
        return jsonify(variacao=variant_json(v,meta,product[8],True)),201 if request.method=='POST' else 200

    @app.route('/gestao/marketplace/produtos/<int:id_produto>/variacoes/<int:id_variacao>/estoque',methods=['GET','POST'])
    @m.protected('owner')
    def variant_stock(user,salon,cur,con,id_produto,id_variacao):
        if request.method=='POST':m.lock_user(cur,salon)
        product=m.get_product(cur,id_produto,salon)
        if not product:return m.erro('Produto não encontrado.',404)
        v=next((v for v in variants(cur,id_produto) if v['id_variacao']==id_variacao),None)
        if not v:return m.erro('Variação não encontrada.',404)
        if request.method=='GET':
            cur.execute('SELECT ID_MOVIMENTO,QUANTIDADE,TIPO,OBSERVACAO,CRIADO_EM FROM MP_ESTOQUE WHERE ID_PRODUTO=? AND ID_VARIACAO=? ORDER BY ID_MOVIMENTO DESC',(id_produto,id_variacao));return jsonify(movimentacoes=[dict(id_movimento=r[0],quantidade=r[1],tipo=r[2],observacao=r[3],criado_em=r[4].isoformat()) for r in cur.fetchall()])
        data=m.body();amount=m.qty(data.get('quantidade'));operation=m.key(data.get('chave_idempotencia'));obs=texto(data.get('observacao'),500,'Observação')
        hash_=m.fingerprint(dict(id_variacao=id_variacao,quantidade=amount,observacao=obs))
        cur.execute('SELECT HASH_PEDIDO FROM MP_ESTOQUE WHERE ID_PRODUTO=? AND CHAVE=?',(id_produto,operation));prior=cur.fetchone()
        if prior and prior[0]!=hash_:raise Conflito('Esta chave já foi usada com outros dados.')
        if not prior:
            if v['estoque']+amount>999999:raise ValueError('Limite de estoque excedido.')
            cur.execute('UPDATE MP_VARIACAO SET ESTOQUE=ESTOQUE+? WHERE ID_VARIACAO=?',(amount,id_variacao));m.stock_move(cur,id_produto,user['id_usuario'],amount,'entrada',obs,operation,hash_,id_variacao);con.commit()
        v=next(v for v in variants(cur,id_produto) if v['id_variacao']==id_variacao)
        return jsonify(variacao=variant_json(v,metadata(cur,id_produto),product[8],True))

    @app.get('/marketplace/lista-desejos')
    @m.protected()
    def wishes(user,salon,cur,con):
        cur.execute('SELECT '+m.P_COLS+' FROM MP_DESEJO D JOIN MP_PRODUTO P ON P.ID_PRODUTO=D.ID_PRODUTO JOIN USUARIO U ON U.ID_USUARIO=P.ID_BARBEARIA WHERE D.ID_USUARIO=? AND P.ATIVO=1 AND U.TIPO=2 AND U.ATIVO=1 AND U.EMAIL_CONFIRMADO=1 ORDER BY P.NOME',(user['id_usuario'],))
        return jsonify(produtos=[m.serialize_product(cur,r) for r in cur.fetchall()])

    @app.put('/marketplace/lista-desejos/<int:id_produto>')
    @m.protected()
    def wish(user,salon,cur,con,id_produto):
        desired=m.boolean(m.body().get('desejado'));m.lock_user(cur,user['id_usuario'])
        if desired and not m.get_product(cur,id_produto,active=True):return m.erro('Produto não encontrado.',404)
        cur.execute('DELETE FROM MP_DESEJO WHERE ID_USUARIO=? AND ID_PRODUTO=?',(user['id_usuario'],id_produto))
        if desired:cur.execute('INSERT INTO MP_DESEJO(ID_USUARIO,ID_PRODUTO) VALUES(?,?)',(user['id_usuario'],id_produto))
        con.commit();return jsonify(desejado=desired)

    @app.get('/gestao/marketplace/relatorios')
    @app.get('/gestao/marketplace/relatorios.csv')
    @m.protected('owner')
    def report(user,salon,cur,con):
        today=date.today();start=day(request.args.get('inicio',today.replace(day=1).isoformat()));end=day(request.args.get('fim',today.isoformat()))
        if end==date.max or end<start or (end-start).days>3660:raise ValueError('Informe um período válido de até dez anos.')
        data=sales_report(m,cur,salon,start,end,request.args.get('agrupamento','dia'))
        if not request.path.endswith('.csv'):return jsonify(data)
        stream=io.StringIO(newline='');writer=csv.writer(stream,delimiter=';');writer.writerow(['Produto','Quantidade','Receita de mercadorias','Custo registrado','Lucro bruto','Custos incompletos'])
        for p in data['produtos']:writer.writerow([csv_cell(p[k]) for k in ('nome','quantidade','faturamento','custo_produtos','lucro_bruto','custos_incompletos')])
        return Response('\ufeff'+stream.getvalue(),mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="vendas-marketplace.csv"','Cache-Control':'no-store'})
