import React from "react";
import { Text, View } from "react-native";
import { useSession } from "../../lib/session";
import { useResource } from "../../lib/useResource";
import { query } from "../../lib/api";
import { Button, Card, Screen, Stat } from "../../ui";
import {
  Copy,
  Heading,
  Resource,
  dateTime,
  go,
  money,
  s,
  today,
} from "./shared";
export default function OwnerDashboard() {
  const { user } = useSession();
  const state = useResource(
    query("/gestao/agenda", { inicio: today(), fim: today() }),
    null,
  );
  const data = state.data;
  const items = data?.agendamentos ?? [];
  const next = items.filter((a) =>
    ["agendado", "confirmado"].includes(a.status),
  );
  return (
    <Screen
      title={`Olá, ${user?.nome?.split(" ")[0] || "profissional"}`}
      subtitle="Sua barbearia, em suas mãos."
      refreshing={state.loading}
      onRefresh={state.reload}
    >
      <Resource state={state}>
        {data && (
          <>
            <View style={s.row}>
              <Stat label="Hoje" value={String(items.length)} />
              <Stat
                label="Concluídos"
                value={String(
                  items.filter((a) => a.status === "concluido").length,
                )}
              />
            </View>
            <Card>
              <Heading>Um dia bem organizado</Heading>
              <Copy muted>
                {next.length
                  ? `${next.length} atendimento(s) previsto(s) para hoje.`
                  : "Nenhum próximo atendimento hoje."}
              </Copy>
              <Button
                title="Abrir minha agenda"
                onPress={() => go("/barbearia/agenda")}
              />
            </Card>
            <Heading>Próximos atendimentos</Heading>
            {next.slice(0, 4).map((a) => (
              <Card key={a.id_agendamento}>
                <Text style={s.heading}>
                  {String(a.inicio_em).slice(11, 16)} · {a.cliente_nome}
                </Text>
                <Copy>
                  {a.funcionario_nome || "Sem profissional"} ·{" "}
                  {money(a.valor_total)}
                </Copy>
                <Copy muted>
                  {dateTime(a.inicio_em)} · {a.status}
                </Copy>
                <Button
                  title="Gerenciar atendimento"
                  variant="secondary"
                  onPress={() =>
                    go(`/barbearia/agenda?atendimento=${a.id_agendamento}`)
                  }
                />
              </Card>
            ))}
          </>
        )}
      </Resource>
      <Heading>Seu negócio</Heading>
      <View style={s.spacer}>
        {[
          ["Equipe e serviços", "/barbearia/equipe"],
          ["Clientes e histórico", "/barbearia/clientes"],
          ["Caixa e comissões", "/barbearia/financeiro"],
          ["Ranking e avaliações", "/barbearia/ranking"],
          ["Metas da equipe", "/barbearia/metas"],
          ["Relatórios", "/barbearia/relatorios"],
          ["Perfil da barbearia", "/barbearia/perfil"],
        ].map(([title, path]) => (
          <Button
            key={path}
            title={title}
            variant="secondary"
            onPress={() => go(path)}
          />
        ))}
      </View>
    </Screen>
  );
}
