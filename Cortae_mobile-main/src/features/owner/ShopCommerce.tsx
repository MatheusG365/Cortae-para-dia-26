import React, { useState } from "react";
import { View } from "react-native";
import { api, query } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, Screen, Stat } from "../../ui";
import {
  Badge,
  Collection,
  Copy,
  Feedback,
  Field,
  Form,
  Heading,
  Period,
  Resource,
  money,
  monthPeriod,
  s,
  useMutation,
} from "./shared";
const base = "/gestao/marketplace";
export function OwnerCommercial({ type }: { type: "fornecedores" | "cupons" }) {
  const coupon = type === "cupons";
  const idKey = coupon ? "id_cupom" : "id_fornecedor";
  const state = useResource<any>(`${base}/${type}`, null);
  const [editor, setEditor] = useState<any>(null);
  const mut = useMutation();
  const fields: Field[] = coupon
    ? [
        { key: "codigo", label: "Código", required: true },
        {
          key: "tipo",
          label: "Desconto",
          options: [
            { label: "Percentual (%)", value: "percentual" },
            { label: "Valor fixo (R$)", value: "fixo" },
          ],
        },
        {
          key: "valor",
          label: "Valor do desconto",
          type: "number",
          required: true,
          min: 0.01,
        },
        { key: "inicio", label: "Início", type: "date", required: true },
        { key: "fim", label: "Fim", type: "date", required: true },
        {
          key: "limite_usos",
          label: "Limite de utilizações (vazio = sem limite)",
          type: "number",
          nullable: true,
          min: 1,
        },
      ]
    : [
        { key: "nome", label: "Nome", required: true },
        { key: "documento", label: "CPF / CNPJ" },
        { key: "email", label: "E-mail", type: "email" },
        { key: "telefone", label: "Telefone" },
        { key: "observacoes", label: "Observações", type: "multiline" },
      ];
  return (
    <Screen
      back
      title={coupon ? "Cupons de desconto" : "Fornecedores"}
      subtitle={
        coupon
          ? "Validade e limites exclusivos da sua loja."
          : "Contatos e fornecedores dos seus produtos."
      }
      onRefresh={state.reload}
      refreshing={state.loading}
    >
      <Button
        title={coupon ? "Adicionar cupom" : "Adicionar fornecedor"}
        onPress={() =>
          setEditor(
            coupon
              ? {
                  codigo: "",
                  tipo: "percentual",
                  valor: "",
                  inicio: monthPeriod().inicio,
                  fim: monthPeriod().fim,
                  limite_usos: "",
                  ativo: true,
                }
              : {
                  nome: "",
                  documento: "",
                  email: "",
                  telefone: "",
                  observacoes: "",
                  ativo: true,
                },
          )
        }
      />
      <Feedback state={mut} />
      {coupon && (
        <Copy muted>
          Um cupom por pedido da loja, aplicado aos produtos após promoções.
          Frete não recebe desconto. Pedidos aguardando pagamento também
          reservam utilização.
        </Copy>
      )}
      {editor && (
        <Card>
          <Heading>
            {editor[idKey] ? "Editar cadastro" : "Novo cadastro"}
          </Heading>
          <Form
            key={editor[idKey] ?? "new"}
            fields={fields}
            initial={{
              ...editor,
              inicio: editor.inicio?.slice(0, 10) ?? "",
              fim: editor.fim?.slice(0, 10) ?? "",
            }}
            title="Salvar"
            busy={mut.busy}
            onSubmit={(body) =>
              mut.run(
                () =>
                  api(
                    `${base}/${type}${editor[idKey] ? `/${editor[idKey]}` : ""}`,
                    { method: editor[idKey] ? "PUT" : "POST", body },
                  ),
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
      <Resource state={state} empty={!!state.data && !state.data[type]?.length}>
        {(state.data?.[type] ?? []).map((r: any) => (
          <Card key={r[idKey]}>
            <Badge>{r.ativo ? "Ativo" : "Inativo"}</Badge>
            <Heading>{r.nome || r.codigo}</Heading>
            {coupon ? (
              <>
                <Copy>
                  {r.tipo === "percentual" ? `${r.valor}%` : money(r.valor)} de
                  desconto
                </Copy>
                <Copy muted>
                  {r.inicio?.slice(0, 10)} a {r.fim?.slice(0, 10)} ·{" "}
                  {r.usos ?? r.usos_realizados ?? 0}/
                  {r.limite_usos ?? "sem limite"} usos
                </Copy>
              </>
            ) : (
              <>
                <Copy>
                  {r.telefone} · {r.email}
                </Copy>
                <Copy muted>{r.observacoes}</Copy>
              </>
            )}
            <Button
              title="Editar"
              variant="secondary"
              onPress={() => setEditor(r)}
            />
            <Button
              title={r.ativo ? "Desativar" : "Ativar"}
              variant="ghost"
              disabled={mut.busy}
              onPress={() => {
                void mut.run(
                  () =>
                    api(`${base}/${type}/${r[idKey]}/ativo`, {
                      method: "PATCH",
                      body: { ativo: !r.ativo },
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
export function OwnerSales() {
  const [period, setPeriod] = useState(monthPeriod());
  const state = useResource<any>(
    query(`${base}/relatorios`, { ...period, agrupamento: "dia" }),
    null,
  );
  const k = state.data?.indicadores;
  return (
    <Screen
      back
      title="Vendas da loja"
      subtitle="Faturamento e produtos mais vendidos."
      onRefresh={state.reload}
      refreshing={state.loading}
    >
      <Period onApply={setPeriod} />
      <Copy muted>
        Pedidos criados no período. Faturamento usa somente pedidos pagos, com
        descontos. Custos e lucro são estimativas sem despesas e taxas.
      </Copy>
      <Resource state={state}>
        {k && (
          <>
            <View style={s.row}>
              {[
                ["Faturamento", money(k.faturamento)],
                ["Pedidos criados", k.quantidade_pedidos],
                ["Pedidos pagos", k.quantidade_pagos],
                ["Ticket médio", money(k.ticket_medio)],
                ["Frete recebido", money(k.frete)],
                ["Descontos", money(k.descontos)],
                [
                  "Custo dos produtos",
                  `${money(k.custo_produtos)}${k.custos_incompletos ? " (parcial)" : ""}`,
                ],
                ["Lucro bruto", money(k.lucro_bruto)],
              ].map(([label, value]) => (
                <Stat key={String(label)} label={String(label)} value={value} />
              ))}
            </View>
            <Collection
              title="Vendas por dia"
              rows={state.data.periodos ?? []}
              fields={[
                ["periodo", "Período"],
                ["quantidade_pagos", "Pedidos pagos"],
                ["faturamento", "Faturamento", money],
                ["ticket_medio", "Ticket médio", money],
              ]}
            />
            <Collection
              title="Produtos vendidos"
              rows={state.data.produtos ?? []}
              fields={[
                ["nome", "Produto"],
                ["quantidade", "Unidades"],
                ["faturamento", "Faturamento", money],
                ["custo_produtos", "Custo", money],
                ["lucro_bruto", "Lucro bruto", money],
              ]}
            />
          </>
        )}
      </Resource>
    </Screen>
  );
}
export function OwnerDelivery() {
  const state = useResource<any>(`${base}/remetente`, null);
  const mut = useMutation();
  const fields: Field[] = [
    ["nome", "Nome / razão social"],
    ["email", "E-mail"],
    ["telefone", "Telefone"],
    ["documento", "CPF / CNPJ"],
    ["inscricao_estadual", "Inscrição estadual"],
    ["cep", "CEP"],
    ["logradouro", "Rua"],
    ["numero", "Número"],
    ["complemento", "Complemento"],
    ["bairro", "Bairro"],
    ["cidade", "Cidade"],
    ["uf", "UF (sigla)"],
  ].map(([key, label]) => ({
    key,
    label,
    required: !["complemento", "inscricao_estadual"].includes(key),
  }));
  return (
    <Screen
      back
      title="Dados das entregas"
      subtitle="Remetente e endereço de origem da sua loja."
    >
      <Feedback state={mut} />
      <Resource state={state}>
        {state.data && (
          <Card>
            <Badge>
              {state.data.integracao?.configurada
                ? "Melhor Envio conectado"
                : "Integração não configurada"}
            </Badge>
            <Copy muted>
              O frete é pago pelo cliente. Compra de etiquetas depende de
              autorização e saldo na conta do Melhor Envio.
            </Copy>
            <Form
              fields={fields}
              initial={state.data.remetente ?? {}}
              busy={mut.busy}
              title="Salvar remetente"
              onSubmit={(body) =>
                mut.run(
                  () => api(`${base}/remetente`, { method: "PUT", body }),
                  state.reload,
                )
              }
            />
          </Card>
        )}
      </Resource>
    </Screen>
  );
}
