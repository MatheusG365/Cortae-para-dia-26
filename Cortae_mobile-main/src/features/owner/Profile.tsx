import React from "react";
import { api } from "../../lib/api";
import { useSession } from "../../lib/session";
import { useResource } from "../../lib/useResource";
import { Button, Card, Screen } from "../../ui";
import {
  Copy,
  Feedback,
  Field,
  Form,
  Heading,
  Resource,
  go,
  useMutation,
} from "./shared";
const fields: Field[] = [
  { key: "historia", label: "Sobre a barbearia", type: "multiline" },
  { key: "localizacao", label: "Endereço / localização" },
  { key: "contato_telefone", label: "Telefone público com DDD" },
  { key: "contato_email", label: "E-mail público", type: "email" },
  { key: "instagram", label: "Instagram" },
  { key: "cor_primaria", label: "Cor principal (#RRGGBB)", required: true },
  { key: "cor_secundaria", label: "Cor secundária (#RRGGBB)", required: true },
  { key: "cor_terciaria", label: "Cor de destaque (#RRGGBB)", required: true },
  {
    key: "cor_texto_primario",
    label: "Texto principal (#RRGGBB)",
    required: true,
  },
  {
    key: "cor_texto_secundario",
    label: "Texto secundário (#RRGGBB)",
    required: true,
  },
];
export default function OwnerProfile() {
  const state = useResource<any>("/barbearia/perfil", null);
  const config = useResource<any>("/gestao/agenda/config", null);
  const { user } = useSession();
  const mut = useMutation();
  return (
    <Screen
      back
      title="Minha barbearia"
      subtitle="Identidade, contatos públicos e regras de agenda."
      onRefresh={() => {
        void state.reload();
        void config.reload();
      }}
      refreshing={state.loading}
    >
      <Feedback state={mut} />
      <Resource state={state}>
        {state.data && (
          <Card>
            <Heading>{user?.nome}</Heading>
            <Copy muted>
              Essas informações aparecem aos clientes. As cores são aplicadas à
              identidade da sua barbearia.
            </Copy>
            <Form
              key={state.data.personalizacao?.id_personalizacao ?? "new"}
              fields={fields}
              initial={{
                historia: "",
                localizacao: "",
                contato_telefone: "",
                contato_email: "",
                instagram: "",
                cor_primaria: "#101010",
                cor_secundaria: "#191919",
                cor_terciaria: "#FF8800",
                cor_texto_primario: "#FFFFFF",
                cor_texto_secundario: "#AAAAAA",
                ...state.data.personalizacao,
              }}
              busy={mut.busy}
              title="Salvar perfil público"
              onSubmit={(v) =>
                mut.run(
                  () =>
                    api("/barbearia/perfil", {
                      method: "PATCH",
                      body: Object.fromEntries(
                        fields.map((f) => [f.key, v[f.key]]),
                      ),
                    }),
                  state.reload,
                )
              }
            />
          </Card>
        )}
      </Resource>
      <Resource state={config}>
        {config.data && (
          <Card>
            <Heading>Regras e lembretes</Heading>
            <Copy muted>
              Antecedência em horas. Zero permite alterações até o início;
              lembrete zero desativa o aviso.
            </Copy>
            <Form
              fields={[
                {
                  key: "cancelamento_horas",
                  label: "Prazo para cancelamento (h)",
                  type: "number",
                  required: true,
                  min: 0,
                  max: 720,
                },
                {
                  key: "reagendamento_horas",
                  label: "Prazo para reagendamento (h)",
                  type: "number",
                  required: true,
                  min: 0,
                  max: 720,
                },
                {
                  key: "lembrete_horas",
                  label: "Lembrete por e-mail antes do atendimento (h)",
                  type: "number",
                  required: true,
                  min: 0,
                  max: 720,
                },
              ]}
              initial={config.data}
              busy={mut.busy}
              title="Salvar regras de agenda"
              onSubmit={(body) =>
                mut.run(
                  () => api("/gestao/agenda/config", { method: "PUT", body }),
                  config.reload,
                )
              }
            />
          </Card>
        )}
      </Resource>
      <Card>
        <Heading>Expediente da equipe</Heading>
        <Copy muted>
          Ajuste turnos e intervalos de cada profissional para definir horários
          disponíveis.
        </Copy>
        <Button
          title="Configurar profissionais"
          variant="secondary"
          onPress={() => go("/barbearia/equipe")}
        />
      </Card>
    </Screen>
  );
}
