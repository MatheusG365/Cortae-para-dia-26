import React, { useState } from "react";
import { Linking } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { api, query } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, Notice, Screen, Select } from "../../ui";
import {
  Badge,
  Copy,
  Feedback,
  Form,
  Heading,
  Resource,
  confirmAction,
  dateTime,
  go,
  money,
  useMutation,
} from "./shared";
const base = "/gestao/marketplace";
const labels: Record<string, string> = {
  aguardando_pagamento: "Aguardando pagamento",
  pago: "Pago",
  separando: "Em preparação",
  pronto_retirada: "Pronto para retirada",
  enviado: "Enviado",
  entregue: "Entregue",
  cancelado: "Cancelado",
  expirado: "Expirado",
  reembolsado: "Reembolsado",
};
export function OwnerOrders() {
  const [status, setStatus] = useState("");
  const [filter, setFilter] = useState("");
  const state = useResource<any>(
    query(`${base}/pedidos`, { status, busca: filter }),
    null,
  );
  return (
    <Screen
      back
      title="Pedidos e entregas"
      subtitle="Acompanhe cada compra da sua loja."
      onRefresh={state.reload}
      refreshing={state.loading}
    >
      <Card>
        <Form
          fields={[
            { key: "busca", label: "Nome do cliente ou número do pedido" },
          ]}
          initial={{ busca: "" }}
          title="Buscar pedidos"
          onSubmit={(v) => setFilter(v.busca)}
        />
        <Select
          label="Situação"
          value={status}
          onChange={setStatus}
          options={[
            { label: "Todos", value: "" },
            ...Object.entries(labels).map(([value, label]) => ({
              value,
              label,
            })),
          ]}
        />
      </Card>
      <Resource
        state={state}
        empty={!!state.data && !state.data.pedidos?.length}
      >
        {(state.data?.pedidos ?? []).map((p: any) => (
          <Card key={p.id_pedido}>
            <Badge>{labels[p.status] ?? p.status}</Badge>
            <Heading>
              #{p.id_pedido} · {p.cliente}
            </Heading>
            <Copy>
              {money(p.total)} · {p.retirada ? "Retirada na loja" : "Entrega"}
            </Copy>
            <Copy muted>{dateTime(p.criado_em)}</Copy>
            <Button
              title="Gerenciar pedido"
              variant="secondary"
              onPress={() => go(`/barbearia/pedido?id=${p.id_pedido}`)}
            />
          </Card>
        ))}
      </Resource>
    </Screen>
  );
}
export function OwnerOrder() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const state = useResource<any>(id ? `${base}/pedidos/${id}` : null, null);
  const mut = useMutation();
  const p = state.data?.pedido;
  const act = (suffix: string, body: any) =>
    mut.run(
      () =>
        api(`${base}/pedidos/${id}${suffix}`, {
          method: suffix === "/status" ? "PATCH" : "POST",
          body,
        }),
      state.reload,
    );
  return (
    <Screen
      back
      title={`Pedido #${id}`}
      subtitle="Compra, preparação e acompanhamento."
      onRefresh={state.reload}
      refreshing={state.loading}
    >
      <Feedback state={mut} />
      <Resource state={state}>
        {p && (
          <>
            <Card>
              <Badge>{labels[p.status] ?? p.status}</Badge>
              <Heading>{p.cliente || p.endereco?.nome}</Heading>
              <Copy>
                {p.endereco?.email} · {p.endereco?.telefone}
              </Copy>
              <Copy muted>
                {dateTime(p.criado_em)} · {p.retirada ? "Retirada" : "Entrega"}
              </Copy>
              {(p.itens ?? []).map((v: any) => (
                <Copy key={`${v.id_produto}:${v.id_variacao ?? "base"}`}>
                  {v.quantidade} × {v.nome}
                  {v.variacao
                    ? ` · ${typeof v.variacao === "string" ? v.variacao : v.variacao.nome}`
                    : ""}{" "}
                  · {money(v.total)}
                </Copy>
              ))}
              <Copy>
                Produtos: {money(p.subtotal)} · Frete: {money(p.frete)}
              </Copy>
              <Heading>Total: {money(p.total)}</Heading>
              {p.status === "pago" && (
                <Button
                  title="Iniciar preparação"
                  loading={mut.busy}
                  onPress={() => {
                    void act("/status", { status: "separando" });
                  }}
                />
              )}
              {p.retirada && p.status === "separando" && (
                <Button
                  title="Pronto para retirada"
                  loading={mut.busy}
                  onPress={() => {
                    void act("/status", { status: "pronto_retirada" });
                  }}
                />
              )}
              {p.retirada && p.status === "pronto_retirada" && (
                <Button
                  title="Confirmar retirada pelo cliente"
                  loading={mut.busy}
                  onPress={() =>
                    confirmAction(
                      "Confirmar retirada?",
                      "Confirme somente após entregar os produtos ao cliente.",
                      () => {
                        void act("/status", { status: "entregue" });
                      },
                    )
                  }
                />
              )}
            </Card>
            {!p.retirada && (
              <Card>
                <Heading>Entrega</Heading>
                <Copy>
                  {p.endereco?.logradouro}, {p.endereco?.numero} ·{" "}
                  {p.endereco?.bairro}
                </Copy>
                <Copy>
                  {p.endereco?.cidade}/{p.endereco?.uf} · {p.endereco?.cep}
                </Copy>
                <Copy>
                  Situação: {p.entrega?.status || "Envio não vinculado"}
                </Copy>
                {p.entrega?.rastreio && (
                  <Copy>Código de rastreio: {p.entrega.rastreio}</Copy>
                )}
                {p.entrega?.id_envio ? (
                  <Button
                    title="Atualizar rastreio"
                    variant="secondary"
                    loading={mut.busy}
                    onPress={() => {
                      void act("/rastreio", {});
                    }}
                  />
                ) : (
                  p.pagamento_status === "pago" &&
                  !["cancelado", "entregue"].includes(p.status) && (
                    <>
                      <Notice message="Emita o envio no Melhor Envio e vincule o ID correspondente. Confira remetente, destinatário e itens antes de confirmar." />
                      <Button
                        title="Abrir Melhor Envio"
                        variant="secondary"
                        onPress={() => {
                          void Linking.openURL("https://melhorenvio.com.br/");
                        }}
                      />
                      <Form
                        fields={[
                          {
                            key: "id_envio",
                            label: "ID do envio (UUID)",
                            required: true,
                          },
                        ]}
                        initial={{ id_envio: "" }}
                        title="Conferi os dados: vincular envio"
                        busy={mut.busy}
                        onSubmit={(v) => {
                          confirmAction(
                            "Vincular este envio?",
                            "Declaro que este envio do Melhor Envio corresponde ao pedido e aos dados do cliente.",
                            () => {
                              void act("/vincular-envio", {
                                id_envio: v.id_envio.trim(),
                                confirmar_vinculo: true,
                              });
                            },
                          );
                        }}
                      />
                    </>
                  )
                )}
                {/^https:\/\//.test(p.entrega?.url_etiqueta ?? "") && (
                  <Button
                    title="Abrir etiqueta existente"
                    variant="secondary"
                    onPress={() => {
                      void Linking.openURL(p.entrega.url_etiqueta);
                    }}
                  />
                )}
              </Card>
            )}
          </>
        )}
      </Resource>
    </Screen>
  );
}
