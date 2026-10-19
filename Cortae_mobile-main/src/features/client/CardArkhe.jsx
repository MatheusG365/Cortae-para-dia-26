import React, { useCallback, useEffect, useRef, useState } from "react";
import { View } from "react-native";
import { useFocusEffect } from "expo-router";
import { Button, Card, Input, Select } from "../../ui";
import { Heading, Label, money } from "./common";
import { dadosCartao, limiteParcelas } from "./cardRules";

const empty = () => ({
  numero_cartao: "",
  validade: "",
  cvv: "",
  tipo: "DEBITO",
  parcelas: 1,
});
export function CardReceipt({ receipt }) {
  if (!receipt) return null;
  return (
    <Card>
      <Heading>Pagamento aprovado · Cartão virtual Arkhé</Heading>
      <Label>
        {money(receipt.valor)} ·{" "}
        {receipt.tipo === "CREDITO" ? "Crédito" : "Débito"} · {receipt.parcelas}{" "}
        parcela(s) · final {String(receipt.final_cartao || "").slice(-4)}
      </Label>
      <Label>
        Compra {receipt.id_compra} · Movimentação {receipt.id_movimentacao}
      </Label>
      <Label>
        Recebimento do estabelecimento: {money(receipt.valor_recebido)} · taxa
        do estabelecimento: {money(receipt.taxa)}.
      </Label>
    </Card>
  );
}
export default function CardArkhe({ total, onSubmit, disabled = false }) {
  const [fields, setFields] = useState(empty);
  const [review, setReview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  const sensitive = useRef(null);
  useEffect(
    () => () => {
      if (sensitive.current) Object.assign(sensitive.current, empty());
    },
    [],
  );
  useFocusEffect(
    useCallback(
      () => () => {
        if (sensitive.current) Object.assign(sensitive.current, empty());
        setFields(empty());
        setReview(false);
      },
      [],
    ),
  );
  function clear() {
    if (sensitive.current) Object.assign(sensitive.current, empty());
    setFields(empty());
    setReview(false);
  }
  function change(name, value) {
    const next = {
      ...fields,
      [name]: value,
      ...(name === "tipo" ? { parcelas: 1 } : {}),
    };
    sensitive.current = next;
    setFields(next);
    setReview(false);
  }
  function check() {
    setError("");
    try {
      dadosCartao(fields, total);
      setReview(true);
    } catch (problem) {
      setError(problem.message);
    }
  }
  async function send() {
    if (lock.current || disabled) return;
    lock.current = true;
    setBusy(true);
    setError("");
    let body;
    try {
      body = dadosCartao(fields, total);
      clear();
      await onSubmit(body);
    } catch (problem) {
      setError(
        problem.message || "Confira o status antes de uma nova cobrança.",
      );
    } finally {
      if (body) {
        body.numero_cartao = "";
        body.cvv = "";
        body.validade = "";
      }
      clear();
      lock.current = false;
      setBusy(false);
    }
  }
  const blocked = busy || disabled;
  return (
    <Card>
      <Heading>Cartão virtual Arkhé</Heading>
      <Label>
        Use o cartão da sua conta Arkhé. Total confirmado pelo servidor:{" "}
        {money(total)}.
      </Label>
      <Label>
        Crédito: até 15 parcelas; a taxa de 5% é descontada do estabelecimento.
        Débito: uma parcela, recebimento integral.
      </Label>
      <View pointerEvents={blocked ? "none" : "auto"} style={{ gap: 12 }}>
        <Input
          label="Número do cartão virtual Arkhé"
          value={fields.numero_cartao}
          onChangeText={(v) =>
            change("numero_cartao", v.replace(/\D/g, "").slice(0, 16))
          }
          keyboardType="number-pad"
          maxLength={16}
          editable={!blocked}
          autoComplete="off"
          importantForAutofill="no"
          autoCorrect={false}
        />
        <Input
          label="Validade (MM/YYYY)"
          value={fields.validade}
          onChangeText={(v) => change("validade", v.slice(0, 7))}
          placeholder="MM/YYYY"
          maxLength={7}
          editable={!blocked}
          autoComplete="off"
          importantForAutofill="no"
          autoCorrect={false}
        />
        <Input
          label="CVV"
          value={fields.cvv}
          onChangeText={(v) => change("cvv", v.replace(/\D/g, "").slice(0, 3))}
          keyboardType="number-pad"
          maxLength={3}
          editable={!blocked}
          secureTextEntry
          autoComplete="off"
          importantForAutofill="no"
          autoCorrect={false}
        />
        <Select
          label="Modalidade"
          value={fields.tipo}
          onChange={(v) => change("tipo", v)}
          options={[
            { value: "DEBITO", label: "Débito" },
            { value: "CREDITO", label: "Crédito" },
          ]}
        />
        <Select
          label="Parcelas"
          value={fields.parcelas}
          onChange={(v) => change("parcelas", v)}
          options={Array.from(
            {
              length:
                fields.tipo === "DEBITO"
                  ? Math.min(1, limiteParcelas(total))
                  : limiteParcelas(total),
            },
            (_, i) => ({ value: i + 1, label: `${i + 1} parcela(s)` }),
          )}
        />
      </View>
      {!!error && <Label>{error}</Label>}
      {review ? (
        <>
          <Label>
            Confirmar {money(total)} no{" "}
            {fields.tipo === "CREDITO" ? "crédito" : "débito"}, em{" "}
            {fields.parcelas} parcela(s)?
          </Label>
          <Button
            title="Confirmar pagamento"
            onPress={send}
            loading={busy}
            disabled={disabled}
          />
          <Button
            title="Voltar"
            onPress={() => setReview(false)}
            disabled={blocked}
            variant="secondary"
          />
        </>
      ) : (
        <Button
          title="Conferir pagamento com cartão"
          onPress={check}
          loading={busy}
          disabled={disabled || !limiteParcelas(total)}
        />
      )}
      <Button
        title="Limpar dados do cartão"
        onPress={() => {
          clear();
          setError("");
        }}
        disabled={blocked}
        variant="ghost"
      />
    </Card>
  );
}
