import React, { useState } from "react";
import { View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { api, assetUrl } from "../../lib/api";
import { useSession } from "../../lib/session";
import { useResource } from "../../lib/useResource";
import { Button, Card, Input, RemoteImage, Screen, Select } from "../../ui";
import {
  Data,
  Feedback,
  Heading,
  Label,
  Resource,
  Summary,
  TermsConsent,
  acceptTerms,
  ask,
  go,
  money,
  s,
  useAction,
} from "./common";
export default function Cart() {
  const state = useResource<Data>("/marketplace/carrinho", {});
  const action = useAction();
  const groups = state.data.grupos || [];
  async function amount(item: Data, n: number) {
    await action.run(async () => {
      await api(`/marketplace/carrinho/${item.id_produto}`, {
        method: "PUT",
        body: { quantidade: n, id_variacao: item.id_variacao ?? null },
      });
      await state.reload();
    });
  }
  return (
    <Screen
      title="Sua sacola de cuidados"
      subtitle="Cada barbearia recebe um pedido separado"
      back
      refreshing={state.loading}
      onRefresh={state.reload}
    >
      <Feedback state={action} />
      <Resource state={state} empty={!state.data.itens?.length}>
        {groups.map((g: Data) => (
          <Card key={g.id_barbearia}>
            <Heading>{g.barbearia}</Heading>
            {g.itens.map((i: Data) => (
              <View
                key={`${i.id_produto}:${i.id_variacao || "base"}`}
                style={{
                  gap: 10,
                  borderBottomColor: "#303030",
                  borderBottomWidth: 1,
                  paddingVertical: 12,
                }}
              >
                <View style={s.row}>
                  <RemoteImage
                    uri={assetUrl(i.imagem)}
                    style={{ width: 70, height: 70, borderRadius: 14 }}
                  />
                  <View style={{ flex: 1 }}>
                    <Label>{i.nome}</Label>
                    <Label muted>
                      {i.variacao?.nome} · {money(i.preco)} por unidade
                    </Label>
                    <Label>
                      {money(Number(i.preco) * Number(i.quantidade))}
                    </Label>
                  </View>
                </View>
                {i.disponivel === false && (
                  <Label muted>Indisponível. Remova para continuar.</Label>
                )}
                <View style={s.wrap}>
                  <Button
                    title="−"
                    variant="secondary"
                    disabled={action.busy || i.quantidade <= 1}
                    onPress={() => amount(i, i.quantidade - 1)}
                  />
                  <Label>{i.quantidade}</Label>
                  <Button
                    title="+"
                    variant="secondary"
                    disabled={action.busy || i.quantidade >= i.estoque}
                    onPress={() => amount(i, i.quantidade + 1)}
                  />
                  <Button
                    title="Remover"
                    variant="ghost"
                    disabled={action.busy}
                    onPress={() =>
                      ask(
                        "Remover produto?",
                        "Este item sairá do seu carrinho.",
                        () => {
                          void amount(i, 0);
                        },
                      )
                    }
                  />
                </View>
              </View>
            ))}
            <Heading>Subtotal {money(g.subtotal)}</Heading>
            <Button
              title="Finalizar compra nesta loja"
              disabled={
                action.busy ||
                g.itens.some(
                  (v: Data) =>
                    v.disponivel === false || v.quantidade > v.estoque,
                )
              }
              onPress={() =>
                go("/cliente/checkout", { barbearia: String(g.id_barbearia) })
              }
            />
          </Card>
        ))}
      </Resource>
      <Button
        title="Continuar explorando"
        variant="secondary"
        onPress={() => go("/cliente/loja")}
      />
    </Screen>
  );
}
const fields = [
  ["nome", "Nome completo"],
  ["email", "E-mail"],
  ["telefone", "Telefone com DDD"],
  ["documento", "CPF ou CNPJ"],
  ["cep", "CEP"],
  ["logradouro", "Rua / avenida"],
  ["numero", "Número"],
  ["complemento", "Complemento (opcional)"],
  ["bairro", "Bairro"],
  ["cidade", "Cidade"],
] as const;
export function Checkout() {
  const { barbearia } = useLocalSearchParams<{ barbearia: string }>();
  const { user } = useSession();
  const action = useAction();
  const [key] = useState(
    () => `mobile-${Date.now()}-${Math.random().toString(36).slice(2)}`,
  );
  const [form, setForm] = useState<Data>({
      nome: user?.nome || "",
      email: user?.email || "",
      telefone: user?.telefone || "",
      documento: "",
      cep: "",
      logradouro: "",
      numero: "",
      complemento: "",
      bairro: "",
      cidade: "",
      uf: "",
    }),
    [pickup, setPickup] = useState(true),
    [quotes, setQuotes] = useState<Data[]>([]),
    [quote, setQuote] = useState(""),
    [coupon, setCoupon] = useState(""),
    [appliedCoupon, setAppliedCoupon] = useState(""),
    [summary, setSummary] = useState<Data | null>(null),
    [checked, setChecked] = useState(false);
  function change(key: string, value: string) {
    setForm((v) => ({ ...v, [key]: value }));
    setSummary(null);
    if (key === "cep") {
      setQuote("");
      setQuotes([]);
    }
  }
  const body = {
    id_barbearia: Number(barbearia),
    cupom: appliedCoupon,
    retirada: pickup,
    id_cotacao: pickup ? null : quote,
    endereco: form,
  };
  async function shipping() {
    setSummary(null);
    const d = await api<Data>("/marketplace/frete", {
      method: "POST",
      body: { id_barbearia: Number(barbearia), cep: form.cep },
    });
    setQuotes(d.cotacoes || []);
    setQuote("");
    if (!d.cotacoes?.length)
      throw new Error(
        "Nenhuma entrega disponível para o CEP. Escolha retirada ou outro endereço.",
      );
  }
  async function preview(code = appliedCoupon) {
    setSummary(null);
    const d = await api<Data>("/marketplace/pedidos/resumo", {
      method: "POST",
      body: { ...body, cupom: code },
    });
    setAppliedCoupon(code);
    setSummary(d.resumo);
  }
  async function order() {
    if (!summary?.confirmacao_resumo)
      throw new Error("Confira o resumo atualizado antes de continuar.");
    await acceptTerms(checked, summary.termos_versao);
    try {
      const d = await api<Data>("/marketplace/pedidos", {
        method: "POST",
        body: {
          ...body,
          confirmacao_resumo: summary.confirmacao_resumo,
          chave_idempotencia: key,
        },
      });
      go(`/cliente/pedidos/${d.pedido.id_pedido}`);
    } catch (e) {
      setSummary(null);
      throw e;
    }
  }
  return (
    <Screen
      title="Como você quer receber?"
      subtitle="Confira seus dados, o frete e os valores antes de criar o pedido"
      back
    >
      <Feedback state={action} />
      <Card>
        <Select
          label="Forma de entrega"
          value={pickup ? "retirada" : "entrega"}
          onChange={(v: string) => {
            setPickup(v === "retirada");
            setSummary(null);
          }}
          options={[
            { label: "Retirar na barbearia · grátis", value: "retirada" },
            { label: "Receber no meu endereço", value: "entrega" },
          ]}
        />
        <Heading>Dados do destinatário</Heading>
        {fields.map(([name, label]) => (
          <Input
            key={name}
            label={label}
            value={form[name]}
            onChangeText={(v: string) => change(name, v)}
            keyboardType={
              ["cep", "telefone", "documento", "numero"].includes(name)
                ? "phone-pad"
                : name === "email"
                  ? "email-address"
                  : "default"
            }
            autoCapitalize={name === "email" ? "none" : "sentences"}
            maxLength={name === "cep" ? 9 : 160}
          />
        ))}
        <Select
          label="Estado"
          value={form.uf}
          onChange={(v: string) => change("uf", v)}
          options={[
            { label: "Selecione a UF", value: "" },
            ..."AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO"
              .split(" ")
              .map((v) => ({ label: v, value: v })),
          ]}
        />
        {!pickup && (
          <>
            <Button
              title="Calcular frete"
              disabled={String(form.cep).replace(/\D/g, "").length !== 8}
              loading={action.busy}
              onPress={() => action.run(shipping)}
            />
            <Select
              label="Opção de entrega"
              value={quote}
              onChange={(v: string) => {
                setQuote(v);
                setSummary(null);
              }}
              options={[
                { label: "Selecione a entrega", value: "" },
                ...quotes.map((v) => ({
                  label: `${v.transportadora} · ${v.servico} · ${money(v.preco)} · até ${v.prazo_dias} dias úteis`,
                  value: v.id_cotacao,
                })),
              ]}
            />
          </>
        )}
      </Card>
      <Card>
        <Heading>Tem um cupom desta loja?</Heading>
        <Input
          label="Código do cupom"
          value={coupon}
          onChangeText={setCoupon}
          autoCapitalize="characters"
          placeholder="Digite seu cupom"
        />
        <View style={s.wrap}>
          <Button
            title="Aplicar cupom e conferir"
            disabled={!pickup && !quote}
            loading={action.busy}
            onPress={() =>
              action.run(() => preview(coupon.trim().toUpperCase()))
            }
          />
          {appliedCoupon && (
            <Button
              title="Remover cupom"
              variant="ghost"
              loading={action.busy}
              onPress={() => {
                setCoupon("");
                void action.run(() => preview(""));
              }}
            />
          )}
        </View>
        {appliedCoupon && <Label>Cupom aplicado: {appliedCoupon}</Label>}
      </Card>
      <Button
        title="Conferir total da compra"
        disabled={!pickup && !quote}
        loading={action.busy}
        onPress={() => action.run(() => preview())}
      />
      {summary && (
        <>
          <Summary resumo={summary} />
          <TermsConsent checked={checked} onChange={setChecked} />
          <Card>
            <Label muted>
              O pedido reservará os produtos. A cobrança será gerada somente
              quando você solicitar na tela do pedido.
            </Label>
            <Button
              title="Criar meu pedido"
              loading={action.busy}
              onPress={() =>
                ask(
                  "Criar pedido?",
                  `Total ${money(summary.valor_total_cliente)}. ${pickup ? "Retirada na barbearia." : "Entrega no endereço informado."}`,
                  () => action.run(order),
                )
              }
            />
          </Card>
        </>
      )}
    </Screen>
  );
}
