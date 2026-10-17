"""Salon marketplace with isolated ownership, stock reservations and durable provider attempts."""
import hashlib
import ipaddress
import json
import re
import uuid
from datetime import datetime,timedelta
from decimal import Decimal
from functools import wraps
from urllib.parse import urlsplit,quote
from flask import jsonify,request
from image_storage import ImageBatch, ImageStorageError, compress_image, find_image, serve_image
from application import app,conectar_banco
from database import travar_usuario
from barbearia import obter_usuario_logado
from gestao import inteiro,dinheiro,texto,Conflito,erro
import melhor_envio
import marketplace_comercial as comercial
from auditoria import registrar_log
from termos import exigir_aceite
from taxa_plataforma import calcular,resumo_confirmavel,confirmar_resumo,registrar_taxa,exigir_aceites

P_COLS='P.ID_PRODUTO,P.ID_BARBEARIA,U.NOME,P.NOME,P.DESCRICAO,P.DETALHES,P.CATEGORIA,P.MARCA,P.PRECO,P.ESTOQUE,P.ESTOQUE_MINIMO,P.ATIVO,P.IMAGENS,P.PESO,P.LARGURA,P.ALTURA,P.COMPRIMENTO'
O_COLS='P.ID_PEDIDO,P.ID_USUARIO,P.ID_BARBEARIA,P.STATUS,P.SUBTOTAL,P.FRETE,P.TOTAL,P.RETIRADA,P.ENDERECO,P.ITENS,P.COTACAO,P.PAGAMENTO_STATUS,P.PAGAMENTO_ID,P.PAGAMENTO_DADOS,P.ENTREGA_STATUS,P.ENTREGA_ID,P.ENTREGA_DADOS,P.CRIADO_EM,U.NOME,B.NOME'
O_COLS += ''.join(", (SELECT T."+column+" FROM PLATAFORMA_TAXA T WHERE T.TIPO='pedido' AND T.ID_OPERACAO=P.ID_PEDIDO)" for column in
    ('VALOR_BASE','FRETE','PERCENTUAL','VALOR_TAXA','PAGADOR','TOTAL_CLIENTE','LIQUIDO_BARBEARIA','TERMOS_VERSAO'))
O_COLS += ''.join(', (SELECT C.'+column+' FROM MP_PEDIDO_COMERCIAL C WHERE C.ID_PEDIDO=P.ID_PEDIDO)' for column in ('SUBTOTAL_ORIGINAL','DESCONTO','CODIGO_CUPOM'))

def dumps(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def loads(value,default=None):return json.loads(str(value)) if value else default
def fingerprint(value):return hashlib.sha256(dumps(value).encode()).hexdigest()
def body():
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise ValueError('Informe um objeto JSON válido.')
    return data

def qty(value,zero=False):
    if isinstance(value,bool) or not isinstance(value,int) or not (0 if zero else 1)<=value<=999999:raise ValueError('Quantidade inteira inválida.')
    return value

def boolean(value):
    if not isinstance(value,bool):raise ValueError('Informe verdadeiro ou falso.')
    return value

def key(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,64}',value):raise ValueError('Chave de idempotência inválida.')
    return value

def image_url(value,cursor=None,salon=None):
    value=texto(value,2000,'URL da imagem',False)
    managed=re.fullmatch(r'/uploads/marketplace/([a-f0-9]{32}\.webp)',value)
    if managed:
        if cursor is None or salon is None:raise ValueError('Imagem da loja inválida.')
        asset=find_image('marketplace',managed.group(1),cursor=cursor)
        if not asset or asset.owner_id!=salon or not asset.active:raise ValueError('Imagem não pertence a esta loja.')
        return value
    url=urlsplit(value)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.hostname.lower() in ('localhost','localhost.localdomain'):
        raise ValueError('Imagens devem usar URLs públicas HTTPS.')
    try:
        address=ipaddress.ip_address(url.hostname)
        if not address.is_global:raise ValueError('Imagem deve usar endereço público.')
    except ValueError as exc:
        if 'Imagem deve' in str(exc):raise
    return value

def address(data):
    if not isinstance(data,dict):raise ValueError('Endereço inválido.')
    result={k:texto(data.get(k),n,k,k in ('complemento','inscricao_estadual')) for k,n in
        (('nome',160),('email',200),('telefone',30),('documento',18),('cep',10),('logradouro',160),('numero',30),('complemento',100),('bairro',100),('cidade',100),('uf',2),('inscricao_estadual',30))}
    result['cep']=re.sub(r'\D','',result['cep']);result['documento']=re.sub(r'\D','',result['documento']);result['telefone']=re.sub(r'\D','',result['telefone']);result['uf']=result['uf'].upper()
    if not re.fullmatch(r'\d{8}',result['cep']) or len(result['documento']) not in (11,14) or len(result['telefone']) not in (10,11) or not re.fullmatch(r'[A-Z]{2}',result['uf']) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',result['email']):raise ValueError('CEP, documento, telefone, UF ou e-mail inválido.')
    return result

def product_data(data,creation=False,cursor=None,salon=None):
    result={k:texto(data.get(k),n,k,k not in ('nome','descricao')) for k,n in (('nome',160),('descricao',10000),('detalhes',15000),('categoria',100),('marca',100))}
    result['preco']=dinheiro(data.get('preco'),True)
    for k in ('peso','largura','altura','comprimento'):
        try:v=Decimal(str(data.get(k)))
        except Exception:raise ValueError('Peso e dimensões são obrigatórios e positivos.') from None
        if isinstance(data.get(k),bool) or not v.is_finite() or not 0<v<=1000:raise ValueError('Peso e dimensões inválidos.')
        result[k]=v.quantize(Decimal('0.001') if k=='peso' else Decimal('0.01'))
        if result[k]<=0:raise ValueError('Peso e dimensões devem ser maiores que zero.')
    images=data.get('imagens',[])
    if not isinstance(images,list) or len(images)>8:raise ValueError('Informe até oito URLs de imagem.')
    result['imagens']=dumps([image_url(v,cursor,salon) for v in images]);result['estoque_minimo']=qty(data.get('estoque_minimo',0),True)
    if creation:result['estoque']=qty(data.get('estoque',0),True)
    if creation or 'ativo' in data:result['ativo']=int(boolean(data.get('ativo',True)))
    return result

def product_body():
    """JSON remains supported; file bytes travel only with their product save."""
    if request.mimetype!='multipart/form-data':return body(),[]
    try:data=json.loads(request.form.get('dados',''))
    except (TypeError,ValueError):raise ValueError('Informe os dados do produto em JSON válido.') from None
    if not isinstance(data,dict):raise ValueError('Informe um objeto JSON válido.')
    if set(request.files)-{'imagens'}:raise ValueError('Campo de imagem inválido.')
    files=request.files.getlist('imagens')
    images=data.get('imagens',[])
    if not isinstance(images,list) or len(files)+len(images)>8:raise ValueError('Cada produto pode ter até oito fotos.')
    # Check every image before creating any provider object. save() reuses the
    # original bytes after rewind, so this does not introduce lossy re-encoding.
    for file in files:
        compress_image(file)
        file.stream.seek(0)
    return data,files


def product_photos(data,files,batch,salon):
    images=loads(data['imagens'],[])
    for file in files:images.append(batch.save(file,'marketplace',owner_id=salon).url)
    data['imagens']=dumps(images)


@app.get('/uploads/marketplace/<path:filename>')
def marketplace_image(filename):
    if not re.fullmatch(r'[a-f0-9]{32}\.webp',filename):return erro('Imagem não encontrada.',404)
    return serve_image('marketplace',filename)


def protected(mode='client'):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            token=obter_usuario_logado()
            if not token:return erro('Faça login.',401)
            con=conectar_banco();cur=con.cursor()
            try:
                for name,value in kwargs.items():
                    if name.startswith('id_'):inteiro(value,name)
                cur.execute('SELECT ID_USUARIO,TIPO FROM USUARIO WHERE ID_USUARIO=? AND ATIVO=1 AND EMAIL_CONFIRMADO=1',(token['id_usuario'],));row=cur.fetchone()
                if not row:return erro('Faça login.',401)
                user={'id_usuario':row[0],'tipo':row[1]};salon=None
                if row[1] not in ((0,2) if mode=='owner' else (1,)):return erro('Sem permissão para esta operação.',403)
                if mode=='owner':
                    requested=request.args.get('id_barbearia');salon=inteiro(requested,'Barbearia') if row[1]==0 else row[0]
                    if requested and inteiro(requested)!=salon:return erro('Sem permissão para outra barbearia.',403)
                    cur.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? AND TIPO=2 AND ATIVO=1 AND EMAIL_CONFIRMADO=1',(salon,))
                    if not cur.fetchone():return erro('Barbearia não encontrada.',404)
                result=fn(user,salon,cur,con,*args,**kwargs)
                response=result[0] if isinstance(result,tuple) else result
                status=result[1] if isinstance(result,tuple) else response.status_code
                if request.method in ('POST','PUT','PATCH','DELETE') and 200<=status<300 and fn.__name__!='bind_shipping':
                    registrar_log('MARKETPLACE','MP_OPERACAO',id_registro=kwargs.get('id_produto') or kwargs.get('id_pedido') or user['id_usuario'],
                        id_usuario=user['id_usuario'],campo='ROTA',valor_depois=request.method+' '+request.path)
                return result
            except Conflito as exc:con.rollback();return erro(str(exc),409)
            except (ValueError,TypeError) as exc:con.rollback();return erro(str(exc),getattr(exc,'status',400))
            except ImageStorageError as exc:con.rollback();return erro(str(exc),exc.status)
            except melhor_envio.EntregaErro as exc:con.rollback();return erro(str(exc),exc.status)
            except Exception:con.rollback();raise
            finally:cur.close();con.close()
        return wrapped
    return decorate

def lock_user(cur,id_):travar_usuario(cur, id_)
def next_id(cur,seq):cur.execute('SELECT NEXT VALUE FOR '+seq+' FROM RDB$DATABASE');return cur.fetchone()[0]
def stock_move(cur,product,user,quantity,kind,observation='',operation=None,hash_=None,variation=None):
    cur.execute('INSERT INTO MP_ESTOQUE(ID_MOVIMENTO,ID_PRODUTO,ID_USUARIO,QUANTIDADE,TIPO,OBSERVACAO,CHAVE,HASH_PEDIDO,ID_VARIACAO) VALUES(?,?,?,?,?,?,?,?,?)',
        (next_id(cur,'SEQ_MP_ESTOQUE'),product,user,quantity,kind,observation,operation or uuid.uuid4().hex,hash_,variation))

def serialize_product(cur,row,owner=False):
    names=('id_produto','id_barbearia','barbearia','nome','descricao','detalhes','categoria','marca','preco','estoque','estoque_minimo','ativo','imagens','peso','largura','altura','comprimento')
    product=dict(zip(names,row));product['ativo']=bool(row[11]);product['imagens']=loads(row[12],[])
    for k in ('descricao','detalhes'):product[k]=str(product[k] or '')
    for k in ('preco','peso','largura','altura','comprimento'):product[k]=float(product[k])
    cur.execute('SELECT AVG(CAST(NOTA AS DECIMAL(8,2))),COUNT(*) FROM MP_AVALIACAO WHERE ID_PRODUTO=?',(row[0],));rating=cur.fetchone()
    product.update(media_avaliacoes=round(float(rating[0] or 0),2),total_avaliacoes=rating[1]);return comercial.enrich_product(cur,product,owner)

def get_product(cur,id_,salon=None,active=False):
    cur.execute('SELECT '+P_COLS+' FROM MP_PRODUTO P JOIN USUARIO U ON U.ID_USUARIO=P.ID_BARBEARIA WHERE P.ID_PRODUTO=?'+(' AND P.ID_BARBEARIA=?' if salon else '')+(' AND P.ATIVO=1 AND U.TIPO=2 AND U.ATIVO=1 AND U.EMAIL_CONFIRMADO=1' if active else ''),(id_,salon) if salon else (id_,))
    return cur.fetchone()

def public_query(cur,salon_id=None):
    conditions=['P.ATIVO=1','U.TIPO=2','U.ATIVO=1','U.EMAIL_CONFIRMADO=1'];params=[]
    if salon_id is not None:conditions.append('P.ID_BARBEARIA=?');params.append(salon_id)
    elif request.args.get('id_barbearia'):conditions.append('P.ID_BARBEARIA=?');params.append(inteiro(request.args['id_barbearia']))
    if request.args.get('categoria'):conditions.append('P.CATEGORIA=?');params.append(texto(request.args['categoria'],100,'Categoria'))
    if request.args.get('busca'):conditions.append('(UPPER(P.NOME) CONTAINING UPPER(?) OR UPPER(P.MARCA) CONTAINING UPPER(?))');search=texto(request.args['busca'],150,'Busca');params.extend((search,search))
    order={'nome':'P.NOME','preco_asc':'P.PRECO,P.ID_PRODUTO','preco_desc':'P.PRECO DESC,P.ID_PRODUTO','recentes':'P.ID_PRODUTO DESC'}.get(request.args.get('ordem','recentes'))
    if not order:raise ValueError('Ordenação inválida.')
    cur.execute('SELECT FIRST 500 '+P_COLS+' FROM MP_PRODUTO P JOIN USUARIO U ON U.ID_USUARIO=P.ID_BARBEARIA WHERE '+' AND '.join(conditions)+' ORDER BY '+order,params)
    return cur.fetchall()

def public_products(cur,rows):
    products=[serialize_product(cur,r) for r in rows]
    highlight=request.args.get('destaque','')
    if highlight not in ('','promocoes','lancamentos'):raise ValueError('Destaque inválido.')
    if highlight:products=[p for p in products if p['em_promocao' if highlight=='promocoes' else 'lancamento']]
    order=request.args.get('ordem','recentes')
    if order in ('preco_asc','preco_desc'):products.sort(key=lambda p:(p['preco'],p['id_produto']),reverse=order=='preco_desc')
    return products

@app.get('/marketplace/produtos')
def marketplace_products():
    con=conectar_banco();cur=con.cursor()
    try:
        rows=public_query(cur);products=public_products(cur,rows)
        cur.execute('SELECT DISTINCT U.ID_USUARIO,U.NOME FROM MP_PRODUTO P JOIN USUARIO U ON U.ID_USUARIO=P.ID_BARBEARIA WHERE P.ATIVO=1 AND U.TIPO=2 AND U.ATIVO=1 AND U.EMAIL_CONFIRMADO=1 ORDER BY U.NOME');salons=[{'id_barbearia':r[0],'nome':r[1]} for r in cur.fetchall()]
        cur.execute('SELECT DISTINCT CATEGORIA FROM MP_PRODUTO WHERE ATIVO=1 AND CATEGORIA IS NOT NULL ORDER BY CATEGORIA');cats=[r[0] for r in cur.fetchall() if r[0]]
        return jsonify(produtos=products,total=len(products),barbearias=salons,categorias=cats)
    except ValueError as exc:return erro(str(exc))
    finally:cur.close();con.close()

@app.get('/marketplace/barbearias/<int:id_barbearia>')
def marketplace_store(id_barbearia):
    """Loja pública de um estabelecimento ativo; filtros nunca alteram o salão da URL."""
    if not 0<id_barbearia<=2147483647:return erro('Loja não encontrada.',404)
    con=conectar_banco();cur=con.cursor()
    try:
        cur.execute('SELECT ID_USUARIO,NOME FROM USUARIO WHERE ID_USUARIO=? AND TIPO=2 AND ATIVO=1 AND EMAIL_CONFIRMADO=1',(id_barbearia,));salon=cur.fetchone()
        if not salon:return erro('Loja não encontrada.',404)
        products=public_products(cur,public_query(cur,salon_id=id_barbearia))
        cur.execute('SELECT DISTINCT CATEGORIA FROM MP_PRODUTO WHERE ID_BARBEARIA=? AND ATIVO=1 AND CATEGORIA IS NOT NULL ORDER BY CATEGORIA',(id_barbearia,));categories=[row[0] for row in cur.fetchall() if row[0]]
        return jsonify(barbearia=dict(id_barbearia=salon[0],nome=salon[1]),produtos=products,total=len(products),categorias=categories)
    except ValueError as exc:return erro(str(exc))
    finally:cur.close();con.close()


@app.get('/marketplace/barbearias/<int:id_barbearia>/perfil')
def marketplace_public_profile(id_barbearia):
    """Public storefront presentation; private account endpoints stay protected."""
    if not 0 < id_barbearia <= 2147483647:
        return erro('Loja não encontrada.', 404)
    from marketplace_perfil import public_profile
    con = conectar_banco(); cur = con.cursor()
    try:
        profile = public_profile(cur, id_barbearia, app.config['UPLOAD_FOLDER'])
        return jsonify(profile) if profile is not None else erro('Loja não encontrada.', 404)
    finally:
        cur.close(); con.close()


@app.get('/marketplace/produtos/<int:id_produto>')
def marketplace_product(id_produto):
    con=conectar_banco();cur=con.cursor()
    try:
        row=get_product(cur,id_produto,active=True)
        if not row:return erro('Produto não encontrado.',404)
        product=serialize_product(cur,row)
        product.update(favorito=False,desejado=False,pode_avaliar=False,minha_avaliacao=None)
        token=obter_usuario_logado()
        if token:
            cur.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? AND TIPO=1 AND ATIVO=1 AND EMAIL_CONFIRMADO=1',(token['id_usuario'],))
            if cur.fetchone():
                uid=token['id_usuario'];cur.execute('SELECT ID_PRODUTO FROM MP_FAVORITO WHERE ID_USUARIO=? AND ID_PRODUTO=?',(uid,id_produto));product['favorito']=bool(cur.fetchone())
                cur.execute('SELECT ID_PRODUTO FROM MP_DESEJO WHERE ID_USUARIO=? AND ID_PRODUTO=?',(uid,id_produto));product['desejado']=bool(cur.fetchone())
                cur.execute("SELECT ITENS FROM MP_PEDIDO WHERE ID_USUARIO=? AND STATUS='entregue'",(uid,));product['pode_avaliar']=any(any(i['id_produto']==id_produto for i in loads(r[0],[])) for r in cur.fetchall())
                cur.execute('SELECT NOTA,COMENTARIO FROM MP_AVALIACAO WHERE ID_USUARIO=? AND ID_PRODUTO=?',(uid,id_produto));mine=cur.fetchone();product['minha_avaliacao']={'nota':mine[0],'comentario':mine[1]} if mine else None
        cur.execute('SELECT A.NOTA,A.COMENTARIO,A.ATUALIZADO_EM,U.NOME FROM MP_AVALIACAO A JOIN USUARIO U ON U.ID_USUARIO=A.ID_USUARIO WHERE A.ID_PRODUTO=? ORDER BY A.ATUALIZADO_EM DESC',(id_produto,));reviews=[dict(nota=r[0],comentario=r[1],atualizado_em=r[2].isoformat(),cliente=r[3]) for r in cur.fetchall()]
        cur.execute('SELECT FIRST 4 '+P_COLS+' FROM MP_PRODUTO P JOIN USUARIO U ON U.ID_USUARIO=P.ID_BARBEARIA WHERE P.ID_BARBEARIA=? AND P.ATIVO=1 AND P.ID_PRODUTO<>? ORDER BY P.ID_PRODUTO DESC',(row[1],id_produto));related=[serialize_product(cur,r) for r in cur.fetchall()]
        return jsonify(produto=product,avaliacoes=reviews,relacionados=related)
    finally:cur.close();con.close()

@app.route('/gestao/marketplace/produtos',methods=['GET','POST'])
@protected('owner')
def owner_products(user,salon,cur,con):
    if request.method=='GET':
        cur.execute('SELECT '+P_COLS+' FROM MP_PRODUTO P JOIN USUARIO U ON U.ID_USUARIO=P.ID_BARBEARIA WHERE P.ID_BARBEARIA=? ORDER BY P.ID_PRODUTO DESC',(salon,));products=[serialize_product(cur,r,True) for r in cur.fetchall()]
        search=texto(request.args.get('busca'),150,'Busca').casefold()
        if search:products=[p for p in products if search in (' '.join(str(p[k] or '') for k in ('nome','descricao','categoria','marca'))).casefold()]
        return jsonify(produtos=products,total=len(products))
    raw,files=product_body();data=product_data(raw,True,cur,salon);lock_user(cur,salon)
    batch=ImageBatch(cur);persisted=False
    try:
        product_photos(data,files,batch,salon)
        id_=next_id(cur,'SEQ_MP_PRODUTO')
        columns=list(data);cur.execute('INSERT INTO MP_PRODUTO(ID_PRODUTO,ID_BARBEARIA,'+','.join(columns)+') VALUES('+','.join('?' for _ in range(len(columns)+2))+')',[id_,salon]+[data[k] for k in columns])
        if data['estoque']:stock_move(cur,id_,user['id_usuario'],data['estoque'],'entrada','Estoque inicial')
        comercial.save_metadata(None,cur,id_,salon,raw,data['preco'])
        con.commit();persisted=True;batch.commit()
        return jsonify(produto=serialize_product(cur,get_product(cur,id_,salon),True)),201
    finally:
        if not persisted:
            try:con.rollback()
            finally:batch.abort()


@app.put('/gestao/marketplace/produtos/<int:id_produto>')
@protected('owner')
def edit_product(user,salon,cur,con,id_produto):
    raw,files=product_body();data=product_data(raw,False,cur,salon);lock_user(cur,salon)
    if not get_product(cur,id_produto,salon):return erro('Produto não encontrado.',404)
    batch=ImageBatch(cur);persisted=False
    try:
        product_photos(data,files,batch,salon)
        cur.execute('UPDATE MP_PRODUTO SET '+','.join(k+'=?' for k in data)+',ATUALIZADO_EM=CURRENT_TIMESTAMP WHERE ID_PRODUTO=? AND ID_BARBEARIA=?',[data[k] for k in data]+[id_produto,salon])
        comercial.save_metadata(None,cur,id_produto,salon,raw,data['preco']);con.commit();persisted=True;batch.commit()
        return jsonify(produto=serialize_product(cur,get_product(cur,id_produto,salon),True))
    finally:
        if not persisted:
            try:con.rollback()
            finally:batch.abort()

@app.patch('/gestao/marketplace/produtos/<int:id_produto>/ativo')
@protected('owner')
def activate_product(user,salon,cur,con,id_produto):
    active=boolean(body().get('ativo'));lock_user(cur,salon)
    if not get_product(cur,id_produto,salon):return erro('Produto não encontrado.',404)
    cur.execute('UPDATE MP_PRODUTO SET ATIVO=?,ATUALIZADO_EM=CURRENT_TIMESTAMP WHERE ID_PRODUTO=? AND ID_BARBEARIA=?',(int(active),id_produto,salon));con.commit();return jsonify(produto=serialize_product(cur,get_product(cur,id_produto,salon),True))

@app.route('/gestao/marketplace/produtos/<int:id_produto>/estoque',methods=['GET','POST'])
@protected('owner')
def product_stock(user,salon,cur,con,id_produto):
    if request.method=='POST':lock_user(cur,salon)
    product=get_product(cur,id_produto,salon)
    if not product:return erro('Produto não encontrado.',404)
    if request.method=='GET':
        cur.execute('SELECT ID_MOVIMENTO,QUANTIDADE,TIPO,OBSERVACAO,CRIADO_EM FROM MP_ESTOQUE WHERE ID_PRODUTO=? ORDER BY ID_MOVIMENTO DESC',(id_produto,));return jsonify(movimentacoes=[dict(id_movimento=r[0],quantidade=r[1],tipo=r[2],observacao=r[3],criado_em=r[4].isoformat()) for r in cur.fetchall()])
    if comercial.variants(cur,id_produto):raise Conflito('Este produto possui variações. Faça a entrada de estoque na variação correspondente.')
    data=body();amount=qty(data.get('quantidade'));operation=key(data.get('chave_idempotencia'));obs=texto(data.get('observacao'),500,'Observação');hash_=fingerprint({'quantidade':amount,'observacao':obs})
    cur.execute('SELECT HASH_PEDIDO FROM MP_ESTOQUE WHERE ID_PRODUTO=? AND CHAVE=?',(id_produto,operation));prior=cur.fetchone()
    if prior:
        if prior[0]!=hash_:raise Conflito('Esta chave já foi usada com outros dados.')
    else:
        if product[9]+amount>999999:raise ValueError('Limite de estoque excedido.')
        cur.execute('UPDATE MP_PRODUTO SET ESTOQUE=ESTOQUE+? WHERE ID_PRODUTO=?',(amount,id_produto));stock_move(cur,id_produto,user['id_usuario'],amount,'entrada',obs,operation,hash_);con.commit()
    return jsonify(produto=serialize_product(cur,get_product(cur,id_produto,salon),True))

@app.get('/marketplace/favoritos')
@protected()
def favorites(user,salon,cur,con):
    cur.execute('SELECT '+P_COLS+' FROM MP_FAVORITO F JOIN MP_PRODUTO P ON P.ID_PRODUTO=F.ID_PRODUTO JOIN USUARIO U ON U.ID_USUARIO=P.ID_BARBEARIA WHERE F.ID_USUARIO=? AND P.ATIVO=1 AND U.TIPO=2 AND U.ATIVO=1 AND U.EMAIL_CONFIRMADO=1 ORDER BY P.NOME',(user['id_usuario'],));return jsonify(produtos=[serialize_product(cur,r) for r in cur.fetchall()])

@app.put('/marketplace/favoritos/<int:id_produto>')
@protected()
def favorite(user,salon,cur,con,id_produto):
    enabled=boolean(body().get('favorito'));lock_user(cur,user['id_usuario'])
    if enabled and not get_product(cur,id_produto,active=True):return erro('Produto não encontrado.',404)
    cur.execute('DELETE FROM MP_FAVORITO WHERE ID_USUARIO=? AND ID_PRODUTO=?',(user['id_usuario'],id_produto))
    if enabled:cur.execute('INSERT INTO MP_FAVORITO(ID_USUARIO,ID_PRODUTO) VALUES(?,?)',(user['id_usuario'],id_produto))
    con.commit();return jsonify(favorito=enabled)

def cart(cur,user,salon=None):
    cur.execute('SELECT '+P_COLS+',C.QUANTIDADE FROM MP_CARRINHO C JOIN MP_PRODUTO P ON P.ID_PRODUTO=C.ID_PRODUTO JOIN USUARIO U ON U.ID_USUARIO=P.ID_BARBEARIA WHERE C.ID_USUARIO=?'+(' AND P.ID_BARBEARIA=?' if salon else '')+' ORDER BY P.ID_PRODUTO',(user,salon) if salon else (user,))
    rows=cur.fetchall();items=[]
    for r in rows:
        product=serialize_product(cur,r[:17]);amount=r[17];price=dinheiro(product['preco'],True)
        items.append({'produto':product,'id_produto':r[0],'id_barbearia':r[1],'id_variacao':None,'chave_item':str(r[0]),'variacao':None,'nome':r[3],'preco':float(price),'quantidade':amount,'total':float(price*amount),'barbearia':product['barbearia'],'imagem':product['imagens'][0] if product['imagens'] else None,'disponivel':not product['tem_variacoes'] and bool(r[11]) and r[9]>=amount and salon_available(cur,r[1]),'estoque':r[9]})
    cur.execute('SELECT '+P_COLS+',C.QUANTIDADE,V.ID_VARIACAO FROM MP_CARRINHO_VAR C JOIN MP_VARIACAO V ON V.ID_VARIACAO=C.ID_VARIACAO JOIN MP_PRODUTO P ON P.ID_PRODUTO=V.ID_PRODUTO JOIN USUARIO U ON U.ID_USUARIO=P.ID_BARBEARIA WHERE C.ID_USUARIO=?'+(' AND P.ID_BARBEARIA=?' if salon else '')+' ORDER BY P.ID_PRODUTO,V.ID_VARIACAO',(user,salon) if salon else (user,))
    for r in cur.fetchall():
        product=serialize_product(cur,r[:17]);amount=r[17];vid=r[18];v=next(v for v in comercial.variants(cur,r[0]) if v['id_variacao']==vid)
        variant=comercial.variant_json(v,comercial.metadata(cur,r[0]),r[8]);price=dinheiro(variant['preco'],True)
        items.append({'produto':product,'id_produto':r[0],'id_barbearia':r[1],'id_variacao':vid,'chave_item':str(r[0])+':'+str(vid),'variacao':variant,'nome':r[3],'preco':float(price),'quantidade':amount,'total':float(price*amount),'barbearia':product['barbearia'],'imagem':product['imagens'][0] if product['imagens'] else None,'disponivel':bool(r[11]) and bool(v['ativo']) and v['estoque']>=amount and salon_available(cur,r[1]),'estoque':v['estoque']})
    return items

def salon_available(cur,salon):
    cur.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? AND TIPO=2 AND ATIVO=1 AND EMAIL_CONFIRMADO=1',(salon,));return bool(cur.fetchone())

def cart_hash(items,sender=None):
    return fingerprint({'itens':[{k:item[k] for k in ('id_produto','id_barbearia','preco','quantidade')}|{'id_variacao':item.get('id_variacao'),'variacao':item.get('variacao'),'pacote':{k:item['produto'][k] for k in ('peso','largura','altura','comprimento')}} for item in items],'remetente':sender or {}})
def valid_cart(items):
    if not items:raise ValueError('Carrinho vazio nesta barbearia.')
    if any(not i['disponivel'] for i in items):raise Conflito('Produto indisponível ou estoque insuficiente. Atualize seu carrinho.')

@app.get('/marketplace/carrinho')
@protected()
def get_cart(user,salon,cur,con):
    items=cart(cur,user['id_usuario']);groups={}
    for i in items:
        group=groups.setdefault(i['id_barbearia'],dict(id_barbearia=i['id_barbearia'],barbearia=i['produto']['barbearia'],itens=[],subtotal=Decimal(0)));group['itens'].append(i);group['subtotal']+=Decimal(str(i['preco']))*i['quantidade']
    for group in groups.values():group['subtotal']=float(group['subtotal'])
    return jsonify(itens=items,grupos=list(groups.values()),total=float(sum(Decimal(str(i['preco']))*i['quantidade'] for i in items)))

@app.put('/marketplace/carrinho/<int:id_produto>')
@protected()
def set_cart(user,salon,cur,con,id_produto):
    data=body();amount=qty(data.get('quantidade'),True);adding=boolean(data.get('adicionar',False));lock_user(cur,user['id_usuario']);product=get_product(cur,id_produto,active=True)
    if amount and not product:return erro('Produto não encontrado.',404)
    variation=data.get('id_variacao')
    if variation not in (None,''):
        variation=inteiro(variation,'Variação')
        v=next((v for v in comercial.variants(cur,id_produto) if v['id_variacao']==variation),None)
        if not v or (amount and not v['ativo']):return erro('Variação não encontrada ou inativa.',404)
        if adding:
            if not amount:raise ValueError('Quantidade para adicionar deve ser positiva.')
            cur.execute('SELECT QUANTIDADE FROM MP_CARRINHO_VAR WHERE ID_USUARIO=? AND ID_VARIACAO=?',(user['id_usuario'],variation));prior=cur.fetchone();amount+=prior[0] if prior else 0;qty(amount)
        if amount>v['estoque']:raise Conflito('Quantidade maior que o estoque disponível.')
        cur.execute('DELETE FROM MP_CARRINHO_VAR WHERE ID_USUARIO=? AND ID_VARIACAO=?',(user['id_usuario'],variation))
        if amount:cur.execute('INSERT INTO MP_CARRINHO_VAR(ID_USUARIO,ID_VARIACAO,QUANTIDADE) VALUES(?,?,?)',(user['id_usuario'],variation,amount))
        con.commit();return jsonify(quantidade=amount,id_variacao=variation,chave_item=str(id_produto)+':'+str(variation))
    if amount and comercial.variants(cur,id_produto):raise ValueError('Escolha uma variação deste produto.')
    if adding:
        if not amount:raise ValueError('Quantidade para adicionar deve ser positiva.')
        cur.execute('SELECT QUANTIDADE FROM MP_CARRINHO WHERE ID_USUARIO=? AND ID_PRODUTO=?',(user['id_usuario'],id_produto));prior=cur.fetchone();amount+=prior[0] if prior else 0
        qty(amount)
    if amount and amount>product[9]:raise Conflito('Quantidade maior que o estoque disponível.')
    cur.execute('DELETE FROM MP_CARRINHO WHERE ID_USUARIO=? AND ID_PRODUTO=?',(user['id_usuario'],id_produto))
    if amount:cur.execute('INSERT INTO MP_CARRINHO(ID_USUARIO,ID_PRODUTO,QUANTIDADE) VALUES(?,?,?)',(user['id_usuario'],id_produto,amount))
    con.commit();return jsonify(quantidade=amount)

@app.put('/marketplace/produtos/<int:id_produto>/avaliacao')
@protected()
def review_product(user,salon,cur,con,id_produto):
    data=body();note=data.get('nota');comment=texto(data.get('comentario',''),1000,'Comentário')
    if isinstance(note,bool) or not isinstance(note,int) or not 1<=note<=5:raise ValueError('Nota deve ser inteira entre 1 e 5.')
    lock_user(cur,user['id_usuario']);cur.execute("SELECT ITENS FROM MP_PEDIDO WHERE ID_USUARIO=? AND STATUS='entregue'",(user['id_usuario'],))
    eligible=any(any(i['id_produto']==id_produto for i in loads(r[0],[])) for r in cur.fetchall())
    if not eligible:return erro('Avaliação disponível apenas após receber um produto comprado.',403)
    cur.execute('UPDATE OR INSERT INTO MP_AVALIACAO(ID_USUARIO,ID_PRODUTO,NOTA,COMENTARIO,ATUALIZADO_EM) VALUES(?,?,?,?,CURRENT_TIMESTAMP) MATCHING(ID_USUARIO,ID_PRODUTO)',(user['id_usuario'],id_produto,note,comment));con.commit();return jsonify(avaliacao=dict(nota=note,comentario=comment))

@app.post('/marketplace/frete')
@protected()
def calculate_shipping(user,salon,cur,con):
    data=body();target=inteiro(data.get('id_barbearia'));cep=re.sub(r'\D','',texto(data.get('cep'),10,'CEP',False))
    if not re.fullmatch(r'\d{8}',cep):raise ValueError('CEP inválido.')
    items=cart(cur,user['id_usuario'],target);valid_cart(items);cur.execute('SELECT DADOS FROM MP_REMETENTE WHERE ID_BARBEARIA=?',(target,));sender=cur.fetchone()
    if not sender:return erro('Barbearia ainda não configurou endereço de envio.',503)
    sender=loads(sender[0]);products=[dict(id=str(i['id_produto']),width=i['produto']['largura'],height=i['produto']['altura'],length=i['produto']['comprimento'],weight=i['produto']['peso'],insurance_value=i['preco'],quantity=i['quantidade']) for i in items]
    response=melhor_envio.calcular(sender['cep'],cep,products)
    if not isinstance(response,list):raise melhor_envio.EntregaErro('Resposta de cotação inválida.')
    expires=datetime.now()+timedelta(minutes=15);quotes=[]
    for service in response:
        if not isinstance(service,dict) or service.get('error') or not service.get('id'):continue
        carrier=str((service.get('company') or {}).get('name','')).casefold()
        if any(name in carrier for name in ('azul','latam','buslog')):continue
        packages=service.get('packages') or []
        if len(packages)>1 and any(name in carrier for name in ('correios','loggi','j&t')):continue
        try:price=dinheiro(service.get('custom_price',service.get('price')),True);days=qty(service.get('custom_delivery_time',service.get('delivery_time')),True)
        except ValueError:continue
        id_=uuid.uuid4().hex;info=dict(id_cotacao=id_,servico=service.get('name',''),transportadora=(service.get('company') or {}).get('name',''),preco=float(price),prazo_dias=days,expira_em=expires.isoformat(),service_id=service['id'],packages=service.get('packages',[]))
        cur.execute('INSERT INTO MP_COTACAO(ID_COTACAO,ID_USUARIO,ID_BARBEARIA,HASH_CARRINHO,CEP,DADOS,EXPIRA_EM) VALUES(?,?,?,?,?,?,?)',(id_,user['id_usuario'],target,cart_hash(items,sender),cep,dumps(info),expires));quotes.append({k:v for k,v in info.items() if k not in ('service_id','packages')})
    con.commit();return jsonify(cotacoes=quotes,retirada_disponivel=True)

def get_order(cur,id_,user,salon=None,lock=False):
    if lock:
        cur.execute('SELECT ID_PEDIDO FROM MP_PEDIDO WHERE ID_PEDIDO=?'+(' AND ID_BARBEARIA=?' if salon else ' AND ID_USUARIO=?')+' WITH LOCK',(id_,salon if salon else user))
        if not cur.fetchone():return None
    cur.execute('SELECT '+O_COLS+' FROM MP_PEDIDO P JOIN USUARIO U ON U.ID_USUARIO=P.ID_USUARIO JOIN USUARIO B ON B.ID_USUARIO=P.ID_BARBEARIA WHERE P.ID_PEDIDO=?'+(' AND P.ID_BARBEARIA=?' if salon else ' AND P.ID_USUARIO=?'),(id_,salon if salon else user));return cur.fetchone()

def order_json(row):
    order=dict(zip(('id_pedido','id_usuario','id_barbearia','status','subtotal','frete','total','retirada','endereco','itens','cotacao','pagamento_status','pagamento_id','pagamento','entrega_status','entrega_id','entrega','criado_em','cliente','barbearia'),row))
    for k in ('subtotal','frete','total'):order[k]=float(order[k])
    for k in ('endereco','itens','cotacao','pagamento','entrega'):order[k]=loads(order[k],[] if k=='itens' else {})
    order['retirada']=bool(order['retirada']);order['criado_em']=order['criado_em'].isoformat();order['pode_cancelar']=row[3]=='aguardando_pagamento' and row[11]=='nao_criado'
    if len(row)>=28 and row[20] is not None:
        resumo=dict(zip(('valor_base','frete','taxa_percentual','taxa_valor','taxa_pagador','valor_total_cliente','valor_liquido_barbearia','termos_versao'),row[20:28]))
        for field in ('valor_base','frete','taxa_percentual','taxa_valor','valor_total_cliente','valor_liquido_barbearia'):resumo[field]=float(resumo[field])
        resumo.update(ativa=row[3]!='cancelado',repasse_automatico=False,taxa_devida=0.0 if row[3]=='cancelado' else resumo['taxa_valor'])
    else:resumo=calcular(row[4],row[5],historico=True)
    order['resumo']=resumo
    order.update(subtotal_original=float(row[28]) if len(row)>28 and row[28] is not None else order['subtotal'],desconto=float(row[29] or 0) if len(row)>29 else 0.0,cupom=row[30] or '' if len(row)>30 else '')
    order['resumo'].update(subtotal_original=order['subtotal_original'],desconto=order['desconto'],cupom=order['cupom'])
    order['entrega'].update(status=row[14],id_envio=row[15]);order['integracao']={'emitir_etiquetas':bool(app.config.get('MELHOR_ENVIO_EMITIR_ETIQUETAS',False))};return order

def resumo_carrinho(cur,user,target,data):
    pickup=boolean(data.get('retirada',False));destination=address(data.get('endereco'))
    cur.execute('SELECT TIPO FROM USUARIO WHERE ID_USUARIO=? AND ATIVO=1 AND EMAIL_CONFIRMADO=1',(target,));role=cur.fetchone()
    if not role or role[0]!=2:raise ValueError('Barbearia não encontrada.')
    items=cart(cur,user['id_usuario'],target);valid_cart(items);shipping=Decimal('0.00');quote_data={}
    if not pickup:
        quote_id=texto(data.get('id_cotacao'),32,'Cotação',False)
        cur.execute('SELECT HASH_CARRINHO,CEP,DADOS,EXPIRA_EM FROM MP_COTACAO WHERE ID_COTACAO=? AND ID_USUARIO=? AND ID_BARBEARIA=?',(quote_id,user['id_usuario'],target));quote_row=cur.fetchone()
        if not quote_row or quote_row[3]<datetime.now() or quote_row[0]!=cart_hash(items,sender_profile(cur,target)) or quote_row[1]!=destination['cep']:raise Conflito('Cotação expirada ou incompatível com endereço e carrinho. Calcule o frete novamente.')
        quote_data=loads(quote_row[2]);shipping=dinheiro(quote_data['preco'],True)
    subtotal=sum((dinheiro(i['preco'],True)*i['quantidade'] for i in items),Decimal('0.00'))
    coupon_id,rebate,code=comercial.apply_coupon(cur,target,data.get('cupom',''),subtotal)
    resumo=resumo_confirmavel(subtotal-rebate,shipping,{'barbearia':target,'cliente':user['id_usuario'],
        'carrinho':[(i['id_produto'],i.get('id_variacao'),i['quantidade'],str(dinheiro(i['preco'],True)),i.get('variacao')) for i in items],
        'cupom':code,'id_cupom':coupon_id,'desconto':str(rebate),'subtotal_original':str(subtotal),
        'retirada':pickup,'endereco':destination,'cotacao':quote_data})
    resumo.update(subtotal_original=float(subtotal),desconto=float(rebate),cupom=code)
    return resumo,items,destination,quote_data

@app.post('/marketplace/pedidos/resumo')
@protected()
def checkout_summary(user,salon,cur,con):
    data=body();target=inteiro(data.get('id_barbearia'))
    resumo,*_=resumo_carrinho(cur,user,target,data)
    return jsonify(resumo=resumo)

@app.post('/marketplace/pedidos')
@protected()
def checkout(user,salon,cur,con):
    data=body();target=inteiro(data.get('id_barbearia'));operation=key(data.get('chave_idempotencia'));pickup=boolean(data.get('retirada',False));destination=address(data.get('endereco'));hash_=fingerprint(data)
    lock_user(cur,user['id_usuario']);lock_user(cur,target)
    cur.execute('SELECT ID_PEDIDO,HASH_PEDIDO FROM MP_PEDIDO WHERE ID_USUARIO=? AND CHAVE=?',(user['id_usuario'],operation));prior=cur.fetchone()
    if prior:
        if prior[1]!=hash_:raise Conflito('Esta chave já foi usada com outros dados.')
        return jsonify(pedido=order_json(get_order(cur,prior[0],user['id_usuario'])))
    exigir_aceite(cur,user['id_usuario'])
    exigir_aceites(cur,user['id_usuario'],user['id_usuario'],target)
    cur.execute('SELECT TIPO FROM USUARIO WHERE ID_USUARIO=? AND ATIVO=1 AND EMAIL_CONFIRMADO=1',(target,));role=cur.fetchone()
    if not role or role[0]!=2:return erro('Barbearia não encontrada.',404)
    resumo,items,destination,quote_data=resumo_carrinho(cur,user,target,data)
    confirmar_resumo(data,resumo);shipping=dinheiro(resumo['frete'])
    snapshot=[];costs=[];subtotal=Decimal(0)
    for i in items:
        amount=i['quantidade'];price=dinheiro(i['preco'],True);subtotal+=price*amount
        if subtotal+shipping>Decimal('9999999999.99'):raise ValueError('Valor total do pedido excede o limite permitido.')
        snapshot.append({k:i[k] for k in ('id_produto','nome','preco','quantidade','total','imagem')}|{'id_variacao':i.get('id_variacao'),'variacao':i.get('variacao'),'peso':i['produto']['peso'],'largura':i['produto']['largura'],'altura':i['produto']['altura'],'comprimento':i['produto']['comprimento']})
        if i.get('id_variacao'):
            cur.execute('SELECT CUSTO_COMPRA FROM MP_VARIACAO WHERE ID_VARIACAO=?',(i['id_variacao'],));purchase=cur.fetchone()[0]
            cur.execute('UPDATE MP_VARIACAO SET ESTOQUE=ESTOQUE-? WHERE ID_VARIACAO=? AND ID_PRODUTO=? AND ATIVO=1 AND ESTOQUE>=?',(amount,i['id_variacao'],i['id_produto'],amount))
        else:
            purchase=comercial.metadata(cur,i['id_produto'])['custo_compra']
            cur.execute('UPDATE MP_PRODUTO SET ESTOQUE=ESTOQUE-? WHERE ID_PRODUTO=? AND ATIVO=1 AND ESTOQUE>=?',(amount,i['id_produto'],amount))
        if cur.rowcount!=1:raise Conflito('Estoque alterado. Atualize seu carrinho.')
        costs.append(str(purchase) if purchase is not None else None)
        stock_move(cur,i['id_produto'],user['id_usuario'],-amount,'reserva','Reserva para pedido',variation=i.get('id_variacao'))
    coupon_id,rebate,code=comercial.apply_coupon(cur,target,data.get('cupom',''),subtotal)
    original=subtotal;subtotal-=rebate
    id_=next_id(cur,'SEQ_MP_PEDIDO');cur.execute('INSERT INTO MP_PEDIDO(ID_PEDIDO,ID_USUARIO,ID_BARBEARIA,CHAVE,HASH_PEDIDO,STATUS,SUBTOTAL,FRETE,TOTAL,RETIRADA,ENDERECO,ITENS,COTACAO) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (id_,user['id_usuario'],target,operation,hash_,'aguardando_pagamento',subtotal,shipping,dinheiro(resumo['valor_total_cliente'],True),int(pickup),dumps(destination),dumps(snapshot),dumps(quote_data)))
    cur.execute('INSERT INTO MP_PEDIDO_COMERCIAL(ID_PEDIDO,SUBTOTAL_ORIGINAL,DESCONTO,CODIGO_CUPOM,CUSTOS) VALUES(?,?,?,?,?)',(id_,original,rebate,code,dumps(costs)))
    if coupon_id:cur.execute('INSERT INTO MP_CUPOM_USO(ID_PEDIDO,ID_CUPOM,ATIVO) VALUES(?,?,1)',(id_,coupon_id))
    registrar_taxa(cur,'pedido',id_,subtotal,shipping,user['id_usuario'],user['id_usuario'],target)
    for i in items:
        if i.get('id_variacao'):cur.execute('DELETE FROM MP_CARRINHO_VAR WHERE ID_USUARIO=? AND ID_VARIACAO=?',(user['id_usuario'],i['id_variacao']))
        else:cur.execute('DELETE FROM MP_CARRINHO WHERE ID_USUARIO=? AND ID_PRODUTO=?',(user['id_usuario'],i['id_produto']))
    con.commit();return jsonify(pedido=order_json(get_order(cur,id_,user['id_usuario']))),201

@app.get('/marketplace/pedidos')
@protected()
def buyer_orders(user,salon,cur,con):
    cur.execute('SELECT '+O_COLS+' FROM MP_PEDIDO P JOIN USUARIO U ON U.ID_USUARIO=P.ID_USUARIO JOIN USUARIO B ON B.ID_USUARIO=P.ID_BARBEARIA WHERE P.ID_USUARIO=? ORDER BY P.ID_PEDIDO DESC',(user['id_usuario'],));return jsonify(pedidos=[order_json(r) for r in cur.fetchall()])

@app.get('/gestao/marketplace/pedidos')
@protected('owner')
def owner_orders(user,salon,cur,con):
    cur.execute('SELECT '+O_COLS+' FROM MP_PEDIDO P JOIN USUARIO U ON U.ID_USUARIO=P.ID_USUARIO JOIN USUARIO B ON B.ID_USUARIO=P.ID_BARBEARIA WHERE P.ID_BARBEARIA=? ORDER BY P.ID_PEDIDO DESC',(salon,));orders=[order_json(r) for r in cur.fetchall()]
    status=request.args.get('status');search=texto(request.args.get('busca'),150,'Busca').casefold()
    return jsonify(pedidos=[o for o in orders if (not status or o['status']==status) and (not search or search in (str(o['id_pedido'])+' '+o['cliente']).casefold())])

@app.get('/marketplace/pedidos/<int:id_pedido>')
@protected()
def buyer_order(user,salon,cur,con,id_pedido):
    row=get_order(cur,id_pedido,user['id_usuario'])
    return jsonify(pedido=order_json(row)) if row else erro('Pedido não encontrado.',404)

@app.get('/gestao/marketplace/pedidos/<int:id_pedido>')
@protected('owner')
def owner_order(user,salon,cur,con,id_pedido):
    row=get_order(cur,id_pedido,user['id_usuario'],salon)
    return jsonify(pedido=order_json(row)) if row else erro('Pedido não encontrado.',404)

@app.post('/marketplace/pedidos/<int:id_pedido>/cancelar')
@protected()
def cancel_order(user,salon,cur,con,id_pedido):
    lock_user(cur,user['id_usuario']);row=get_order(cur,id_pedido,user['id_usuario'],lock=True)
    if not row:return erro('Pedido não encontrado.',404)
    if row[3]=='cancelado':return jsonify(pedido=order_json(row))
    if row[3]!='aguardando_pagamento' or row[11]!='nao_criado':raise Conflito('Pedido com cobrança ou pagamento exige conciliação e estorno antes de cancelar.')
    lock_user(cur,row[2])
    for item in loads(row[9],[]):
        if item.get('id_variacao'):cur.execute('UPDATE MP_VARIACAO SET ESTOQUE=ESTOQUE+? WHERE ID_VARIACAO=?',(item['quantidade'],item['id_variacao']))
        else:cur.execute('UPDATE MP_PRODUTO SET ESTOQUE=ESTOQUE+? WHERE ID_PRODUTO=?',(item['quantidade'],item['id_produto']))
        stock_move(cur,item['id_produto'],user['id_usuario'],item['quantidade'],'cancelamento','Pedido #'+str(id_pedido),variation=item.get('id_variacao'))
    cur.execute('UPDATE MP_CUPOM_USO SET ATIVO=0 WHERE ID_PEDIDO=?',(id_pedido,))
    cur.execute("UPDATE MP_PEDIDO SET STATUS='cancelado',ATUALIZADO_EM=CURRENT_TIMESTAMP WHERE ID_PEDIDO=?",(id_pedido,));con.commit();return jsonify(pedido=order_json(get_order(cur,id_pedido,user['id_usuario'])))

@app.patch('/gestao/marketplace/pedidos/<int:id_pedido>/status')
@protected('owner')
def status_order(user,salon,cur,con,id_pedido):
    desired=body().get('status');row=get_order(cur,id_pedido,user['id_usuario'],salon,True)
    if not row:return erro('Pedido não encontrado.',404)
    if row[11]!='pago':raise Conflito('Confirme o pagamento antes de preparar ou entregar o pedido.')
    allowed={'pago':{'separando'},'separando':{'pronto_retirada'} if row[7] else set(),'pronto_retirada':{'entregue'}}
    if desired!=row[3] and desired not in allowed.get(row[3],set()):raise Conflito('Transição de status inválida. Entregas por transportadora são confirmadas pelo rastreio.')
    cur.execute('UPDATE MP_PEDIDO SET STATUS=?,ATUALIZADO_EM=CURRENT_TIMESTAMP WHERE ID_PEDIDO=?',(desired,id_pedido));con.commit();return jsonify(pedido=order_json(get_order(cur,id_pedido,user['id_usuario'],salon)))

def pix_response(data,total,expected_id=None):
    if not isinstance(data,dict):raise ValueError('Resposta Pix inválida.')
    id_=str(data.get('id_cobranca') or data.get('id') or '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',id_) or (expected_id and id_!=expected_id):raise ValueError('Identificação Pix inválida.')
    status=data.get('status')
    if isinstance(status,bool) or status not in (0,1,'0','1'):raise ValueError('Status Pix desconhecido; confira a cobrança.')
    if dinheiro(data.get('valor'),True)!=dinheiro(total,True):raise ValueError('Valor da cobrança diferente do pedido.')
    code=data.get('codigo_pagamento') or data.get('pix_copia_cola') or data.get('pix') or data.get('codigo_pix') or ''
    if not isinstance(code,str) or len(code)>5000:raise ValueError('Código Pix inválido.')
    return dict(id_cobranca=id_,codigo_pix=code,valor=float(total),status=int(status))

@app.post('/marketplace/pedidos/<int:id_pedido>/pix')
@protected()
def create_pix(user,salon,cur,con,id_pedido):
    from pagamento import _credenciais_da_barbearia
    from arkhe import _chamar_arkhe,ArkheErro
    row=get_order(cur,id_pedido,user['id_usuario'],lock=True)
    if not row:return erro('Pedido não encontrado.',404)
    if row[3]=='cancelado':raise Conflito('Pedido cancelado não pode gerar cobrança.')
    if row[11] in ('pendente','pago'):return jsonify(pedido=order_json(row),pagamento=loads(row[13],{}))
    if row[11]!='nao_criado':raise Conflito('Cobrança em processamento ou com resultado incerto. Confira a Arkhé antes de nova tentativa.')
    try:credentials=_credenciais_da_barbearia(row[2])
    except RuntimeError:return erro('Conta Arkhé da barbearia não configurada.',503)
    if not app.config.get('ARKHE_BASE_URL'):return erro('Arkhé não configurada.',503)
    cur.execute("UPDATE MP_PEDIDO SET PAGAMENTO_STATUS='processando' WHERE ID_PEDIDO=?",(id_pedido,));con.commit()
    try:
        response=_chamar_arkhe('POST','/api/v1/cobrancas/pix',corpo={'valor':float(row[6])},credenciais=credentials)
        payment=pix_response(response,row[6])
    except (ArkheErro,ValueError):
        cur.execute("UPDATE MP_PEDIDO SET PAGAMENTO_STATUS='incerto' WHERE ID_PEDIDO=?",(id_pedido,));con.commit()
        return erro('Não foi possível confirmar a criação da cobrança. Confira a Arkhé; a operação não será repetida automaticamente.',502)
    cur.execute('UPDATE MP_PEDIDO SET PAGAMENTO_STATUS=?,PAGAMENTO_ID=?,PAGAMENTO_DADOS=?,STATUS=?,ATUALIZADO_EM=CURRENT_TIMESTAMP WHERE ID_PEDIDO=?',
        ('pago' if payment['status']==1 else 'pendente',payment['id_cobranca'],dumps(payment),'pago' if payment['status']==1 else row[3],id_pedido));con.commit()
    return jsonify(pedido=order_json(get_order(cur,id_pedido,user['id_usuario'])),pagamento=payment),201

@app.get('/marketplace/pedidos/<int:id_pedido>/pagamento')
@protected()
def consult_pix(user,salon,cur,con,id_pedido):
    from pagamento import _credenciais_da_barbearia
    from arkhe import _chamar_arkhe,ArkheErro
    row=get_order(cur,id_pedido,user['id_usuario'],lock=True)
    if not row:return erro('Pedido não encontrado.',404)
    if row[11]=='pago' or row[3]=='cancelado':return jsonify(pedido=order_json(row),pagamento=loads(row[13],{}))
    if row[11]!='pendente' or not row[12]:return erro('Cobrança ainda não disponível ou exige conferência manual.',409)
    try:
        credentials=_credenciais_da_barbearia(row[2]);response=_chamar_arkhe('GET','/api/v1/cobrancas/pix/'+quote(row[12],safe=''),credenciais=credentials);payment=pix_response(response,row[6],row[12])
    except RuntimeError:return erro('Conta Arkhé da barbearia não configurada.',503)
    except (ArkheErro,ValueError):return erro('Não foi possível confirmar o pagamento com a Arkhé.',502)
    if payment['status']==1:cur.execute("UPDATE MP_PEDIDO SET PAGAMENTO_STATUS='pago',STATUS='pago',PAGAMENTO_DADOS=?,ATUALIZADO_EM=CURRENT_TIMESTAMP WHERE ID_PEDIDO=?",(dumps(payment),id_pedido));con.commit()
    return jsonify(pedido=order_json(get_order(cur,id_pedido,user['id_usuario'])),pagamento=payment)

def sender_profile(cur,salon):
    cur.execute('SELECT DADOS FROM MP_REMETENTE WHERE ID_BARBEARIA=?',(salon,));row=cur.fetchone();return loads(row[0],{}) if row else {}

def label_count(cur):
    cur.execute("SELECT COUNT(*) FROM MP_PEDIDO WHERE ENTREGA_STATUS IN ('comprando','compra_incerta','comprada','gerando','geracao_incerta','gerada','vinculada')")
    return cur.fetchone()[0]

@app.route('/gestao/marketplace/remetente',methods=['GET','PUT'])
@protected('owner')
def sender(user,salon,cur,con):
    if request.method=='PUT':
        data=address(body());lock_user(cur,salon);cur.execute('UPDATE OR INSERT INTO MP_REMETENTE(ID_BARBEARIA,DADOS) VALUES(?,?) MATCHING(ID_BARBEARIA)',(salon,dumps(data)));con.commit()
    return jsonify(remetente=sender_profile(cur,salon),integracao=dict(configurada=melhor_envio.configurado(),emitir_etiquetas=bool(app.config.get('MELHOR_ENVIO_EMITIR_ETIQUETAS',False)),limite_etiquetas=3,etiquetas_utilizadas=label_count(cur),sandbox=bool(app.config.get('MELHOR_ENVIO_SANDBOX'))))

def provider_address(data):
    result={'name':data['nome'],'phone':data['telefone'],'email':data['email'],**({'document':data['documento']} if len(data['documento'])==11 else {'company_document':data['documento']}),'address':data['logradouro'],'number':data['numero'],'complement':data.get('complemento',''),'district':data['bairro'],'city':data['cidade'],'state_abbr':data['uf'],'postal_code':data['cep'],'country_id':'BR'}
    if data.get('inscricao_estadual'):result['state_register']=data['inscricao_estadual']
    return result

def shipping_state(cur,id_,state,details=None,provider_id=None):
    if details is None:cur.execute('UPDATE MP_PEDIDO SET ENTREGA_STATUS=?,ATUALIZADO_EM=CURRENT_TIMESTAMP WHERE ID_PEDIDO=?',(state,id_))
    else:cur.execute('UPDATE MP_PEDIDO SET ENTREGA_STATUS=?,ENTREGA_DADOS=?,ENTREGA_ID=?,ATUALIZADO_EM=CURRENT_TIMESTAMP WHERE ID_PEDIDO=?',(state,dumps(details),provider_id,id_))

def safe_label_url(value):
    if not isinstance(value,str):return None
    url=urlsplit(value)
    if url.scheme!='https' or url.username or url.password:return None
    host=(url.hostname or '').lower()
    if host in ('melhorenvio.com.br','sandbox.melhorenvio.com.br') or host.endswith('.melhorenvio.com.br'):return value
    return None

@app.post('/gestao/marketplace/pedidos/<int:id_pedido>/etiqueta')
@protected('owner')
def label_action(user,salon,cur,con,id_pedido):
    if not app.config.get('MELHOR_ENVIO_EMITIR_ETIQUETAS',False):return erro('Emissão de etiquetas não autorizada. A integração atual permite somente cotação e rastreio.',403)
    data=body();action=data.get('acao');row=get_order(cur,id_pedido,user['id_usuario'],salon,True)
    if not row:return erro('Pedido não encontrado.',404)
    if row[7] or row[11]!='pago' or row[3] in ('cancelado','entregue'):raise Conflito('Etiqueta exige pedido pago com entrega disponível.')
    if not melhor_envio.configurado():return erro('Melhor Envio não configurado no servidor.',503)
    if action not in ('preparar','comprar','gerar'):raise ValueError('Ação de etiqueta inválida.')
    state=row[14];details=loads(row[16],{});provider_id=row[15]
    if action=='preparar':
        if state=='preparada':return jsonify(pedido=order_json(row),entrega=order_json(row)['entrega'])
        if state!='nao_criada':raise Conflito('Envio já iniciado ou exige conciliação. Não será criado novamente.')
        sender=sender_profile(cur,salon)
        if not sender:raise ValueError('Configure o remetente primeiro.')
        invoice=texto(data.get('nota_fiscal'),44,'Chave da nota fiscal',False)
        if not re.fullmatch(r'\d{44}',invoice) or not sender.get('inscricao_estadual'):raise ValueError('Envio comercial exige chave de nota fiscal com 44 dígitos e inscrição estadual do remetente.')
        quote_data=loads(row[10],{});items=loads(row[9],[])
        if not quote_data.get('service_id'):raise Conflito('Pedido não tem serviço de frete válido.')
        # Consolidated dimensions conservatively stack items; quote provider packages carry original package when available.
        packages=quote_data.get('packages') or []
        if not packages:raise ValueError('A cotação não informou a embalagem. Recalcule o frete antes de gerar a etiqueta.')
        volumes=[]
        for package in packages:
            dimensions=package.get('dimensions') or package
            volume={k:float(dimensions.get(k) if k!='weight' else package.get(k)) for k in ('width','height','length','weight')}
            if any(not Decimal(str(v)).is_finite() or v<=0 for v in volume.values()):raise ValueError('Dimensões de embalagem inválidas na cotação.')
            volumes.append(volume)
        payload={'service':quote_data['service_id'],'from':provider_address(sender),'to':provider_address(loads(row[8])), 'products':[{'name':i['nome'],'quantity':i['quantidade'],'unitary_value':i['preco']} for i in items], 'volumes':volumes,'options':{'insurance_value':float(row[4]),'receipt':False,'own_hand':False,'reverse':False,'non_commercial':False,'invoice':{'key':invoice}}}
        shipping_state(cur,id_pedido,'preparando');con.commit()
        try:
            response=melhor_envio.chamar('POST','/api/v2/me/cart',payload);provider_id=str(response.get('id') or '') if isinstance(response,dict) else ''
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,150}',provider_id):raise melhor_envio.EntregaErro('ID do envio inválido.')
            cost=dinheiro(response.get('price'),True);details=dict(custo_etiqueta=float(cost),nota_fiscal=invoice,servico=quote_data['servico'])
        except (melhor_envio.EntregaErro,ValueError):shipping_state(cur,id_pedido,'preparo_incerto');con.commit();return erro('Resultado do preparo incerto. Confira o carrinho do Melhor Envio antes de tentar novamente.',502)
        shipping_state(cur,id_pedido,'preparada',details,provider_id);con.commit()
    elif action=='comprar':
        if state=='comprada':return jsonify(pedido=order_json(row),entrega=order_json(row)['entrega'])
        if state!='preparada':raise Conflito('Prepare a etiqueta antes da compra. Estados incertos exigem conferência manual.')
        if data.get('confirmar_custo') is not True:raise ValueError('Confirme explicitamente o custo da etiqueta para usar o saldo Melhor Envio.')
        cur.execute('SELECT ID FROM MP_INTEGRACAO WHERE ID=1 WITH LOCK');cur.fetchone()
        if label_count(cur)>=3:raise Conflito('Limite de três envios simultâneos da plataforma atingido. Confira os envios pendentes.')
        shipping_state(cur,id_pedido,'comprando');con.commit()
        try:
            response=melhor_envio.chamar('POST','checkout',{'orders':[provider_id]})
            if not isinstance(response,dict) or response.get('error') or not response.get('purchase'):raise melhor_envio.EntregaErro('Compra não confirmada.')
        except melhor_envio.EntregaErro:shipping_state(cur,id_pedido,'compra_incerta');con.commit();return erro('Resultado da compra incerto. Confira o Melhor Envio antes de tentar novamente.',502)
        shipping_state(cur,id_pedido,'comprada',details,provider_id);con.commit()
    else:
        if state=='gerada':return jsonify(pedido=order_json(row),entrega=order_json(row)['entrega'])
        if state!='comprada':raise Conflito('Compre a etiqueta antes de gerar. Estados incertos exigem conferência manual.')
        shipping_state(cur,id_pedido,'gerando');con.commit()
        try:
            response=melhor_envio.chamar('POST','generate',{'orders':[provider_id]})
            if not isinstance(response,dict) or response.get('error') or response.get('errors') or response.get('success') is False:raise melhor_envio.EntregaErro('Geração não confirmada.')
            printed=melhor_envio.chamar('POST','print',{'mode':'public','orders':[provider_id]});url=safe_label_url(printed.get('url') if isinstance(printed,dict) else None)
            if not url:raise melhor_envio.EntregaErro('URL da etiqueta indisponível.')
        except melhor_envio.EntregaErro:shipping_state(cur,id_pedido,'geracao_incerta');con.commit();return erro('Geração exige conferência manual no Melhor Envio.',502)
        details['url_etiqueta']=url;shipping_state(cur,id_pedido,'gerada',details,provider_id);con.commit()
    result=order_json(get_order(cur,id_pedido,user['id_usuario'],salon));return jsonify(pedido=result,entrega=result['entrega'])


# Explicit dependency keeps commercial route registration free of circular imports.
import sys as _sys
comercial.register(_sys.modules[__name__])

@app.get('/gestao/marketplace/pedidos/<int:id_pedido>/etiqueta')
@protected('owner')
def label_read(user,salon,cur,con,id_pedido):
    row=get_order(cur,id_pedido,user['id_usuario'],salon)
    if not row:return erro('Pedido não encontrado.',404)
    order=order_json(row);return jsonify(pedido=order,entrega=order['entrega'],url_etiqueta=order['entrega'].get('url_etiqueta'))

@app.post('/gestao/marketplace/pedidos/<int:id_pedido>/rastreio')
@protected('owner')
def tracking(user,salon,cur,con,id_pedido):
    row=get_order(cur,id_pedido,user['id_usuario'],salon,True)
    if not row:return erro('Pedido não encontrado.',404)
    if not row[15] or row[14] not in ('vinculada','gerada','enviado','entregue'):raise Conflito('Envio não disponível para rastreio.')
    response=melhor_envio.chamar('POST','tracking',{'orders':[row[15]]});entry=tracking_entry(response,row[15])
    details=loads(row[16],{});details['rastreio']=texto(entry.get('tracking'),150,'Rastreio');details['status_transportadora']=texto(entry.get('status'),100,'Status')
    # Only provider terminal delivery states may fulfil a shipping order.
    if row[14]=='entregue':
        details['status_transportadora']='delivered';shipping_state(cur,id_pedido,'entregue',details,row[15])
    elif entry.get('status') in ('delivered','posted','in_transit'):
        state='entregue' if entry['status']=='delivered' else 'enviado';shipping_state(cur,id_pedido,state,details,row[15]);cur.execute('UPDATE MP_PEDIDO SET STATUS=? WHERE ID_PEDIDO=?',(state,id_pedido))
    else:shipping_state(cur,id_pedido,row[14],details,row[15])
    con.commit();order=order_json(get_order(cur,id_pedido,user['id_usuario'],salon));return jsonify(pedido=order,entrega=order['entrega'])

def tracking_entry(response,provider_id):
    entry=response.get(provider_id) if isinstance(response,dict) else None
    if not isinstance(entry,dict) or entry.get('error') or entry.get('errors') or entry.get('status') not in ('pending','released','posted','in_transit','delivered','undelivered','canceled','cancelled'):
        raise melhor_envio.EntregaErro('Não foi possível validar esse envio com o Melhor Envio.')
    if entry.get('id') and str(entry['id']).lower()!=provider_id.lower():raise melhor_envio.EntregaErro('Identificação de rastreio divergente.')
    return entry

@app.post('/gestao/marketplace/pedidos/<int:id_pedido>/vincular-envio')
@protected('owner')
def bind_shipping(user,salon,cur,con,id_pedido):
    """Responsável declara vínculo de etiqueta externa; API valida existência, não titularidade remota."""
    data=body()
    if data.get('confirmar_vinculo') is not True:raise ValueError('Confirme que este envio corresponde a este pedido.')
    try:provider_id=str(uuid.UUID(texto(data.get('id_envio'),36,'Identificação do envio',False)))
    except (ValueError,AttributeError):raise ValueError('Informe o UUID válido do envio Melhor Envio.') from None
    row=get_order(cur,id_pedido,user['id_usuario'],salon,True)
    if not row:return erro('Pedido não encontrado.',404)
    if row[7] or row[11]!='pago' or row[3] in ('cancelado','entregue'):raise Conflito('Vínculo exige pedido pago com entrega disponível.')
    if row[15]:
        if row[15]!=provider_id:raise Conflito('Este pedido já possui outro envio vinculado.')
        return jsonify(pedido=order_json(row),entrega=order_json(row)['entrega'])
    if row[14]!='nao_criada':raise Conflito('Este pedido possui emissão em andamento ou incerta; confira antes de vincular outro envio.')
    cur.execute('SELECT ID FROM MP_INTEGRACAO WHERE ID=1 WITH LOCK');cur.fetchone()
    cur.execute('SELECT ID_PEDIDO FROM MP_PEDIDO WHERE ENTREGA_ID=?',(provider_id,))
    if cur.fetchone():raise Conflito('Este envio já está vinculado a outro pedido da plataforma.')
    response=melhor_envio.chamar('POST','tracking',{'orders':[provider_id]});entry=tracking_entry(response,provider_id)
    if entry['status'] in ('canceled','cancelled'):raise Conflito('Não é possível vincular envio cancelado.')
    details={'origem':'vinculo_manual','declaracao_responsavel':True,'id_usuario_responsavel':user['id_usuario'],'vinculado_em':datetime.now().isoformat(),
        'rastreio':texto(entry.get('tracking'),150,'Rastreio'),'status_transportadora':entry['status']}
    state='entregue' if entry['status']=='delivered' else 'enviado' if entry['status'] in ('posted','in_transit') else 'vinculada'
    shipping_state(cur,id_pedido,state,details,provider_id)
    if state in ('entregue','enviado'):cur.execute('UPDATE MP_PEDIDO SET STATUS=? WHERE ID_PEDIDO=?',(state,id_pedido))
    con.commit()
    registrar_log('UPDATE','MP_PEDIDO',id_registro=id_pedido,id_usuario=user['id_usuario'],campo='ENTREGA_ID',valor_antes=None,valor_depois=provider_id)
    result=order_json(get_order(cur,id_pedido,user['id_usuario'],salon));return jsonify(pedido=result,entrega=result['entrega'])
