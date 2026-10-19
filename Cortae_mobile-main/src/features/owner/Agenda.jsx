import React, { useState } from "react";
import { useLocalSearchParams } from "expo-router";
import { api, query } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, Screen, Select } from "../../ui";
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
  today,
  useMutation,
} from "./shared";
function range(day, mode) {
  const d = new Date(`${day}T12:00:00`);
  const end = new Date(d);
  end.setDate(d.getDate() + (mode === "semana" ? 6 : 0));
  return {
    inicio: day,
    fim: `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, "0")}-${String(end.getDate()).padStart(2, "0")}`,
  };
}
export default function OwnerAgenda() {
  const params = useLocalSearchParams();
  const [date, setDate] = useState(today());
  const [mode, setMode] = useState("dia");
  const [period, setPeriod] = useState(range(today(), "dia"));
  const [status, setStatus] = useState("");
  const [staff, setStaff] = useState("");
  const [selected, setSelected] = useState(null);
  const mut = useMutation();
  const state = useResource(query("/gestao/agenda", period), null);
  const blocks = useResource(query("/gestao/agenda/bloqueios", period), null);
  const data = state.data;
  const active =
    selected ??
    data?.agendamentos?.find(
      (a) => String(a.id_agendamento) === params.atendimento,
    );
  const items = (data?.agendamentos ?? []).filter(
    (a) =>
      (!status || a.status === status) &&
      (!staff || String(a.id_funcionario) === staff),
  );
  const run = (path, body, method = "PUT") =>
    mut.run(
      () => api(path, { method, body }),
      async () => {
        setSelected(null);
        await state.reload();
      },
    );
  return (
    <Screen
      title="Agenda"
      subtitle="Atendimentos, horários e disponibilidade."
      onRefresh={() => {
        void state.reload();
        void blocks.reload();
      }}
      refreshing={state.loading}
    >
      <Button
        title="Agendar um cliente"
        onPress={() => go("/barbearia/novo-agendamento")}
      />
      <Card>
        <Form
          key={date}
          fields={[
            {
              key: "data",
              label: "Data de referência",
              type: "date",
              required: true,
            },
          ]}
          initial={{ data: date }}
          title="Ver data"
          onSubmit={(v) => {
            setDate(v.data);
            setPeriod(range(v.data, mode));
          }}
        />
        <Select
          label="Visualização"
          value={mode}
          options={[
            { label: "Dia", value: "dia" },
            { label: "Próximos 7 dias", value: "semana" },
          ]}
          onChange={(v) => {
            setMode(v);
            setPeriod(range(date, v));
          }}
        />
        <Select
          label="Profissional"
          value={staff}
          options={[
            { label: "Toda a equipe", value: "" },
            ...(data?.funcionarios ?? []).map((f) => ({
              label: f.nome,
              value: String(f.id_funcionario),
            })),
          ]}
          onChange={setStaff}
        />
        <Select
          label="Status"
          value={status}
          onChange={setStatus}
          options={[
            { label: "Todos", value: "" },
            ...[
              "agendado",
              "confirmado",
              "concluido",
              "cancelado",
              "faltou",
            ].map((v) => ({ label: v, value: v })),
          ]}
        />
      </Card>
      <Feedback state={mut} />
      <Resource state={state} empty={!!data && !items.length}>
        {items.map((a) => (
          <Card key={a.id_agendamento}>
            <Badge>{a.status}</Badge>
            <Heading>
              {String(a.inicio_em).slice(11, 16)} · {a.cliente_nome}
            </Heading>
            <Copy>
              {dateTime(a.inicio_em)} — {String(a.fim_em ?? "").slice(11, 16)}
            </Copy>
            <Copy muted>
              {a.funcionario_nome || "Sem profissional"} ·{" "}
              {(a.servicos_nomes || []).join(", ")}
            </Copy>
            {a.corte_nome && <Copy>Corte: {a.corte_nome}</Copy>}
            <Copy>{money(a.valor_total)}</Copy>
            <Button
              title="Abrir atendimento"
              variant="secondary"
              onPress={() => setSelected(a)}
            />
          </Card>
        ))}
      </Resource>
      {active && (
        <Card>
          <Heading>Atendimento #{active.id_agendamento}</Heading>
          <Copy>
            {active.cliente_nome} · {active.funcionario_nome}
          </Copy>
          <Copy>
            {dateTime(active.inicio_em)} · {money(active.valor_total)}
          </Copy>
          {["agendado", "confirmado"].includes(active.status) && (
            <>
              <Form
                key={active.id_agendamento}
                fields={
                  active.valor_total == null
                    ? [
                        {
                          key: "valor_realizado",
                          label: "Valor real do atendimento antigo",
                          type: "number",
                          required: true,
                          min: 0,
                        },
                      ]
                    : []
                }
                initial={{}}
                title="Concluir atendimento"
                busy={mut.busy}
                onSubmit={(v) =>
                  confirmAction(
                    "Concluir atendimento?",
                    "Confirme somente se o serviço foi realizado.",
                    () => {
                      void run(
                        `/agendamentos/${active.id_agendamento}/status-atendimento`,
                        { status: "concluido", ...v },
                      );
                    },
                  )
                }
              />
              <Button
                title="Registrar falta"
                variant="secondary"
                disabled={mut.busy}
                onPress={() =>
                  confirmAction(
                    "Cliente faltou?",
                    "O atendimento será marcado como falta.",
                    () => {
                      void run(
                        `/agendamentos/${active.id_agendamento}/status-atendimento`,
                        { status: "faltou" },
                      );
                    },
                  )
                }
              />
              <Button
                title="Cancelar atendimento"
                variant="danger"
                disabled={mut.busy}
                onPress={() =>
                  confirmAction(
                    "Cancelar atendimento?",
                    "O horário será liberado e clientes na espera poderão ser avisados.",
                    () => {
                      void run(
                        `/agendamentos/${active.id_agendamento}/cancelar`,
                        {},
                      );
                    },
                  )
                }
              />
              <Heading>Remarcar</Heading>
              <Form
                fields={[
                  {
                    key: "data",
                    label: "Nova data",
                    type: "date",
                    required: true,
                  },
                  {
                    key: "horario",
                    label: "Novo horário",
                    type: "time",
                    required: true,
                  },
                ]}
                initial={{ data: today(), horario: "" }}
                title="Confirmar reagendamento"
                busy={mut.busy}
                onSubmit={(v) =>
                  run(`/agendamentos/${active.id_agendamento}/reagendar`, v)
                }
              />
            </>
          )}
          <Button
            title="Registrar recebimento"
            variant="secondary"
            onPress={() =>
              go(`/barbearia/financeiro?atendimento=${active.id_agendamento}`)
            }
          />
          <Button
            title="Fechar atendimento"
            variant="ghost"
            onPress={() => {
              setSelected(null);
              go("/barbearia/agenda");
            }}
          />
        </Card>
      )}
      <Heading>Bloqueios e folgas</Heading>
      <Resource state={blocks}>
        {(blocks.data?.bloqueios ?? []).map((b) => (
          <Card key={b.id_bloqueio}>
            <Heading>{b.motivo}</Heading>
            <Copy>
              {dateTime(b.inicio_em)} até {dateTime(b.fim_em)}
            </Copy>
            <Button
              title="Remover bloqueio"
              variant="danger"
              disabled={mut.busy}
              onPress={() =>
                confirmAction(
                  "Remover bloqueio?",
                  "O período voltará a ficar disponível conforme o expediente.",
                  () => {
                    void mut.run(
                      () =>
                        api(`/gestao/agenda/bloqueios/${b.id_bloqueio}`, {
                          method: "DELETE",
                        }),
                      blocks.reload,
                    );
                  },
                )
              }
            />
          </Card>
        ))}
      </Resource>
      <Card>
        <Heading>Bloquear um período</Heading>
        <Copy muted>
          Use data e horário local: AAAA-MM-DDTHH:MM. O servidor impede conflito
          com reservas.
        </Copy>
        <Form
          fields={[
            {
              key: "id_funcionario",
              label: "Profissional",
              options: [
                { label: "Todo o salão", value: "" },
                ...(data?.funcionarios ?? []).map((f) => ({
                  label: f.nome,
                  value: String(f.id_funcionario),
                })),
              ],
            },
            { key: "inicio_em", label: "Início", required: true },
            { key: "fim_em", label: "Fim", required: true },
            { key: "motivo", label: "Motivo", required: true },
          ]}
          initial={{
            id_funcionario: "",
            inicio_em: `${date}T08:00`,
            fim_em: `${date}T12:00`,
            motivo: "",
          }}
          title="Salvar bloqueio"
          busy={mut.busy}
          onSubmit={(v) =>
            mut.run(
              () =>
                api("/gestao/agenda/bloqueios", {
                  method: "POST",
                  body: {
                    ...v,
                    id_funcionario: v.id_funcionario
                      ? Number(v.id_funcionario)
                      : null,
                  },
                }),
              blocks.reload,
            )
          }
        />
      </Card>
    </Screen>
  );
}
