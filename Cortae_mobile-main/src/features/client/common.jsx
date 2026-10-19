import React, { useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { api, assetUrl } from "../../lib/api";
import { confirmDialog } from "../../lib/dialogs";
import { useResource } from "../../lib/useResource";
import { Button, Card, Empty, Loading, Notice, RemoteImage } from "../../ui";
import { colors, fonts } from "../../theme";
export const money = (v) =>
  v == null
    ? "Valor não informado"
    : Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
export const dateTime = (v) =>
  v
    ? new Date(String(v).replace(" ", "T")).toLocaleString("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
      })
    : "Não informado";
export const localDate = (date = new Date()) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
export const errorText = (e) =>
  e instanceof Error
    ? e.message
    : "Não foi possível concluir. Tente novamente.";
export const go = (pathname, params = {}) => router.push({ pathname, params });
export const ask = confirmDialog;
export function useAction() {
  const lock = useRef(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [success, setSuccess] = useState("");
  async function run(action, message = "") {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await action();
      setSuccess(message);
    } catch (e) {
      setError(errorText(e));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return { busy, error, success, run, setError };
}
export function Feedback({ state }) {
  return (
    <>
      {!!state.error && <Notice kind="error" message={state.error} />}
      {!!state.success && <Notice kind="success" message={state.success} />}
    </>
  );
}
export function Resource({ state, empty, children }) {
  if (state.loading) return <Loading />;
  if (state.error)
    return (
      <Notice
        kind="error"
        message={String(state.error)}
        onRetry={state.reload}
      />
    );
  if (empty)
    return (
      <Empty
        title="Nada por aqui ainda"
        message="Assim que houver informações, elas aparecerão aqui."
      />
    );
  return <>{children}</>;
}
export function Label({ children, muted = false }) {
  return <Text style={muted ? s.muted : s.text}>{children}</Text>;
}
export function Heading({ children }) {
  return <Text style={s.heading}>{children}</Text>;
}
export function ProductCard({ product: p, accent }) {
  return (
    <Card>
      <RemoteImage
        uri={assetUrl(p.imagens?.[0] || p.imagem)}
        style={s.productImage}
      />
      <Label muted>
        {p.barbearia} · {p.categoria || "Cuidados pessoais"}
      </Label>
      <Heading>{p.nome}</Heading>
      <View style={s.wrap}>
        {p.em_promocao && <Label>Promoção</Label>}
        {p.lancamento && <Label>Lançamento</Label>}
      </View>
      <Label>
        {money(p.preco)} · ★ {Number(p.media_avaliacoes || 0).toFixed(1)}
      </Label>
      <Button
        title="Conhecer produto"
        accent={accent}
        onPress={() => go(`/cliente/produto/${p.id_produto}`)}
      />
    </Card>
  );
}
export function Summary({ resumo: r }) {
  if (!r) return null;
  return (
    <Card>
      <Heading>Resumo dos valores</Heading>
      <Label>
        Produtos / serviços:{" "}
        {money(r.valor_base ?? r.base_calculo ?? r.subtotal)}
      </Label>
      {r.frete != null && <Label>Frete: {money(r.frete)}</Label>}
      {r.desconto > 0 && <Label>Desconto: −{money(r.desconto)}</Label>}
      {r.ativa && (
        <Label>
          Taxa {r.taxa_percentual ?? 1.5}%: {money(r.taxa_valor)} · paga por{" "}
          {r.taxa_pagador}
        </Label>
      )}
      <Heading>Total: {money(r.valor_total_cliente)}</Heading>
    </Card>
  );
}
export function TermsConsent({ checked, onChange }) {
  const terms = useResource("/termos-uso", {});
  return (
    <Card>
      <Resource state={terms}>
        <Heading>Termos de uso</Heading>
        {terms.data.estado_publicacao === "rascunho" ? (
          <Label muted>
            Política em rascunho. Nenhuma aceitação será registrada.
          </Label>
        ) : (
          <Button
            title={
              checked ? "✓ Li e aceito os termos" : "Ler e aceitar os termos"
            }
            variant="secondary"
            onPress={() => {
              if (checked) {
                onChange(false);
                return;
              }
              confirmDialog(
                terms.data.titulo || "Termos",
                (terms.data.secoes || [])
                  .map(
                    (sec) =>
                      `${sec.titulo}\n${(sec.paragrafos || []).join("\n")}`,
                  )
                  .join("\n\n"),
                () => onChange(true),
                { kind: "terms", confirmLabel: "Li e aceito" },
              );
            }}
          />
        )}
      </Resource>
    </Card>
  );
}
export async function acceptTerms(checked, expected) {
  const t = await api("/termos-uso");
  if (t.aceite_habilitado === false || t.estado_publicacao === "rascunho")
    return;
  if (expected && expected !== t.versao)
    throw new Error(
      "Os termos mudaram. Confira novamente o resumo e os termos.",
    );
  if (!checked) throw new Error("Leia e aceite os termos antes de continuar.");
  await api("/termos-uso/aceite", {
    method: "POST",
    body: { versao: t.versao, aceito: true },
  });
}
export const s = StyleSheet.create({
  text: {
    color: colors.text,
    fontFamily: fonts.regular,
    fontSize: 15,
    lineHeight: 23,
  },
  muted: {
    color: colors.muted,
    fontFamily: fonts.regular,
    fontSize: 13,
    lineHeight: 21,
  },
  heading: {
    color: colors.text,
    fontFamily: fonts.bold,
    fontSize: 20,
    fontWeight: "700",
    lineHeight: 28,
  },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  row: { flexDirection: "row", alignItems: "center", gap: 12 },
  productImage: {
    height: 190,
    width: "100%",
    borderRadius: 18,
    backgroundColor: colors.surfaceAlt,
  },
  hero: {
    height: 210,
    width: "100%",
    borderRadius: 22,
    backgroundColor: colors.surfaceAlt,
  },
  selected: {
    borderColor: colors.accent,
    borderWidth: 2,
    borderRadius: 18,
    padding: 12,
  },
  avatar: { width: 52, height: 52, borderRadius: 26 },
  small: { flex: 1, minWidth: 88 },
});
