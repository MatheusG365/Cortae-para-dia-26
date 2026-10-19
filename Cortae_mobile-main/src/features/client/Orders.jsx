import React, { useState } from "react";
import { canCreateOrderPix } from "./clientRules";
import { useLocalSearchParams } from "expo-router";
import { api, assetUrl } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, Notice, RemoteImage, Screen } from "../../ui";
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
import CardArkhe, { CardReceipt } from "./CardArkhe";
import {
  CARTAO_INCERTO,
  dadosCartao,
  cartaoEmConferencia,
  erroCartaoIncerto,
  podePagarPedido,
  reciboCartao,
} from "./cardRules";
export default function Orders() {
  const { id } = useLocalSearchParams();
  const state = useResource(
    id ? `/marketplace/pedidos/${id}` : "/marketplace/pedidos",
    {},
  );
  const action = useAction();
  const [payment, setPayment] = useState(null);
  const [uncertain, setUncertain] = useState(null);
  const p = state.data.pedido;
  const pix = payment?.id === String(id) ? payment.value : p?.pagamento;
  const blocked = uncertain === String(id) || cartaoEmConferencia(p);
  const receipt = reciboCartao(pix);
  const canPix = !blocked && !receipt && canCreateOrderPix(p);
  async function refresh() {
    const fresh = await api(`/marketplace/pedidos/${id}`);
    state.setData(fresh);
    if (
      ["aprovado", "recusado"].includes(
        fresh.pedido?.pagamento?.cartao_estado,
      ) ||
      fresh.pedido?.pagamento_status === "pago"
    )
      setUncertain(null);
    return fresh.pedido;
  }
  async function act(kind) {
    if (
      kind === "pagamento" &&
      (p?.pagamento?.metodo === "cartao" || blocked)
    ) {
      await refresh();
      return;
    }
    if (kind === "pix") {
      const fresh = await api(`/marketplace/pedidos/${id}`);
      if (blocked || !podePagarPedido(fresh.pedido))
        throw new Error("Já existe pagamento ou cobrança. Atualize o pedido.");
    }
    try {
      const d = await api(
        `/marketplace/pedidos/${id}/${kind}`,
        kind === "pagamento" ? {} : { method: "POST", body: {} },
      );
      if (d.pagamento) setPayment({ id: String(id), value: d.pagamento });
    } catch (error) {
      if (kind === "pix" && erroCartaoIncerto(error)) setUncertain(String(id));
      throw error;
    } finally {
      await state.reload();
    }
  }
  async function payCard(fields) {
    const fresh = await api(`/marketplace/pedidos/${id}`);
    if (blocked || !podePagarPedido(fresh.pedido))
      throw new Error("Já existe pagamento ou cobrança. Atualize o pedido.");
    if (Math.abs(Number(fresh.pedido.total) - Number(p.total)) > 0.005) {
      state.setData(fresh);
      throw new Error(
        "O valor mudou. Confira o novo total antes de confirmar.",
      );
    }
    try {
      const response = await api(`/marketplace/pedidos/${id}/cartao`, {
        method: "POST",
        body: dadosCartao(fields, fresh.pedido.total),
      });
      setPayment({ id: String(id), value: response.pagamento });
      if (!reciboCartao(response)) {
        setUncertain(String(id));
        throw new Error(CARTAO_INCERTO);
      }
    } catch (error) {
      if (erroCartaoIncerto(error)) {
        setUncertain(String(id));
        throw new Error(CARTAO_INCERTO);
      }
      throw error;
    } finally {
      await state.reload();
    }
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
              <CardReceipt receipt={receipt} />
              {blocked && <Notice kind="info" message={CARTAO_INCERTO} />}
              {!blocked && !receipt && podePagarPedido(p) && (
                <CardArkhe
                  key={String(id)}
                  total={p.total}
                  disabled={action.busy}
                  onSubmit={(fields) => action.run(() => payCard(fields))}
                />
              )}
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
            {pix?.metodo !== "cartao" && pix?.codigo_pix && (
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
                loading={action.busy}
                onPress={() => action.run(refresh)}
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
