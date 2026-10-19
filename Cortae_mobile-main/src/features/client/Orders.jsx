import React, { useState } from "react";
import { canCreateOrderPix } from "./clientRules";
import { useLocalSearchParams } from "expo-router";
import { api, assetUrl } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, RemoteImage, Screen } from "../../ui";
import {
  Feedback,
  Heading,
  Label,
  Resource,
  Summary,
  ask,
  dateTime,
  go,
  money,
  s,
  useAction,
} from "./common";
import { PixCode } from "./Payment";
export default function Orders() {
  const { id } = useLocalSearchParams();
  const state = useResource(
    id ? `/marketplace/pedidos/${id}` : "/marketplace/pedidos",
    {},
  );
  const action = useAction();
  const [payment, setPayment] = useState(null);
  const p = state.data.pedido;
  const pix = payment || p?.pagamento;
  const canPix = canCreateOrderPix(p);
  async function act(kind) {
    const d = await api(
      `/marketplace/pedidos/${id}/${kind}`,
      kind === "pagamento" ? {} : { method: "POST", body: {} },
    );
    if (d.pagamento) setPayment(d.pagamento);
    await state.reload();
  }
  return (
    <Screen
      title={id ? `Pedido #${id}` : "Minhas compras"}
      subtitle="Acompanhe seus produtos, pagamentos e entregas"
      back
      refreshing={state.loading}
      onRefresh={state.reload}
    >
      <Feedback state={action} />
      <Resource state={state} empty={!id && !state.data.pedidos?.length}>
        {p ? (
          <>
            <Card>
              <Label muted>{p.status}</Label>
              <Heading>{p.barbearia}</Heading>
              <Label>{dateTime(p.criado_em)}</Label>
              <Heading>{money(p.total)}</Heading>
              {(p.itens || []).map((item) => (
                <Card key={`${item.id_produto}:${item.id_variacao || "base"}`}>
                  <RemoteImage
                    uri={assetUrl(item.imagem)}
                    style={s.productImage}
                  />
                  <Heading>{item.nome}</Heading>
                  <Label>
                    {item.variacao?.nome} · {item.quantidade} ×{" "}
                    {money(item.preco)}
                  </Label>
                  <Button
                    title={
                      p.status === "entregue"
                        ? "Ver produto e avaliar"
                        : "Ver produto"
                    }
                    variant="ghost"
                    onPress={() => go(`/cliente/produto/${item.id_produto}`)}
                  />
                </Card>
              ))}
            </Card>
            <Summary resumo={p.resumo} />
            <Card>
              <Heading>Pagamento</Heading>
              <Label>Status: {p.pagamento_status || "Não iniciado"}</Label>
              {canPix && (
                <Button
                  title="Gerar cobrança Pix"
                  loading={action.busy}
                  onPress={() =>
                    ask(
                      "Gerar cobrança?",
                      `Será solicitada uma cobrança de ${money(p.total)} para este pedido. Confira o recebedor antes de pagar.`,
                      () => action.run(() => act("pix")),
                    )
                  }
                />
              )}
              {p.status === "aguardando_pagamento" && (
                <Button
                  title="Consultar pagamento"
                  variant="secondary"
                  loading={action.busy}
                  onPress={() =>
                    action.run(
                      () => act("pagamento"),
                      "Consulta concluída. Confira o status do pedido.",
                    )
                  }
                />
              )}
            </Card>
            {pix?.codigo_pix && (
              <PixCode code={pix.codigo_pix} amount={pix.valor} />
            )}
            <Card>
              <Heading>
                {p.retirada ? "Retirada na barbearia" : "Sua entrega"}
              </Heading>
              {p.retirada ? (
                <Label>Acompanhe o status para saber quando retirar.</Label>
              ) : (
                <>
                  <Label>
                    {p.endereco?.logradouro}, {p.endereco?.numero} ·{" "}
                    {p.endereco?.complemento}
                  </Label>
                  <Label>
                    {p.endereco?.bairro} · {p.endereco?.cidade}/{p.endereco?.uf}
                  </Label>
                  <Label>CEP {p.endereco?.cep}</Label>
                  <Label>
                    {p.entrega?.rastreio
                      ? `Rastreio: ${p.entrega.rastreio}`
                      : "A transportadora ainda não informou o rastreamento."}
                  </Label>
                </>
              )}
              <Button
                title="Atualizar acompanhamento"
                variant="secondary"
                onPress={state.reload}
              />
            </Card>
            {p.pode_cancelar && (
              <Button
                title="Cancelar pedido"
                variant="danger"
                loading={action.busy}
                onPress={() =>
                  ask(
                    "Cancelar pedido?",
                    "Os produtos reservados retornarão ao estoque. O cancelamento é permitido apenas nas condições informadas pelo sistema.",
                    () =>
                      action.run(() => act("cancelar"), "Pedido cancelado."),
                  )
                }
              />
            )}
          </>
        ) : (
          (state.data.pedidos || []).map((order) => (
            <Card key={order.id_pedido}>
              <Label muted>{order.status}</Label>
              <Heading>
                Pedido #{order.id_pedido} · {order.barbearia}
              </Heading>
              <Label>
                {dateTime(order.criado_em)} ·{" "}
                {order.retirada ? "Retirada" : "Entrega"}
              </Label>
              <Heading>{money(order.total)}</Heading>
              <Button
                title="Acompanhar pedido"
                variant="secondary"
                onPress={() => go(`/cliente/pedidos/${order.id_pedido}`)}
              />
            </Card>
          ))
        )}
      </Resource>
    </Screen>
  );
}
