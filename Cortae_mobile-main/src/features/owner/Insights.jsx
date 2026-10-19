import React, { useState } from "react";
import { View } from "react-native";
import { api, query } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, Notice, Screen, Select, Stat } from "../../ui";
import {
  Badge,
  Collection,
  Copy,
  Feedback,
  Form,
  Heading,
  Period,
  Resource,
  dateTime,
  money,
  monthPeriod,
  s,
  today,
  useMutation,
} from "./shared";
export function OwnerRanking() {
  const [period, setPeriod] = useState(monthPeriod());
  const [order, setOrder] = useState("faturamento");
  const [staff, setStaff] = useState("");
  const [page, setPage] = useState(1);
  const state = useResource(
    query("/gestao/ranking", { ...period, ordenar: order }),
    null,
  );
  const reviews = useResource(
    query("/gestao/avaliacoes", {
      ...period,
      pagina: page,
      ...(staff ? { id_funcionario: staff } : {}),
    }),
    null,
  );
  return (
    <Screen
      back
      title="Ranking e avaliações"
      subtitle="Resultados da equipe e experiência dos clientes."
      onRefresh={() => {
        void state.reload();
        void reviews.reload();
      }}
      refreshing={state.loading}
    >
      <Period
        onApply={(p) => {
          setPage(1);
          setPeriod(p);
        }}
      />
      <Select
        label="Ordenar ranking"
        value={order}
        onChange={setOrder}
        options={[
          { label: "Valor dos serviços", value: "faturamento" },
          { label: "Atendimentos", value: "atendimentos" },
          { label: "Avaliações", value: "avaliacao" },
        ]}
      />
      <Resource state={state}>
        {state.data && (
          <>
            <View style={s.row}>
              <Stat
                label="Realizados"
                value={state.data.resumo?.atendimentos_realizados ?? 0}
              />
              <Stat
                label="Valor dos serviços"
                value={money(state.data.resumo?.faturamento)}
              />
            </View>
            <Notice message="Valores usam o histórico de serviços concluídos. Não representam necessariamente dinheiro recebido." />
            {(state.data.profissionais ?? []).map((p) => (
              <Card key={p.id_funcionario}>
                <Badge>
                  {p.posicao ? `${p.posicao}º lugar` : "Sem posição"}
                </Badge>
                <Heading>{p.nome}</Heading>
                <Copy>
                  {p.atendimentos_realizados} realizados ·{" "}
                  {money(p.faturamento)}
                </Copy>
                <Copy>
                  ★{" "}
                  {p.media_nota == null
                    ? "Sem avaliação"
                    : Number(p.media_nota).toFixed(1)}{" "}
                  · {p.total_avaliacoes} avaliações
                </Copy>
                {Number(p.sem_valor_historico) > 0 && (
                  <Notice
                    message={`${p.sem_valor_historico} atendimento(s) sem valor histórico.`}
                  />
                )}
              </Card>
            ))}
          </>
        )}
      </Resource>
      <Heading>Avaliações dos clientes</Heading>
      <Select
        label="Profissional"
        value={staff}
        onChange={(v) => {
          setStaff(v);
          setPage(1);
        }}
        options={[
          { label: "Toda a equipe", value: "" },
          ...(state.data?.profissionais ?? []).map((p) => ({
            label: p.nome,
            value: String(p.id_funcionario),
          })),
        ]}
      />
      <Resource
        state={reviews}
        empty={!!reviews.data && !reviews.data.avaliacoes?.length}
      >
        {(reviews.data?.avaliacoes ?? []).map((r) => (
          <Card key={r.id_agendamento}>
            <Heading>
              ★ {r.nota} · {r.cliente_nome || "Cliente"}
            </Heading>
            <Copy>{r.comentario || "Sem comentário."}</Copy>
            <Copy muted>
              {r.funcionario_nome} · {dateTime(r.inicio_em)}
            </Copy>
          </Card>
        ))}
      </Resource>
      {Number(reviews.data?.paginas) > 1 && (
        <View style={s.row}>
          <Button
            title="Anterior"
            variant="secondary"
            disabled={page <= 1 || reviews.loading}
            onPress={() => setPage((p) => p - 1)}
          />
          <Copy>
            {page} de {reviews.data.paginas}
          </Copy>
          <Button
            title="Próxima"
            variant="secondary"
            disabled={page >= reviews.data.paginas || reviews.loading}
            onPress={() => setPage((p) => p + 1)}
          />
        </View>
      )}
    </Screen>
  );
}
export function OwnerGoals() {
  const [period, setPeriod] = useState(monthPeriod());
  const state = useResource(query("/gestao/metas", period), null);
  const team = useResource(
    query("/gestao/agenda", { inicio: today(), fim: today() }),
    null,
  );
  const [editor, setEditor] = useState(null);
  const mut = useMutation();
  return (
    <Screen
      back
      title="Metas da equipe"
      subtitle="Objetivos claros, progresso acompanhado."
      onRefresh={state.reload}
      refreshing={state.loading}
    >
      <Period onApply={setPeriod} />
      <Button
        title="Criar meta"
        onPress={() =>
          setEditor({
            id_funcionario: "",
            tipo: "atendimentos",
            alvo: "",
            ...period,
            ativo: true,
          })
        }
      />
      <Feedback state={mut} />
      {editor && (
        <Card>
          <Heading>{editor.id_meta ? "Editar meta" : "Nova meta"}</Heading>
          <Resource state={team}>
            <Form
              key={editor.id_meta ?? "new"}
              fields={[
                {
                  key: "id_funcionario",
                  label: "Profissional",
                  required: true,
                  options: [
                    { label: "Selecione", value: "" },
                    ...(team.data?.funcionarios ?? []).map((p) => ({
                      label: p.nome,
                      value: String(p.id_funcionario),
                    })),
                  ],
                },
                {
                  key: "tipo",
                  label: "Indicador",
                  options: [
                    { label: "Atendimentos concluídos", value: "atendimentos" },
                    {
                      label: "Valor dos serviços concluídos",
                      value: "faturamento",
                    },
                  ],
                },
                {
                  key: "alvo",
                  label: "Objetivo (quantidade ou R$)",
                  type: "number",
                  required: true,
                  min: 0.01,
                },
                {
                  key: "inicio",
                  label: "Início",
                  type: "date",
                  required: true,
                },
                { key: "fim", label: "Fim", type: "date", required: true },
              ]}
              initial={{
                ...editor,
                id_funcionario: String(editor.id_funcionario),
              }}
              title="Salvar meta"
              busy={mut.busy}
              onSubmit={(v) =>
                mut.run(
                  () =>
                    api(
                      `/gestao/metas${editor.id_meta ? `/${editor.id_meta}` : ""}`,
                      {
                        method: editor.id_meta ? "PUT" : "POST",
                        body: {
                          ...v,
                          id_funcionario: Number(v.id_funcionario),
                        },
                      },
                    ),
                  async () => {
                    setEditor(null);
                    await state.reload();
                  },
                )
              }
            />
          </Resource>
          <Button
            title="Cancelar edição"
            variant="ghost"
            onPress={() => setEditor(null)}
          />
        </Card>
      )}
      <Resource state={state} empty={!!state.data && !state.data.metas?.length}>
        {(state.data?.metas ?? []).map((m) => (
          <Card key={m.id_meta}>
            <Badge>
              {!m.ativo
                ? "Inativa"
                : m.atingida
                  ? "Atingida"
                  : "Em acompanhamento"}
            </Badge>
            <Heading>{m.nome_profissional}</Heading>
            <Copy muted>
              {dateTime(m.inicio)} até {dateTime(m.fim)}
            </Copy>
            <Copy>
              {m.tipo === "faturamento" ? money(m.realizado) : m.realizado} de{" "}
              {m.tipo === "faturamento" ? money(m.alvo) : m.alvo}
            </Copy>
            <View style={s.progress}>
              <View
                style={[
                  s.progressFill,
                  {
                    width: `${Math.max(0, Math.min(100, Number(m.percentual) || 0))}%`,
                  },
                ]}
              />
            </View>
            <Copy>
              {Number(m.percentual).toFixed(1)}% ·{" "}
              {m.atingida
                ? "Objetivo alcançado"
                : `Faltam ${m.tipo === "faturamento" ? money(m.restante) : m.restante}`}
            </Copy>
            {m.sem_valor_historico > 0 && (
              <Notice message="Há atendimentos sem valor histórico; o progresso financeiro pode estar incompleto." />
            )}
            <Button
              title="Editar meta"
              variant="secondary"
              onPress={() => setEditor(m)}
            />
            <Button
              title={m.ativo ? "Desativar meta" : "Ativar meta"}
              variant="ghost"
              disabled={mut.busy}
              onPress={() => {
                void mut.run(
                  () =>
                    api(`/gestao/metas/${m.id_meta}`, {
                      method: "PATCH",
                      body: { ativo: !m.ativo },
                    }),
                  state.reload,
                );
              }}
            />
          </Card>
        ))}
      </Resource>
      <Copy muted>
        O progresso considera o período completo da meta e os preços históricos
        dos serviços, sem medir recebimentos bancários.
      </Copy>
    </Screen>
  );
}
export function OwnerReports() {
  const [period, setPeriod] = useState(monthPeriod());
  const state = useResource(
    query("/gestao/relatorios", { ...period, inativos_dias: 90 }),
    null,
  );
  const d = state.data;
  return (
    <Screen
      back
      title="Relatórios"
      subtitle="Entenda a rotina e os resultados do estabelecimento."
      onRefresh={state.reload}
      refreshing={state.loading}
    >
      <Period onApply={setPeriod} />
      <Resource state={state}>
        {d && (
          <>
            <View style={s.row}>
              {[
                ["agendamentos", "Agendamentos"],
                ["realizados", "Realizados"],
                ["cancelados", "Cancelados"],
                ["faltas", "Faltas"],
                ["clientes", "Clientes"],
              ].map(([key, label]) => (
                <Stat key={key} label={label} value={d.resumo?.[key] ?? 0} />
              ))}
            </View>
            <Card>
              <Heading>Valor dos serviços realizados</Heading>
              <Copy>{money(d.resumo?.valor_realizado)}</Copy>
              <Copy muted>
                Preço registrado na reserva. Consulte o caixa para ver valores
                recebidos.
              </Copy>
            </Card>
            <Collection
              title="Serviços procurados"
              rows={d.servicos ?? []}
              fields={[
                ["nome", "Serviço"],
                ["quantidade", "Quantidade"],
                ["valor", "Valor", money],
              ]}
            />
            <Collection
              title="Profissionais"
              rows={d.profissionais ?? []}
              fields={[
                ["nome", "Profissional"],
                ["quantidade", "Agendamentos"],
                ["realizados", "Realizados"],
                ["valor", "Valor realizado", money],
              ]}
            />
            <Collection
              title="Horários procurados"
              rows={d.horarios ?? []}
              fields={[
                ["hora", "Horário"],
                ["quantidade", "Agendamentos"],
              ]}
            />
            <Collection
              title="Clientes frequentes"
              rows={d.clientes ?? []}
              fields={[
                ["nome", "Nome"],
                ["atendimentos_realizados", "Realizados"],
                ["faltas", "Faltas"],
                ["ultima_visita", "Última visita", dateTime],
              ]}
            />
            <Collection
              title="Sem visita há 90 dias"
              rows={d.inativos ?? []}
              fields={[
                ["nome", "Nome"],
                ["telefone", "Telefone"],
                ["dias_inativo", "Dias sem visita"],
              ]}
            />
          </>
        )}
      </Resource>
    </Screen>
  );
}
