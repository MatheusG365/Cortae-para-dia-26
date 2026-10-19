import React, { useState } from "react";
import { bookingChoice } from "./clientRules";
import { View } from "react-native";
import DateTimePicker from "@react-native-community/datetimepicker";
import { useLocalSearchParams } from "expo-router";
import { api, query } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, Notice, Screen, Select } from "../../ui";
import {
  Feedback,
  Heading,
  Label,
  Resource,
  Summary,
  TermsConsent,
  acceptTerms,
  ask,
  go,
  localDate,
  s,
  useAction,
} from "./common";
export default function Booking() {
  const p = useLocalSearchParams();
  const [staffSelection, setStaffSelection] = useState(p.funcionario || ""),
    [date, setDate] = useState(localDate()),
    [showDate, setShowDate] = useState(false),
    [slot, setSlot] = useState(""),
    [summary, setSummary] = useState(null),
    [checked, setChecked] = useState(false),
    [created, setCreated] = useState(null);
  const action = useAction();
  const people = useResource(
    query(`/barbearias/${p.barbearia}/funcionarios`, { servicos: p.servicos }),
    {},
  );
  const staff =
    staffSelection ||
    (people.data.funcionarios?.length === 1
      ? String(people.data.funcionarios[0].id_funcionario)
      : "");
  const required = !!people.data.funcionarios?.length;
  const schedule = useResource(
    !people.loading && (!required || staff) && !people.error
      ? query("/agendamentos/horarios", {
          id_barbearia: p.barbearia,
          ids_servicos: p.servicos,
          id_funcionario: staff || undefined,
          data: date,
        })
      : null,
    {},
  );
  const body = {
    id_barbearia: Number(p.barbearia),
    ids_servicos: String(p.servicos || "")
      .split(",")
      .filter(Boolean),
    id_funcionario: staff ? Number(staff) : null,
    data: date,
    horario: slot,
    ...bookingChoice(p),
  };
  async function preview() {
    const d = await api("/agendamentos/resumo", { method: "POST", body });
    setSummary(d.resumo);
  }
  async function create() {
    if (!summary?.confirmacao_resumo)
      throw new Error("Confira os valores antes de confirmar.");
    await acceptTerms(checked, summary.termos_versao);
    try {
      const d = await api("/agendamentos", {
        method: "POST",
        body: { ...body, confirmacao_resumo: summary.confirmacao_resumo },
      });
      setCreated(d.agendamento);
    } catch (e) {
      setSummary(null);
      await schedule.reload();
      throw e;
    }
  }
  if (created)
    return (
      <Screen
        title="Seu horário está reservado"
        subtitle="Acompanhe os detalhes e escolha como pagar"
        back
      >
        <Card>
          <Heading>Agendamento #{created.id_agendamento}</Heading>
          <Label>
            {date.split("-").reverse().join("/")} · {slot}
          </Label>
          <Label>O pagamento ainda precisa ser confirmado.</Label>
          <Button
            title="Ver meu agendamento e pagamento"
            onPress={() =>
              go("/cliente/agendamentos", {
                id: String(created.id_agendamento),
              })
            }
          />
        </Card>
      </Screen>
    );
  return (
    <Screen
      title="Reserve seu momento"
      subtitle="Escolha o profissional, o dia e um horário disponível"
      back
    >
      <Feedback state={action} />
      <Resource state={people}>
        <Select
          label="Com quem você quer se cuidar?"
          value={staff}
          options={[
            {
              label: required
                ? "Escolha o profissional"
                : "Sem profissional disponível para estes serviços",
              value: "",
            },
            ...(people.data.funcionarios || []).map((f) => ({
              label: f.nome,
              value: String(f.id_funcionario),
            })),
          ]}
          onChange={(v) => {
            setStaffSelection(v);
            setSlot("");
            setSummary(null);
          }}
        />
        {!people.data.funcionarios?.length && (
          <Notice
            kind="info"
            message="Se os serviços exigirem profissional e não houver horários, escolha outra combinação de serviços ou entre em contato com o estabelecimento."
          />
        )}
      </Resource>
      <Button
        title={`Dia: ${date.split("-").reverse().join("/")}`}
        variant="secondary"
        onPress={() => setShowDate(true)}
      />
      {showDate && (
        <DateTimePicker
          value={new Date(date + "T12:00:00")}
          mode="date"
          minimumDate={new Date()}
          onDismiss={() => setShowDate(false)}
          onValueChange={(_, value) => {
            setShowDate(false);
            if (value) {
              setDate(localDate(value));
              setSlot("");
              setSummary(null);
            }
          }}
        />
      )}
      <Heading>Horários disponíveis</Heading>
      <Resource state={schedule}>
        {!schedule.data.horarios?.length && (
          <Notice
            kind="info"
            message="Nenhum horário disponível nesta data. Consulte outro dia ou profissional."
          />
        )}
        <View style={s.wrap}>
          {(schedule.data.horarios || []).map((h) => (
            <View style={s.small} key={h.horario}>
              <Button
                title={`${h.horario}${slot === h.horario ? " ✓" : ""}${!h.disponivel ? " · reservado" : ""}`}
                variant={slot === h.horario ? "primary" : "secondary"}
                disabled={
                  action.busy || (!h.disponivel && !h.lista_espera_disponivel)
                }
                onPress={() => {
                  if (h.disponivel) {
                    setSlot(h.horario);
                    setSummary(null);
                  } else
                    ask(
                      "Entrar na lista de espera?",
                      `${date} às ${h.horario}. Você receberá um aviso por e-mail se este horário for liberado. O aviso não reserva o horário.`,
                      () =>
                        action.run(async () => {
                          await api("/agendamentos/lista-espera", {
                            method: "POST",
                            body: { ...body, horario: h.horario },
                          });
                        }, "Você entrou na lista de espera. Acompanhe em Agendamentos."),
                    );
                }}
              />
            </View>
          ))}
        </View>
        {slot && (
          <Card>
            <Heading>
              {slot} · {schedule.data.duracao_minutos} minutos
            </Heading>
            <Label>
              {(schedule.data.servicos || []).map((v) => v.nome).join(", ")}
            </Label>
            <Button
              title="Conferir valores"
              loading={action.busy}
              onPress={() => action.run(preview)}
            />
          </Card>
        )}
      </Resource>
      {summary && (
        <>
          <Summary resumo={summary} />
          <TermsConsent checked={checked} onChange={setChecked} />
          <Button
            title="Confirmar agendamento"
            loading={action.busy}
            onPress={() =>
              ask(
                "Confirmar agendamento?",
                `${date.split("-").reverse().join("/")} às ${slot}. O pagamento será escolhido depois da reserva.`,
                () => action.run(create),
              )
            }
          />
        </>
      )}
    </Screen>
  );
}
