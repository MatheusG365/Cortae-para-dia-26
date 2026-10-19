import { useProductSave } from "./useProductSave";
import ProductPhotoEditor from "./ProductPhotoEditor";
import { productImageLinks, productPhotoBody } from "./productPhotos";
import { appendPhoto } from "../client/Photo";
import React, { useRef, useState } from "react";
import { useLocalSearchParams } from "expo-router";
import { api, query } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, Input, RemoteImage, Screen } from "../../ui";
import {
  Badge,
  Collection,
  Copy,
  Feedback,
  Form,
  Heading,
  Resource,
  go,
  money,
  uniqueKey,
  useMutation,
  dateTime,
} from "./shared";
const base = "/gestao/marketplace";
const productFields = [
  { key: "nome", label: "Nome", required: true },
  { key: "categoria", label: "Categoria" },
  { key: "marca", label: "Marca" },
  {
    key: "preco",
    label: "Preço de venda (R$)",
    type: "number",
    required: true,
    min: 0.01,
  },
  { key: "estoque_minimo", label: "Estoque mínimo", type: "number", min: 0 },
  {
    key: "descricao",
    label: "Descrição curta",
    type: "multiline",
    required: true,
  },
  { key: "detalhes", label: "Detalhes e modo de uso", type: "multiline" },
  {
    key: "custo_compra",
    label: "Custo de compra por unidade (R$)",
    type: "number",
    nullable: true,
    min: 0,
  },
  {
    key: "promocao_preco",
    label: "Preço promocional (R$)",
    type: "number",
    nullable: true,
    min: 0.01,
  },
  {
    key: "promocao_inicio",
    label: "Início da promoção",
    type: "date",
    nullable: true,
  },
  {
    key: "promocao_fim",
    label: "Fim da promoção",
    type: "date",
    nullable: true,
  },
  {
    key: "lancamento_ate",
    label: "Destacar lançamento até",
    type: "date",
    nullable: true,
  },
  {
    key: "peso",
    label: "Peso embalado (kg)",
    type: "number",
    required: true,
    min: 0.001,
  },
  {
    key: "largura",
    label: "Largura (cm)",
    type: "number",
    required: true,
    min: 0.01,
  },
  {
    key: "altura",
    label: "Altura (cm)",
    type: "number",
    required: true,
    min: 0.01,
  },
  {
    key: "comprimento",
    label: "Comprimento (cm)",
    type: "number",
    required: true,
    min: 0.01,
  },
];
export function OwnerShop() {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");
  const state = useResource(query(`${base}/produtos`, { busca: filter }), null);
  const mut = useMutation();
  return (
    <Screen
      title="Sua loja"
      subtitle="Produtos, estoque e pedidos da barbearia."
      onRefresh={state.reload}
      refreshing={state.loading}
    >
      <Button
        title="Adicionar produto"
        icon="add"
        onPress={() => go("/barbearia/produto?id=novo")}
      />
      <Card>
        <Input label="Buscar produto" value={search} onChangeText={setSearch} />
        <Button
          title="Buscar"
          variant="secondary"
          onPress={() => setFilter(search)}
        />
      </Card>
      <Feedback state={mut} />
      <Resource
        state={state}
        empty={!!state.data && !state.data.produtos?.length}
      >
        {(state.data?.produtos ?? []).map((p) => (
          <Card key={p.id_produto}>
            <RemoteImage
              uri={p.imagens?.[0]}
              style={{ height: 170, width: "100%", borderRadius: 14 }}
            />
            <Badge>{p.ativo ? "À venda" : "Inativo"}</Badge>
            <Heading>{p.nome}</Heading>
            <Copy>
              {money(p.preco)} · {p.estoque} em estoque
            </Copy>
            <Copy muted>
              Compra: {money(p.custo_compra)} · Margem:{" "}
              {p.margem_lucro_percentual == null
                ? "Não informada"
                : `${Number(p.margem_lucro_percentual).toFixed(1)}%`}
            </Copy>
            {p.estoque <= p.estoque_minimo && (
              <Copy>Estoque baixo · Reposição recomendada</Copy>
            )}
            <Button
              title="Editar produto"
              variant="secondary"
              onPress={() => go(`/barbearia/produto?id=${p.id_produto}`)}
            />
            <Button
              title="Variações de tamanho, cor e volume"
              variant="secondary"
              onPress={() => go(`/barbearia/variacoes?id=${p.id_produto}`)}
            />
            {!p.tem_variacoes && (
              <Button
                title="Estoque e entradas"
                variant="secondary"
                onPress={() => go(`/barbearia/estoque?id=${p.id_produto}`)}
              />
            )}
            <Button
              title={p.ativo ? "Desativar produto" : "Ativar produto"}
              variant="ghost"
              disabled={mut.busy}
              onPress={() => {
                void mut.run(
                  () =>
                    api(`${base}/produtos/${p.id_produto}/ativo`, {
                      method: "PATCH",
                      body: { ativo: !p.ativo },
                    }),
                  state.reload,
                );
              }}
            />
          </Card>
        ))}
      </Resource>
      <Heading>Gerenciar loja</Heading>
      {[
        ["Pedidos e entregas", "pedidos"],
        ["Fornecedores", "fornecedores"],
        ["Cupons de desconto", "cupons"],
        ["Painel de vendas", "vendas"],
        ["Remetente das entregas", "entregas"],
      ].map(([title, path]) => (
        <Button
          key={path}
          title={title}
          variant="secondary"
          onPress={() => go(`/barbearia/${path}`)}
        />
      ))}
    </Screen>
  );
}
export function OwnerProductEditor() {
  const { id } = useLocalSearchParams();
  const isNew = id === "novo";
  const state = useResource(!isNew && id ? `${base}/produtos` : null, null);
  const suppliers = useResource(`${base}/fornecedores`, null);
  const product = state.data?.produtos?.find(
    (p) => String(p.id_produto) === String(id),
  );
  return (
    <Screen
      back
      title={isNew ? "Novo produto" : "Editar produto"}
      subtitle="Catálogo exclusivo da sua barbearia."
    >
      <Resource state={suppliers}>
        {isNew ? (
          <OwnerProductForm
            key={id}
            id={id}
            isNew={isNew}
            product={undefined}
            suppliers={suppliers}
          />
        ) : (
          <Resource state={state}>
            {product ? (
              <OwnerProductForm
                key={id}
                id={id}
                isNew={isNew}
                product={product}
                suppliers={suppliers}
              />
            ) : (
              <Copy>Produto não encontrado nesta loja.</Copy>
            )}
          </Resource>
        )}
      </Resource>
    </Screen>
  );
}
function OwnerProductForm({ id, isNew, product, suppliers }) {
  const mut = useProductSave();
  const [photos, setPhotos] = useState([]);
  const [imageLinks, setImageLinks] = useState(
    (product?.imagens ?? []).join("\n"),
  );
  const fields = [
    ...productFields.slice(0, 4),
    ...(isNew
      ? [
          {
            key: "estoque",
            label: "Estoque inicial",
            type: "number",
            min: 0,
          },
        ]
      : []),
    ...productFields.slice(4),
    {
      key: "id_fornecedor",
      label: "Fornecedor",
      options: [
        { label: "Sem fornecedor", value: "" },
        ...(suppliers.data?.fornecedores ?? []).map((f) => ({
          label: f.nome,
          value: String(f.id_fornecedor),
        })),
      ],
    },
  ];
  const initial = {
    nome: "",
    categoria: "",
    marca: "",
    estoque: 0,
    estoque_minimo: 0,
    descricao: "",
    detalhes: "",
    peso: 0.1,
    largura: 10,
    altura: 5,
    comprimento: 15,
    ativo: true,
    ...product,
    preco_cadastro: undefined,
    preco_original: undefined,
    imagens: (product?.imagens ?? []).join("\n"),
    preco:
      product?.preco_cadastro ??
      product?.preco_original ??
      product?.preco ??
      "",
    id_fornecedor: String(product?.id_fornecedor ?? ""),
  };
  return (
    <Card>
      <Feedback state={mut} />
      <ProductPhotoEditor
        links={imageLinks}
        setLinks={setImageLinks}
        photos={photos}
        setPhotos={setPhotos}
        busy={mut.busy}
      />
      <Form
        key={id}
        fields={fields}
        initial={initial}
        busy={mut.busy}
        title="Salvar produto"
        onSubmit={(v) =>
          mut.run(
            async ({ current, sessionVersion, signal }) => {
              const images = productImageLinks(imageLinks);
              const body = {
                ...v,
                imagens: images,
                id_fornecedor: v.id_fornecedor ? Number(v.id_fornecedor) : null,
              };
              if (!isNew) delete body.estoque;
              const prepared = await productPhotoBody(
                body,
                photos,
                appendPhoto,
              );
              if (!current()) return;
              await api(`${base}/produtos${isNew ? "" : `/${id}`}`, {
                method: isNew ? "POST" : "PUT",
                body: prepared,
                expectedSessionVersion: sessionVersion,
                signal,
              });
            },
            () => go("/barbearia/loja"),
          )
        }
      />
      <Copy muted>
        O estoque de produtos existentes deve ser alterado pela entrada de
        estoque. Promoções das variações seguem a mesma redução percentual do
        produto.
      </Copy>
    </Card>
  );
}
export function OwnerStock() {
  const { id, variacao } = useLocalSearchParams();
  const [revision, setRevision] = useState(0);
  const path = `${base}/produtos/${id}${variacao ? `/variacoes/${variacao}` : ""}/estoque`;
  const state = useResource(id ? path : null, null);
  const mut = useMutation();
  const attempt = useRef({ signature: "", key: "" });
  return (
    <Screen
      back
      title="Estoque e entradas"
      subtitle={
        variacao ? `Variação #${variacao} · Produto #${id}` : `Produto #${id}`
      }
      onRefresh={state.reload}
      refreshing={state.loading}
    >
      <Feedback state={mut} />
      <Card>
        <Heading>Registrar reposição</Heading>
        <Form
          key={revision}
          fields={[
            {
              key: "quantidade",
              label: "Quantidade recebida",
              type: "number",
              required: true,
              min: 1,
              max: 999999,
            },
            { key: "observacao", label: "Observação" },
          ]}
          initial={{ quantidade: "", observacao: "" }}
          title="Registrar entrada"
          busy={mut.busy}
          onSubmit={(body) =>
            mut.run(
              async () => {
                if (!Number.isInteger(body.quantidade))
                  throw new Error("Informe uma quantidade inteira.");
                const signature = JSON.stringify(body);
                if (attempt.current.signature !== signature)
                  attempt.current = { signature, key: uniqueKey() };
                await api(path, {
                  method: "POST",
                  body: { ...body, chave_idempotencia: attempt.current.key },
                });
                attempt.current = { signature: "", key: "" };
              },
              async () => {
                await state.reload();
                setRevision((v) => v + 1);
              },
              "Entrada de estoque registrada.",
            )
          }
        />
      </Card>
      <Resource state={state}>
        <Collection
          title="Histórico de movimentações"
          rows={state.data?.movimentacoes ?? []}
          fields={[
            ["criado_em", "Data", dateTime],
            ["tipo", "Tipo"],
            ["quantidade", "Quantidade"],
            ["observacao", "Observação"],
          ]}
        />
      </Resource>
    </Screen>
  );
}
export function OwnerVariants() {
  const { id } = useLocalSearchParams();
  const path = `${base}/produtos/${id}/variacoes`;
  const state = useResource(id ? path : null, null);
  const mut = useMutation();
  const [editor, setEditor] = useState(null);
  return (
    <Screen
      back
      title="Variações do produto"
      subtitle="Cada tamanho, cor ou volume tem preço e estoque próprios."
      onRefresh={state.reload}
      refreshing={state.loading}
    >
      <Button
        title="Adicionar variação"
        onPress={() =>
          setEditor({
            nome: "",
            sku: "",
            tamanho: "",
            cor: "",
            volume: "",
            preco: "",
            custo_compra: "",
            estoque: 0,
            ativo: true,
          })
        }
      />
      <Feedback state={mut} />
      {editor && (
        <Card>
          <Heading>
            {editor.id_variacao ? "Editar variação" : "Nova variação"}
          </Heading>
          <Form
            key={editor.id_variacao ?? "new"}
            initial={editor}
            busy={mut.busy}
            title="Salvar variação"
            fields={[
              { key: "nome", label: "Nome", required: true },
              { key: "sku", label: "SKU" },
              { key: "tamanho", label: "Tamanho" },
              { key: "cor", label: "Cor" },
              { key: "volume", label: "Volume" },
              {
                key: "preco",
                label: "Preço de venda (R$)",
                type: "number",
                required: true,
                min: 0.01,
              },
              {
                key: "custo_compra",
                label: "Custo por unidade (R$)",
                type: "number",
                nullable: true,
                min: 0,
              },
              ...(!editor.id_variacao
                ? [
                    {
                      key: "estoque",
                      label: "Estoque inicial",
                      type: "number",
                      min: 0,
                    },
                  ]
                : []),
            ]}
            onSubmit={(body) =>
              mut.run(
                async () => {
                  if (editor.id_variacao) delete body.estoque;
                  await api(
                    `${path}${editor.id_variacao ? `/${editor.id_variacao}` : ""}`,
                    { method: editor.id_variacao ? "PUT" : "POST", body },
                  );
                },
                async () => {
                  setEditor(null);
                  await state.reload();
                },
              )
            }
          />
          <Button
            title="Fechar edição"
            variant="ghost"
            onPress={() => setEditor(null)}
          />
        </Card>
      )}
      <Resource
        state={state}
        empty={!!state.data && !state.data.variacoes?.length}
      >
        {(state.data?.variacoes ?? []).map((v) => (
          <Card key={v.id_variacao}>
            <Badge>{v.ativo ? "Ativa" : "Inativa"}</Badge>
            <Heading>{v.nome}</Heading>
            <Copy muted>
              {[v.tamanho, v.cor, v.volume, v.sku].filter(Boolean).join(" · ")}
            </Copy>
            <Copy>
              {money(v.preco)} · {v.estoque} unidades
            </Copy>
            <Button
              title="Editar variação"
              variant="secondary"
              onPress={() =>
                setEditor({ ...v, preco: v.preco_original ?? v.preco })
              }
            />
            <Button
              title="Estoque desta variação"
              variant="secondary"
              onPress={() =>
                go(`/barbearia/estoque?id=${id}&variacao=${v.id_variacao}`)
              }
            />
            <Button
              title={v.ativo ? "Desativar" : "Ativar"}
              variant="ghost"
              disabled={mut.busy}
              onPress={() => {
                void mut.run(
                  () =>
                    api(`${path}/${v.id_variacao}/ativo`, {
                      method: "PATCH",
                      body: { ativo: !v.ativo },
                    }),
                  state.reload,
                );
              }}
            />
          </Card>
        ))}
      </Resource>
    </Screen>
  );
}
