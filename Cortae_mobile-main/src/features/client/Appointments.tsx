import React, { useState } from "react";
import { View } from "react-native";
import DateTimePicker from "@react-native-community/datetimepicker";
import { useLocalSearchParams } from "expo-router";
import { api, assetUrl, query } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, Input, RemoteImage, Screen, Select } from "../../ui";
import {
  Data,
  Feedback,
  Heading,
  Label,
  Resource,
  Summary,
  ask,
  dateTime,
  go,
  localDate,
  money,
  s,
  useAction,
} from "./common";
import BookingPayment from "./Payment";
function Review({ item, onSaved }: { item: Data; onSaved: () => void }) {
  const [note, setNote] = useState(String(item.avaliacao?.nota || 5)),
    [comment, setComment] = useState(item.avaliacao?.comentario || "");
  const action = useAction();
  return (
    <Card>
      <Heading>
        {item.avaliacao ? "Sua avaliação" : "Como foi sua experiência?"}
      </Heading>
      <Select
        label="Sua nota"
        value={note}
        onChange={setNote}
        options={[5, 4, 3, 2, 1].map((v) => ({
          label: `${v} ${v === 1 ? "estrela" : "estrelas"}`,
          value: String(v),
        }))}
      />
      <Input
        label="Conte como foi"
        value={comment}
        onChangeText={setComment}
        maxLength={1000}
        multiline
      />
      <Feedback state={action} />
      <Button
        title="Salvar avaliação"
        loading={action.busy}
        onPress={() =>
          action.run(async () => {
            await api(`/agendamentos/${item.id_agendamento}/avaliacao`, {
              method: "PUT",
              body: { nota: Number(note), comentario: comment },
            });
            onSaved();
          }, "Obrigado pela sua avaliação.")
        }
      />
    </Card>
  );
}
function Reschedule({ item, onSaved }: { item: Data; onSaved: () => void }) {
  const [date, setDate] = useState(localDate()),
    [showDate, setShowDate] = useState(false),
    [slot, setSlot] = useState("");
  const action = useAction();
  const state = useResource<Data>(
    query("/agendamentos/horarios", {
      id_barbearia: item.id_barbearia,
      ids_servicos: (item.servicos || []).join(","),
      id_funcionario: item.id_funcionario || undefined,
      data: date,
    }),
    {},
  );
  return (
    <Card>
      <Heading>Escolha o novo horário</Heading>
      <Button
        title={date.split("-").reverse().join("/")}
        variant="secondary"
        onPress={() => setShowDate(true)}
      />
      {showDate && (
        <DateTimePicker
          value={new Date(date + "T12:00:00")}
          mode="date"
          minimumDate={new Date()}
          onChange={(_: any, value?: Date) => {
            setShowDate(false);
            if (value) {
              setDate(localDate(value));
              setSlot("");
            }
          }}
        />
      )}
      <Resource state={state}>
        <Select
          label="Horários livres"
          value={slot}
          onChange={setSlot}
          options={[
            { label: "Selecione um horário", value: "" },
            ...(state.data.horarios || [])
              .filter((h: Data) => h.disponivel)
              .map((h: Data) => ({
                label: `${h.horario} até ${h.fim}`,
                value: h.horario,
              })),
          ]}
        />
      </Resource>
      <Feedback state={action} />
      <Button
        title="Confirmar remarcação"
        disabled={!slot}
        loading={action.busy}
        onPress={() =>
          ask(
            "Reagendar atendimento?",
            `${date} às ${slot}. Os prazos da barbearia serão conferidos pelo sistema.`,
            () =>
              action.run(async () => {
                await api(`/agendamentos/${item.id_agendamento}/reagendar`, {
                  method: "PUT",
                  body: { data: date, horario: slot },
                });
                onSaved();
              }, "Atendimento remarcado."),
          )
        }
      />
    </Card>
  );
}
export default function Appointments() {
  const params = useLocalSearchParams<{ id: string }>();
  const state = useResource<Data>("/agendamentos", {});
  const waiting = useResource<Data>("/agendamentos/lista-espera", {});
  const [actionId, setActionId] = useState(params.id || ""),
    [mode, setMode] = useState("details"),
    [tab, setTab] = useState("proximos");
  const action = useAction();
  const all = state.data.agendamentos || [];
  const selected = all.find((v: Data) => String(v.id_agendamento) === actionId);
  const list = all.filter((v: Data) =>
    tab === "historico"
      ? ["cancelado", "concluido", "faltou"].includes(v.status)
      : !["cancelado", "concluido", "faltou"].includes(v.status),
  );
  return (
    <Screen
      title="Meus agendamentos"
      subtitle="Seu próximo cuidado e suas experiências anteriores"
      refreshing={state.loading}
      onRefresh={() => {
        state.reload();
        waiting.reload();
      }}
    >
      <Feedback state={action} />
      {selected ? (
        <>
          <Button
            title="← Voltar à lista"
            variant="ghost"
            onPress={() => {
              setActionId("");
              setMode("details");
            }}
          />
          <Card>
            <Heading>{selected.barbearia_nome}</Heading>
            <Label>{(selected.servicos_nomes || []).join(", ")}</Label>
            <Label>
              {dateTime(selected.inicio_em)} ·{" "}
              {selected.funcionario_nome || "Profissional não informado"}
            </Label>
            <Label>{selected.corte_nome}</Label>
            <Heading>{money(selected.valor_total)}</Heading>
            <Label>Status: {selected.status}</Label>
            {selected.corte_imagem_url && (
              <RemoteImage
                uri={assetUrl(selected.corte_imagem_url)}
                style={s.productImage}
              />
            )}
            <View style={s.wrap}>
              {selected.permite_reagendar && (
                <Button
                  title="Reagendar"
                  variant="secondary"
                  onPress={() =>
                    setMode(mode === "reschedule" ? "details" : "reschedule")
                  }
                />
              )}
              {selected.permite_cancelar && (
                <Button
                  title="Cancelar"
                  variant="danger"
                  loading={action.busy}
                  onPress={() =>
                    ask(
                      "Cancelar atendimento?",
                      "O cancelamento depende das regras de prazo do estabelecimento. A reserva será encerrada após confirmação.",
                      () =>
                        action.run(async () => {
                          await api(
                            `/agendamentos/${selected.id_agendamento}/cancelar`,
                            { method: "PUT", body: {} },
                          );
                          await state.reload();
                        }, "Agendamento cancelado."),
                    )
                  }
                />
              )}
            </View>
          </Card>
          {mode === "reschedule" && (
            <Reschedule
              item={selected}
              onSaved={() => {
                setMode("details");
                state.reload();
              }}
            />
          )}
          <Summary resumo={selected.resumo} />
          <BookingPayment booking={selected} />
          {selected.pode_avaliar && (
            <Review
              key={selected.id_agendamento}
              item={selected}
              onSaved={state.reload}
            />
          )}
          {selected.avaliacao && !selected.pode_avaliar && (
            <Card>
              <Heading>★ {selected.avaliacao.nota}/5</Heading>
              <Label>{selected.avaliacao.comentario}</Label>
            </Card>
          )}
          <Card>
            <Heading>Histórico do atendimento</Heading>
            {(selected.historico_atendimento || []).map((v: Data) => (
              <Label key={v.id_historico}>
                {v.status} · {dateTime(v.registrado_em)}
              </Label>
            ))}
          </Card>
        </>
      ) : (
        <>
          <View style={s.wrap}>
            <Button
              title="Próximos"
              variant={tab === "proximos" ? "primary" : "secondary"}
              onPress={() => setTab("proximos")}
            />
            <Button
              title="Histórico"
              variant={tab === "historico" ? "primary" : "secondary"}
              onPress={() => setTab("historico")}
            />
          </View>
          <Resource state={state} empty={!list.length}>
            {list.map((v: Data) => (
              <Card key={v.id_agendamento}>
                <Label muted>{v.status.toUpperCase()}</Label>
                <Heading>{v.barbearia_nome}</Heading>
                <Label>{(v.servicos_nomes || []).join(", ")}</Label>
                <Label>{dateTime(v.inicio_em)}</Label>
                <Label muted>
                  {v.funcionario_nome || "Profissional não informado"} ·{" "}
                  {money(v.valor_total)}
                </Label>
                <Button
                  title={
                    v.pode_avaliar ? "Ver detalhes e avaliar" : "Ver detalhes"
                  }
                  variant="secondary"
                  onPress={() => {
                    setActionId(String(v.id_agendamento));
                    setMode("details");
                  }}
                />
              </Card>
            ))}
          </Resource>
          <Heading>Minha lista de espera</Heading>
          <Label muted>
            O aviso por e-mail não reserva o horário. Após o aviso, confirme sua
            reserva.
          </Label>
          <Resource state={waiting}>
            {(waiting.data.lista_espera || waiting.data.entradas || []).map(
              (v: Data) => (
                <Card key={v.id_lista_espera || v.id}>
                  <Heading>{v.barbearia_nome || "Barbearia"}</Heading>
                  <Label>
                    {dateTime(v.inicio_em) || `${v.data} ${v.horario}`}
                  </Label>
                  <Label muted>{v.status}</Label>
                  <Button
                    title="Consultar disponibilidade"
                    variant="secondary"
                    onPress={() =>
                      go("/cliente/agendar", {
                        barbearia: v.id_barbearia,
                        servicos: (v.ids_servicos || v.servicos || []).join(
                          ",",
                        ),
                        funcionario: v.id_funcionario || "",
                        escolha_corte: v.escolha_corte || "na_hora",
                        id_corte: v.id_corte || "",
                        id_visagismo: v.id_visagismo || "",
                      })
                    }
                  />
                  {v.status !== "cancelada" && (
                    <Button
                      title="Sair da lista de espera"
                      variant="ghost"
                      disabled={action.busy}
                      onPress={() =>
                        ask(
                          "Sair da lista?",
                          "Você deixará de receber aviso para este horário.",
                          () =>
                            action.run(async () => {
                              await api(
                                `/agendamentos/lista-espera/${v.id_lista_espera || v.id}`,
                                { method: "DELETE" },
                              );
                              await waiting.reload();
                            }),
                        )
                      }
                    />
                  )}
                </Card>
              ),
            )}
          </Resource>
          <Button
            title="Encontrar um novo atendimento"
            onPress={() => go("/cliente")}
          />
        </>
      )}
    </Screen>
  );
}
