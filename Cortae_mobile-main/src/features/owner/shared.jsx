import React, { useRef, useState } from "react";
import { Platform, StyleSheet, Text, View } from "react-native";
import DateTimePicker from "@react-native-community/datetimepicker";
import { router } from "expo-router";
import { confirmDialog, showInformation } from "../../lib/dialogs";
import { Button, Card, Empty, Input, Loading, Notice, Select } from "../../ui";
import { colors, fonts } from "../../theme";
export const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
export function monthPeriod() {
  const d = new Date();
  return {
    inicio: `${today().slice(0, 7)}-01`,
    fim: `${today().slice(0, 7)}-${new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate()}`,
  };
}
export const money = (n) =>
  n == null || !Number.isFinite(Number(n))
    ? "Não informado"
    : Number(n).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
export const dateTime = (v) =>
  v
    ? String(v)
        .slice(0, 16)
        .replace("T", " às ")
        .split(" às ")
        .map((p, i) => (i === 0 ? p.split("-").reverse().join("/") : p))
        .join(" às ")
    : "Não informado";
export const message = (e) =>
  typeof e === "string"
    ? e
    : e instanceof Error
      ? e.message
      : "Não foi possível concluir. Tente novamente.";
export const go = (path) => router.push(path);
export const uniqueKey = () =>
  `mobile-${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
export const confirmAction = confirmDialog;
export function Heading({ children }) {
  return <Text style={s.heading}>{children}</Text>;
}
export function Copy({ children, muted = false }) {
  return (
    <Text selectable style={[s.copy, muted && s.muted]}>
      {children}
    </Text>
  );
}
export function Badge({ children }) {
  return (
    <View style={s.badge}>
      <Text style={s.badgeText}>{children}</Text>
    </View>
  );
}
export function Resource({ state, children, empty = false }) {
  if (state.loading) return <Loading />;
  if (state.error)
    return (
      <Notice
        message={message(state.error)}
        kind="error"
        onRetry={state.reload}
      />
    );
  if (empty)
    return (
      <Empty
        title="Nenhum registro"
        message="Não há dados para os filtros selecionados."
      />
    );
  return <>{children}</>;
}
export function useMutation() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const lock = useRef(false);
  async function run(action, done, text = "Alterações salvas.") {
    if (lock.current) return false;
    lock.current = true;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await action();
      await done?.();
      setSuccess(text);
      return true;
    } catch (e) {
      setError(message(e));
      return false;
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
export function DateField({
  label,
  value,
  onChange,
  mode = "date",
  optional = false,
  disabled = false,
}) {
  const [open, setOpen] = useState(false);
  const parsed = new Date(
    mode === "date"
      ? `${value || today()}T12:00:00`
      : `${today()}T${value || "08:00"}:00`,
  );
  const date = Number.isNaN(parsed.getTime()) ? new Date() : parsed;
  if (Platform.OS === "web")
    return (
      <Input
        label={`${label} (${mode === "date" ? "AAAA-MM-DD" : "HH:MM"})`}
        value={value}
        onChangeText={onChange}
        editable={!disabled}
      />
    );
  return (
    <View style={{ gap: 6 }}>
      <Copy>{label}</Copy>
      <Button
        title={
          value
            ? mode === "date"
              ? value.split("-").reverse().join("/")
              : value
            : "Selecionar"
        }
        variant="secondary"
        disabled={disabled}
        onPress={() => setOpen((v) => !v)}
      />
      {open && (
        <DateTimePicker
          value={date}
          mode={mode}
          display={Platform.OS === "ios" ? "spinner" : "default"}
          is24Hour
          themeVariant="dark"
          onDismiss={() => setOpen(false)}
          onValueChange={(_, picked) => {
            if (Platform.OS !== "ios") setOpen(false);
            onChange(
              mode === "date"
                ? `${picked.getFullYear()}-${String(picked.getMonth() + 1).padStart(2, "0")}-${String(picked.getDate()).padStart(2, "0")}`
                : `${String(picked.getHours()).padStart(2, "0")}:${String(picked.getMinutes()).padStart(2, "0")}`,
            );
          }}
        />
      )}
      {optional && !!value && (
        <Button
          title="Limpar data"
          variant="ghost"
          disabled={disabled}
          onPress={() => onChange("")}
        />
      )}
    </View>
  );
}
export function Form({
  fields,
  initial,
  onSubmit,
  title = "Salvar",
  busy = false,
}) {
  const [values, setValues] = useState(initial);
  const [error, setError] = useState("");
  function submit() {
    setError("");
    const body = { ...values };
    for (const f of fields) {
      const raw = values[f.key];
      const v = String(raw ?? "").trim();
      if (f.required && !v) {
        setError(`Preencha: ${f.label}.`);
        return;
      }
      if (f.type === "date" && v && !/^\d{4}-\d{2}-\d{2}$/.test(v)) {
        setError(`${f.label}: use AAAA-MM-DD.`);
        return;
      }
      if (f.type === "time" && v && !/^([01]\d|2[0-3]):[0-5]\d$/.test(v)) {
        setError(`${f.label}: use HH:MM.`);
        return;
      }
      if (f.type === "number") {
        if (!v && f.nullable) {
          body[f.key] = null;
          continue;
        }
        const n = Number(v.replace(",", "."));
        if (
          !Number.isFinite(n) ||
          (f.min != null && n < f.min) ||
          (f.max != null && n > f.max)
        ) {
          setError(`Valor inválido: ${f.label}.`);
          return;
        }
        body[f.key] = n;
      } else if (f.nullable && !v) body[f.key] = null;
    }
    void onSubmit(body);
  }
  return (
    <View style={s.form}>
      {fields.map((f) =>
        f.options ? (
          <Select
            key={f.key}
            label={f.label}
            value={String(values[f.key] ?? "")}
            options={f.options}
            onChange={(v) => setValues((a) => ({ ...a, [f.key]: v }))}
          />
        ) : f.type === "date" || f.type === "time" ? (
          <DateField
            key={f.key}
            label={f.label}
            value={String(values[f.key] ?? "")}
            mode={f.type}
            onChange={(v) => setValues((a) => ({ ...a, [f.key]: v }))}
            optional={!f.required}
            disabled={busy}
          />
        ) : (
          <Input
            key={f.key}
            label={f.label}
            value={String(values[f.key] ?? "")}
            onChangeText={(v) => setValues((a) => ({ ...a, [f.key]: v }))}
            multiline={f.type === "multiline"}
            autoCapitalize={f.type === "email" ? "none" : "sentences"}
            keyboardType={
              f.type === "number"
                ? "decimal-pad"
                : f.type === "email"
                  ? "email-address"
                  : "default"
            }
            editable={!busy}
          />
        ),
      )}
      {!!error && <Notice kind="error" message={error} />}
      <Button title={title} onPress={submit} loading={busy} />
    </View>
  );
}
export function Period({ onApply, initial = monthPeriod() }) {
  return (
    <Card>
      <Form
        fields={[
          { key: "inicio", label: "De", type: "date", required: true },
          { key: "fim", label: "Até", type: "date", required: true },
        ]}
        initial={initial}
        title="Consultar período"
        onSubmit={(p) => {
          if (p.inicio > p.fim)
            showInformation(
              "Datas inválidas",
              "A data inicial deve vir antes da final.",
            );
          else onApply(p);
        }}
      />
    </Card>
  );
}
export function Collection({ title, rows, fields }) {
  return (
    <Card>
      <Heading>{title}</Heading>
      {!rows.length && <Copy muted>Nenhum registro no período.</Copy>}
      {rows.map((r, i) => (
        <View key={r.id ?? i} style={s.divider}>
          {fields.map(([key, label, format]) => (
            <Copy key={key}>
              {label}: {format ? format(r[key]) : String(r[key] ?? "—")}
            </Copy>
          ))}
        </View>
      ))}
    </Card>
  );
}

export const s = StyleSheet.create({
  heading: {
    fontFamily: fonts.bold,
    fontSize: 19,
    fontWeight: "700",
    color: colors.text,
    marginBottom: 8,
  },
  copy: {
    fontFamily: fonts.regular,
    color: colors.text,
    fontSize: 14,
    lineHeight: 22,
  },
  muted: { color: colors.muted },
  form: { gap: 14 },
  badge: {
    alignSelf: "flex-start",
    borderRadius: 8,
    paddingVertical: 5,
    paddingHorizontal: 9,
    backgroundColor: colors.surfaceAlt,
  },
  badgeText: {
    fontFamily: fonts.bold,
    color: colors.accent,
    fontSize: 12,
    fontWeight: "700",
  },
  divider: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: 12,
    marginTop: 10,
    gap: 4,
  },
  row: { flexDirection: "row", gap: 10, flexWrap: "wrap" },
  spacer: { gap: 14 },
  progress: {
    height: 8,
    borderRadius: 4,
    overflow: "hidden",
    backgroundColor: colors.surfaceAlt,
  },
  progressFill: { height: 8, backgroundColor: colors.accent, borderRadius: 4 },
});
