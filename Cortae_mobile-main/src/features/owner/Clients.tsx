import React, { useState } from "react";
import { api, query } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, Screen } from "../../ui";
import {
  Collection,
  Copy,
  Feedback,
  Form,
  Heading,
  Resource,
  dateTime,
  money,
  useMutation,
} from "./shared";
export default function OwnerClients() {
  const [filter, setFilter] = useState<any>({});
  const state = useResource<any>(query("/gestao/clientes", filter), null);
  const [id, setId] = useState<number | null>(null);
  const detail = useResource<any>(id ? `/gestao/clientes/${id}` : null, null);
  const mut = useMutation();
  const data = detail.data;
  return (
    <Screen
      back
      title="Clientes"
      subtitle="Preferências, visitas e histórico de cada cliente."
      onRefresh={state.reload}
      refreshing={state.loading}
    >
      <Card>
        <Form
          fields={[
            { key: "busca", label: "Nome, e-mail ou telefone" },
            {
              key: "inativos_dias",
              label: "Sem visita há dias",
              type: "number",
              nullable: true,
              min: 1,
              max: 3650,
            },
          ]}
          initial={{ busca: "", inativos_dias: "" }}
          title="Buscar clientes"
          onSubmit={(v) =>
            setFilter(
              Object.fromEntries(
                Object.entries(v).filter(([, x]) => x != null && x !== ""),
              ),
            )
          }
        />
      </Card>
      <Feedback state={mut} />
      <Resource
        state={state}
        empty={!!state.data && !state.data.clientes?.length}
      >
        {(state.data?.clientes ?? []).map((c: any) => (
          <Card key={c.id_usuario}>
            <Heading>{c.nome}</Heading>
            <Copy muted>
              {c.email} · {c.telefone || "Telefone não informado"}
            </Copy>
            <Copy>
              {c.atendimentos_realizados ?? 0} realizados · {c.faltas ?? 0}{" "}
              faltas
            </Copy>
            <Copy muted>Última visita: {dateTime(c.ultima_visita)}</Copy>
            <Button
              title="Abrir ficha"
              variant="secondary"
              onPress={() => setId(c.id_usuario)}
            />
          </Card>
        ))}
      </Resource>
      {id && (
        <Resource state={detail}>
          {data && (
            <>
              <Card>
                <Heading>Ficha de {data.cliente?.nome}</Heading>
                <Copy>
                  {data.cliente?.email} · {data.cliente?.telefone}
                </Copy>
                <Form
                  key={id}
                  fields={[
                    {
                      key: "observacoes",
                      label: "Observações",
                      type: "multiline",
                    },
                    {
                      key: "preferencias",
                      label: "Preferências",
                      type: "multiline",
                    },
                  ]}
                  initial={{
                    observacoes: data.observacoes ?? "",
                    preferencias: data.preferencias ?? "",
                  }}
                  busy={mut.busy}
                  title="Salvar ficha"
                  onSubmit={(body) =>
                    mut.run(
                      () =>
                        api(`/gestao/clientes/${id}`, { method: "PUT", body }),
                      detail.reload,
                    )
                  }
                />
                <Button
                  title="Fechar ficha"
                  variant="ghost"
                  onPress={() => setId(null)}
                />
              </Card>
              <Collection
                title="Atendimentos e faltas"
                rows={data.agendamentos ?? []}
                fields={[
                  ["inicio_em", "Data", dateTime],
                  ["funcionario_nome", "Profissional"],
                  ["status", "Status"],
                  ["valor_total", "Valor", money],
                ]}
              />
              <Collection
                title="Histórico financeiro"
                rows={data.pagamentos ?? []}
                fields={[
                  ["id_agendamento", "Atendimento"],
                  ["forma", "Forma"],
                  ["valor", "Valor", money],
                  ["status", "Status"],
                ]}
              />
            </>
          )}
        </Resource>
      )}
    </Screen>
  );
}
