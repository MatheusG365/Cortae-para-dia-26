import React, { useState } from "react";
import { View } from "react-native";
import { api, query } from "../../lib/api";
import { useSession } from "../../lib/session";
import { useResource } from "../../lib/useResource";
import { Button, Card, Chip, Input, Notice, Screen, Select } from "../../ui";
import {
  Copy,
  DateField,
  Feedback,
  Heading,
  Resource,
  go,
  money,
  s,
  today,
  useMutation,
} from "./shared";
export default function OwnerBooking() {
  const { user } = useSession();
  const state = useResource(
    query("/gestao/agenda", { inicio: today(), fim: today() }),
    null,
  );
  const mut = useMutation();
  const [email, setEmail] = useState("");
  const [found, setFound] = useState(null);
  const [client, setClient] = useState("");
  const [staff, setStaff] = useState("");
  const [day, setDay] = useState(today());
  const [services, setServices] = useState([]);
  const [chosenHour, setChosenHour] = useState({ key: "", value: "" });
  const [summaryState, setSummary] = useState(null);
  const [accepted, setAccepted] = useState(false);
  const terms = useResource("/termos-uso", null);
  const selectedKey = services.join(",");
  const salon = state.data?.id_barbearia ?? user?.id_usuario;
  const availability = useResource(
    salon && staff && services.length
      ? query("/agendamentos/horarios", {
          id_barbearia: salon,
          id_funcionario: staff,
          data: day,
          ids_servicos: selectedKey,
        })
      : null,
    null,
  );
  const selection = [client, staff, day, selectedKey].join(":");
  const hour = chosenHour.key === selection ? chosenHour.value : "";
  const summary =
    summaryState?._selection === selection + ":" + hour ? summaryState : null;
  const setHour = (v) => setChosenHour({ key: selection, value: v });
  const clients = [
    ...(state.data?.clientes ?? []),
    ...(found &&
    !(state.data?.clientes ?? []).some((c) => c.id_usuario === found.id_usuario)
      ? [found]
      : []),
  ];
  const body = {
    id_barbearia: Number(salon),
    id_cliente: Number(client),
    id_funcionario: Number(staff),
    ids_servicos: services,
  };
  async function preview() {
    await mut.run(
      async () => {
        if (!client || !staff || !services.length || !hour)
          throw new Error(
            "Selecione cliente, profissional, serviços e horário.",
          );
        const r = await api("/agendamentos/resumo", {
          method: "POST",
          body,
        });
        if (!r.resumo?.confirmacao_resumo)
          throw new Error("O servidor não confirmou os valores.");
        setSummary({ ...r.resumo, _selection: selection + ":" + hour });
      },
      undefined,
      "Valores conferidos. Revise antes de confirmar.",
    );
  }
  async function save() {
    await mut.run(
      async () => {
        if (!summary?.confirmacao_resumo)
          throw new Error("Confira os valores antes de agendar.");
        if (!terms.data) throw new Error("Aguarde os Termos de Uso.");
        const draft =
          terms.data.aceite_habilitado === false ||
          terms.data.estado_publicacao === "rascunho";
        if (!draft && !accepted)
          throw new Error("Leia e aceite os Termos de Uso.");
        if (!draft)
          await api("/termos-uso/aceite", {
            method: "POST",
            body: { versao: terms.data.versao, aceito: true },
          });
        await api("/gestao/agenda", {
          method: "POST",
          body: {
            ...body,
            data: day,
            horario: hour,
            confirmacao_resumo: summary.confirmacao_resumo,
          },
        });
        go("/barbearia/agenda");
      },
      undefined,
      "Agendamento criado.",
    );
  }
  return (
    <Screen
      back
      title="Agendar cliente"
      subtitle="Disponibilidade e preços confirmados pela barbearia."
    >
      <Feedback state={mut} />
      <Resource state={state}>
        <Card>
          <Heading>Quem será atendido?</Heading>
          <Input
            label="E-mail de cliente cadastrado"
            autoCapitalize="none"
            keyboardType="email-address"
            value={email}
            onChangeText={setEmail}
          />
          <Button
            title="Localizar cliente"
            variant="secondary"
            loading={mut.busy}
            onPress={() => {
              void mut.run(
                async () => {
                  const r = await api(
                    query("/gestao/agenda/cliente", { email: email.trim() }),
                  );
                  setFound(r.cliente);
                  setClient(String(r.cliente.id_usuario));
                },
                undefined,
                "Cliente localizado.",
              );
            }}
          />
          <Select
            label="Cliente"
            value={client}
            onChange={setClient}
            options={[
              { label: "Selecione", value: "" },
              ...clients.map((c) => ({
                label: `${c.nome} · ${c.email}`,
                value: String(c.id_usuario),
              })),
            ]}
          />
        </Card>
        <Card>
          <Heading>Serviços e profissional</Heading>
          <View style={s.row}>
            {(state.data?.servicos ?? [])
              .filter((v) => v.ativo !== false)
              .map((v) => (
                <Chip
                  key={v.id_servico}
                  active={services.includes(v.id_servico)}
                  onPress={() =>
                    setServices((a) =>
                      a.includes(v.id_servico)
                        ? a.filter((id) => id !== v.id_servico)
                        : [...a, v.id_servico],
                    )
                  }
                >
                  {v.nome} · {money(v.preco)}
                </Chip>
              ))}
          </View>
          <Select
            label="Profissional"
            value={staff}
            onChange={setStaff}
            options={[
              { label: "Selecione", value: "" },
              ...(state.data?.funcionarios ?? [])
                .filter(
                  (f) =>
                    f.ativo !== false &&
                    services.every((id) =>
                      (f.ids_servicos ?? f.servicos ?? []).includes(id),
                    ),
                )
                .map((f) => ({
                  label: f.nome,
                  value: String(f.id_funcionario),
                })),
            ]}
          />
          <DateField
            label="Data do atendimento"
            value={day}
            onChange={setDay}
          />
          <Resource state={availability}>
            <Select
              label="Horário disponível"
              value={hour}
              onChange={(v) => {
                setHour(v);
                setSummary(null);
              }}
              options={[
                { label: "Selecione", value: "" },
                ...(availability.data?.horarios ?? [])
                  .filter((h) => h.disponivel)
                  .map((h) => ({
                    label: `${h.horario} — ${h.fim}`,
                    value: h.horario,
                  })),
              ]}
            />
            {availability.data &&
              !(availability.data.horarios ?? []).some((h) => h.disponivel) && (
                <Notice message="Não há horário disponível para esta seleção. Escolha outra data ou profissional." />
              )}
          </Resource>
          <Button
            title="Conferir valores"
            loading={mut.busy}
            onPress={() => {
              void preview();
            }}
          />
        </Card>
      </Resource>
      {summary && (
        <Card>
          <Heading>Resumo do atendimento</Heading>
          <Copy>Serviços: {money(summary.valor_base)}</Copy>
          <Copy>Taxa: {money(summary.taxa_valor)}</Copy>
          <Copy>Total do cliente: {money(summary.valor_total_cliente)}</Copy>
          <Copy>
            {day} · {hour}
          </Copy>
          <Button
            variant="ghost"
            title="Ler Termos de Uso"
            onPress={() => go("/termos")}
          />
          {terms.data?.aceite_habilitado !== false &&
            terms.data?.estado_publicacao !== "rascunho" && (
              <Chip active={accepted} onPress={() => setAccepted((v) => !v)}>
                Li e aceito os Termos de Uso pela minha conta.
              </Chip>
            )}
          <Notice message="O aceite é da sua própria conta ao registrar a reserva, sem representar aceite em nome do cliente." />
          <Button
            title="Confirmar agendamento"
            loading={mut.busy}
            onPress={() => {
              void save();
            }}
          />
        </Card>
      )}
    </Screen>
  );
}
