import React, { useState } from "react";
import { canRequestBookingCharge } from "./clientRules";
import { Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import QRCode from "react-native-qrcode-svg";
import { api } from "../../lib/api";
import CardArkhe, { CardReceipt } from "./CardArkhe";
import {
  CARTAO_INCERTO,
  dadosCartao,
  cartaoEmConferencia,
  erroCartaoIncerto,
  reciboCartao,
} from "./cardRules";
import { useResource } from "../../lib/useResource";
import { Button, Card, Notice } from "../../ui";
import {
  Feedback,
  Heading,
  Label,
  Resource,
  ask,
  money,
  s,
  useAction,
} from "./common";
export function PixCode({ code, amount }) {
  const action = useAction();
  return (
    <Card>
      <Heading>
        {code.startsWith("ARKHEPIX:")
          ? "Pagamento interno Arkhé"
          : "Código de pagamento"}
      </Heading>
      {code.startsWith("ARKHEPIX:") && (
        <Notice
          kind="info"
          message="Este é um código interno da Arkhé. Não é um Pix bancário padrão; use o ambiente da Arkhé para pagar."
        />
      )}
      <View
        style={{
          alignSelf: "center",
          padding: 16,
          backgroundColor: "#fff",
          borderRadius: 18,
        }}
      >
        <QRCode value={code} size={190} />
      </View>
      <Text selectable style={s.muted}>
        {code}
      </Text>
      {amount != null && <Label>{money(amount)}</Label>}
      <Feedback state={action} />
      <Button
        title="Copiar código"
        variant="secondary"
        onPress={() =>
          action.run(async () => {
            await Clipboard.setStringAsync(code);
          }, "Código copiado.")
        }
      />
    </Card>
  );
}
export default function BookingPayment(props) {
  return (
    <BookingPaymentCurrent
      key={String(props.booking.id_agendamento)}
      {...props}
    />
  );
}
function BookingPaymentCurrent({ booking }) {
  const id = booking.id_agendamento;
  const state = useResource(`/pagamentos/agendamento/${id}`, {});
  const action = useAction();
  const [payment, setPayment] = useState(null);
  const [uncertain, setUncertain] = useState(false);
  const d = state.data;
  const existing = d.cobrancas || [];
  const codigoPagamento = String(
    payment?.codigo_pagamento || payment?.codigo_pix || "",
  ).trim();
  const canCreate =
    !state.loading &&
    !state.error &&
    !uncertain &&
    !cartaoEmConferencia(d) &&
    !reciboCartao(payment) &&
    canRequestBookingCharge(d, booking.status);
  async function refresh() {
    const fresh = await api(`/pagamentos/agendamento/${id}`);
    state.setData?.(fresh);
    if (
      ["aprovado", "recusado"].includes(fresh.cartao_estado) ||
      fresh.cobrancas?.length ||
      fresh.quitado
    )
      setUncertain(false);
    await state.reload();
    return fresh;
  }
  async function request(method, fields) {
    const fresh = await api(`/pagamentos/agendamento/${id}`);
    if (
      uncertain ||
      cartaoEmConferencia(fresh) ||
      !canRequestBookingCharge(fresh, booking.status)
    )
      throw new Error(
        "Já existe pagamento ou cobrança. Atualize e consulte a cobrança existente.",
      );
    if (
      method === "cartao" &&
      Math.abs(Number(fresh.saldo) - Number(d.saldo)) > 0.005
    ) {
      state.setData?.(fresh);
      throw new Error(
        "O valor mudou. Confira o novo total antes de confirmar.",
      );
    }
    let posted = false;
    try {
      posted = true;
      const response = await api(`/pagamentos/${method}`, {
        method: "POST",
        body: {
          id_agendamento: id,
          ...(method === "cartao" ? dadosCartao(fields, fresh.saldo) : {}),
        },
      });
      setPayment(response);
      if (method === "cartao" && !reciboCartao(response)) {
        setUncertain(true);
        throw new Error(CARTAO_INCERTO);
      }
    } catch (error) {
      if (erroCartaoIncerto(error)) {
        setUncertain(true);
        throw new Error(CARTAO_INCERTO);
      }
      throw error;
    } finally {
      if (posted) await state.reload();
    }
  }
  async function consult(item) {
    const code = String(item.descricao).match(/^ARKHE:([^ ]+)/)?.[1];
    if (!code) return;
    // Restore only the provider's existing code, kept in component memory.
    const result = await api(`/pagamentos/pix/${encodeURIComponent(code)}`);
    setPayment(result);
    await state.reload();
  }
  return (
    <>
      <Card>
        <Heading>Pagamento do atendimento</Heading>
        <Resource state={state}>
          <Label>
            {d.quitado
              ? "Quitado"
              : d.parcial
                ? "Pagamento parcial"
                : "Pendente"}{" "}
            · recebido {money(d.valor_recebido)} · saldo {money(d.saldo)}
          </Label>
          {existing.map((item) => (
            <View key={item.id_financeiro}>
              <Label>
                {item.confirmado ? "Recebido" : "Pendente"} ·{" "}
                {money(item.valor)}
              </Label>
              {/^ARKHE:([^ ]+)/.test(item.descricao || "") && (
                <Button
                  title="Consultar cobrança existente"
                  variant="secondary"
                  loading={action.busy}
                  onPress={() =>
                    action.run(
                      () => consult(item),
                      "Consulta concluída. Confira o status atualizado.",
                    )
                  }
                />
              )}
            </View>
          ))}
          <CardReceipt receipt={reciboCartao(d) || reciboCartao(payment)} />
          {(uncertain || cartaoEmConferencia(d)) && (
            <Notice kind="info" message={CARTAO_INCERTO} />
          )}
          {canCreate && (
            <>
              <CardArkhe
                total={d.saldo}
                disabled={action.busy}
                onSubmit={(fields) =>
                  action.run(() => request("cartao", fields))
                }
              />
              <Button
                title="Gerar cobrança Pix"
                loading={action.busy}
                onPress={() =>
                  ask(
                    "Gerar cobrança?",
                    `Será criada uma cobrança de ${money(d.saldo)}. Pague somente após conferir o recebedor.`,
                    () => action.run(() => request("pix")),
                  )
                }
              />
              <Button
                title="Pagar no estabelecimento"
                variant="secondary"
                loading={action.busy}
                onPress={() =>
                  ask(
                    "Pagar no estabelecimento?",
                    "O pagamento ficará pendente até o estabelecimento confirmar o recebimento.",
                    () => action.run(() => request("na-hora")),
                  )
                }
              />
            </>
          )}
          {d.parcial && (
            <Notice
              kind="info"
              message="O saldo restante deve ser tratado com o estabelecimento. Nenhuma nova cobrança integral será criada aqui."
            />
          )}
          <Button
            title="Atualizar status"
            variant="ghost"
            loading={action.busy}
            onPress={() => action.run(refresh)}
          />
        </Resource>
        <Feedback state={action} />
      </Card>
      {!!codigoPagamento && (
        <PixCode code={codigoPagamento} amount={payment?.valor} />
      )}
    </>
  );
}
