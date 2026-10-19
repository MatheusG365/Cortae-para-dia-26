import React, { useRef, useState } from "react";
import { View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { api, query } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, Input, Notice, Screen, Select, Stat } from "../../ui";
import {
  Collection,
  Copy,
  Feedback,
  Form,
  Heading,
  Period,
  Resource,
  confirmAction,
  dateTime,
  money,
  monthPeriod,
  s,
  today,
  uniqueKey,
  useMutation,
} from "./shared";
function Receipts({ initialId, done }) {
  const [id, setId] = useState(initialId ?? "");
  const [selected, setSelected] = useState(initialId ?? "");
  const state = useResource(
    selected ? `/gestao/agendamentos/${selected}/recebimentos` : null,
    null,
  );
  const [payments, setPayments] = useState([{ forma: "dinheiro", valor: "" }]);
  const mut = useMutation();
  const attempt = useRef({ signature: "", key: "" });
  const total =
    payments.reduce(
      (sum, p) => sum + Math.round(Number(p.valor.replace(",", ".")) * 100),
      0,
    ) / 100;
  return (
    <Card>
      <Heading>Pagamento do atendimento</Heading>
      <Copy muted>
        Registre somente valores recebidos no estabelecimento. O registro não
        cobra nem movimenta conta bancária.
      </Copy>
      <Input
        label="Número do agendamento"
        keyboardType="number-pad"
        value={id}
        onChangeText={(v) => {
          setId(v);
          setSelected("");
        }}
      />
      <Button
        title="Consultar atendimento"
        variant="secondary"
        onPress={() => setSelected(id)}
      />
      <Feedback state={mut} />
      {selected && (
        <Resource state={state}>
          {state.data && (
            <>
              <Copy>Atendimento: {money(state.data.valor_total)}</Copy>
              <Copy>
                Recebido: {money(state.data.valor_recebido)} · Saldo:{" "}
                {money(state.data.saldo)}
              </Copy>
              {(state.data.pagamentos ?? []).map((p, i) => (
                <Copy key={p.id_recebimento ?? i}>
                  {p.forma} · {money(p.valor)} · {dateTime(p.data_pagamento)}
                </Copy>
              ))}
              {Number(state.data.saldo) > 0 && (
                <>
                  {payments.map((p, i) => (
                    <View key={i} style={s.divider}>
                      <Select
                        label={`Forma ${i + 1}`}
                        value={p.forma}
                        onChange={(v) =>
                          setPayments((a) =>
                            a.map((p, j) => (j === i ? { ...p, forma: v } : p)),
                          )
                        }
                        options={[
                          { label: "Dinheiro", value: "dinheiro" },
                          { label: "Cartão físico", value: "cartao" },
                          {
                            label: "Pix manual conferido",
                            value: "pix_manual",
                          },
                        ]}
                      />
                      <Input
                        label="Valor já recebido (R$)"
                        keyboardType="decimal-pad"
                        value={p.valor}
                        onChangeText={(v) =>
                          setPayments((a) =>
                            a.map((p, j) => (j === i ? { ...p, valor: v } : p)),
                          )
                        }
                      />
                      {payments.length > 1 && (
                        <Button
                          title="Remover forma"
                          variant="ghost"
                          onPress={() =>
                            setPayments((a) => a.filter((_, j) => j !== i))
                          }
                        />
                      )}
                    </View>
                  ))}
                  <Button
                    title="Adicionar outra forma"
                    variant="secondary"
                    disabled={payments.length >= 3}
                    onPress={() =>
                      setPayments((a) => [...a, { forma: "cartao", valor: "" }])
                    }
                  />
                  <Copy>Total deste registro: {money(total)}</Copy>
                  <Button
                    title="Confirmar valores recebidos"
                    disabled={
                      !Number.isFinite(total) ||
                      total <= 0 ||
                      total > Number(state.data.saldo)
                    }
                    loading={mut.busy}
                    onPress={() =>
                      confirmAction(
                        "Registrar recebimento?",
                        "Confirme que conferiu o dinheiro, a máquina de cartão ou o comprovante do Pix.",
                        () => {
                          void mut.run(
                            async () => {
                              const body = {
                                pagamentos: payments.map((p) => ({
                                  forma: p.forma,
                                  valor: Number(p.valor.replace(",", ".")),
                                })),
                              };
                              const signature = JSON.stringify([
                                selected,
                                body,
                              ]);
                              if (attempt.current.signature !== signature)
                                attempt.current = {
                                  signature,
                                  key: uniqueKey(),
                                };
                              await api(
                                `/gestao/agendamentos/${selected}/recebimentos`,
                                {
                                  method: "POST",
                                  body: {
                                    ...body,
                                    chave_idempotencia: attempt.current.key,
                                  },
                                },
                              );
                              attempt.current = { signature: "", key: "" };
                              setPayments([{ forma: "dinheiro", valor: "" }]);
                            },
                            async () => {
                              await state.reload();
                              await done();
                            },
                            "Recebimento registrado.",
                          );
                        },
                      )
                    }
                  />
                </>
              )}
            </>
          )}
        </Resource>
      )}
    </Card>
  );
}
function Commissions({ period, done }) {
  const state = useResource(
    query("/gestao/comissoes/pagamentos", period),
    null,
  );
  const [entry, setEntry] = useState(null);
  const mut = useMutation();
  const attempt = useRef({ signature: "", key: "" });
  return (
    <>
      <Heading>Comissões</Heading>
      <Notice message="Registre pagamentos feitos por fora do sistema. Nenhuma transferência automática será realizada." />
      <Resource state={state}>
        {state.data && (
          <>
            <View style={s.row}>
              <Stat
                label="Calculadas"
                value={money(state.data.totais?.valor_comissao)}
              />
              <Stat label="A pagar" value={money(state.data.totais?.saldo)} />
            </View>
            {(state.data.comissoes ?? []).map((c) => (
              <Card key={c.id_agendamento}>
                <Heading>{c.nome_funcionario}</Heading>
                <Copy>
                  Atendimento #{c.id_agendamento} · {dateTime(c.inicio_em)}
                </Copy>
                <Copy>
                  Comissão: {money(c.valor_comissao)} · Pago:{" "}
                  {money(c.valor_pago)}
                </Copy>
                <Copy>Saldo: {money(c.saldo)}</Copy>
                {Number(c.saldo) > 0 && (
                  <Button
                    title="Registrar pagamento manual"
                    variant="secondary"
                    onPress={() =>
                      setEntry({
                        ...c,
                        valor: c.saldo,
                        data_pagamento: today(),
                        observacao: "",
                      })
                    }
                  />
                )}
              </Card>
            ))}
            <Collection
              title="Histórico de pagamentos"
              rows={state.data.pagamentos ?? []}
              fields={[
                ["nome_funcionario", "Profissional"],
                ["id_agendamento", "Atendimento"],
                ["valor", "Pago", money],
                ["data_pagamento", "Data", dateTime],
                ["observacao", "Observação"],
              ]}
            />
          </>
        )}
      </Resource>
      <Feedback state={mut} />
      {entry && (
        <Card>
          <Heading>Pagamento manual · #{entry.id_agendamento}</Heading>
          <Form
            key={entry.id_agendamento}
            fields={[
              {
                key: "valor",
                label: "Valor pago (R$)",
                type: "number",
                required: true,
                min: 0.01,
                max: entry.saldo,
              },
              {
                key: "data_pagamento",
                label: "Data do pagamento",
                type: "date",
                required: true,
              },
              { key: "observacao", label: "Observação" },
            ]}
            initial={entry}
            busy={mut.busy}
            title="Confirmar pagamento já realizado"
            onSubmit={(body) =>
              mut.run(
                async () => {
                  const payload = {
                    id_agendamento: entry.id_agendamento,
                    valor: body.valor,
                    data_pagamento: body.data_pagamento,
                    observacao: body.observacao,
                  };
                  const signature = JSON.stringify(payload);
                  if (attempt.current.signature !== signature)
                    attempt.current = { signature, key: uniqueKey() };
                  await api("/gestao/comissoes/pagamentos", {
                    method: "POST",
                    body: {
                      ...payload,
                      chave_idempotencia: attempt.current.key,
                    },
                  });
                  attempt.current = { signature: "", key: "" };
                  setEntry(null);
                },
                async () => {
                  await state.reload();
                  await done();
                },
                "Pagamento de comissão registrado.",
              )
            }
          />
          <Button
            title="Fechar registro"
            variant="ghost"
            onPress={() => setEntry(null)}
          />
        </Card>
      )}
    </>
  );
}
export default function OwnerFinance() {
  const params = useLocalSearchParams();
  const [period, setPeriod] = useState(monthPeriod());
  const summary = useResource(
    query("/gestao/financeiro/resumo", { ...period, agrupamento: "dia" }),
    null,
  );
  const records = useResource(
    query("/gestao/financeiro/lancamentos", period),
    null,
  );
  const categories = useResource("/gestao/financeiro/categorias", null);
  const [editor, setEditor] = useState(null);
  const [newCategory, setNewCategory] = useState(false);
  const mut = useMutation();
  const refresh = async () => {
    await Promise.all([
      summary.reload(),
      records.reload(),
      categories.reload(),
    ]);
  };
  const initial = () => ({
    tipo: "saida",
    categoria_id: "",
    descricao: "",
    valor: "",
    vencimento: today(),
    status: "pendente",
    data_pagamento: "",
  });
  const fields = [
    {
      key: "tipo",
      label: "Tipo",
      options: [
        { label: "Receita", value: "entrada" },
        { label: "Despesa", value: "saida" },
      ],
    },
    {
      key: "categoria_id",
      label: "Categoria",
      options: [
        { label: "Sem categoria", value: "" },
        ...(categories.data?.categorias ?? [])
          .filter((c) => c.ativo !== false)
          .map((c) => ({
            label: `${c.nome} · ${c.tipo}`,
            value: String(c.id_categoria),
          })),
      ],
    },
    { key: "descricao", label: "Descrição", required: true },
    {
      key: "valor",
      label: "Valor (R$)",
      type: "number",
      required: true,
      min: 0.01,
      max: 1000000,
    },
    { key: "vencimento", label: "Vencimento", type: "date", required: true },
    {
      key: "status",
      label: "Situação",
      options: [
        { label: "Pendente", value: "pendente" },
        { label: "Pago / recebido", value: "pago" },
        { label: "Cancelado", value: "cancelado" },
      ],
    },
    {
      key: "data_pagamento",
      label: "Data do pagamento (se pago)",
      type: "date",
    },
  ];
  return (
    <Screen
      back
      title="Caixa e comissões"
      subtitle="Recebimentos, despesas e pagamentos manuais."
      onRefresh={() => {
        void refresh();
      }}
      refreshing={summary.loading}
    >
      <Period onApply={setPeriod} />
      <Resource state={summary}>
        {summary.data && (
          <>
            <View style={s.row}>
              {[
                ["receitas", "Recebido"],
                ["despesas", "Despesas pagas"],
                ["lucro", "Resultado"],
                ["pendentes_receber", "A receber"],
                ["pendentes_pagar", "A pagar"],
              ].map(([key, label]) => (
                <Stat
                  key={key}
                  label={label}
                  value={money(summary.data.resumo?.[key])}
                />
              ))}
            </View>
            <Copy muted>
              Resultado de caixa de {period.inicio} até {period.fim}. Valores
              correspondem aos recebimentos e despesas pagos.
            </Copy>
            <Collection
              title="Fluxo diário"
              rows={summary.data.serie ?? []}
              fields={[
                ["periodo", "Dia"],
                ["receitas", "Receitas", money],
                ["despesas", "Despesas", money],
                ["lucro", "Resultado", money],
              ]}
            />
          </>
        )}
      </Resource>
      <Receipts initialId={params.atendimento} done={refresh} />
      <Feedback state={mut} />
      <Button title="Novo lançamento" onPress={() => setEditor(initial())} />
      <Button
        title="Cadastrar categoria"
        variant="secondary"
        onPress={() => setNewCategory((v) => !v)}
      />
      {newCategory && (
        <Card>
          <Heading>Nova categoria</Heading>
          <Form
            fields={[
              { key: "nome", label: "Nome", required: true },
              {
                key: "tipo",
                label: "Tipo",
                options: [
                  { label: "Receita", value: "entrada" },
                  { label: "Despesa", value: "saida" },
                ],
              },
            ]}
            initial={{ nome: "", tipo: "saida" }}
            busy={mut.busy}
            title="Salvar categoria"
            onSubmit={(body) =>
              mut.run(
                () =>
                  api("/gestao/financeiro/categorias", {
                    method: "POST",
                    body,
                  }),
                async () => {
                  setNewCategory(false);
                  await categories.reload();
                },
              )
            }
          />
        </Card>
      )}
      {editor && (
        <Card>
          <Heading>
            {editor.id_lancamento ? "Editar lançamento" : "Novo lançamento"}
          </Heading>
          <Form
            key={editor.id_lancamento ?? "new"}
            fields={fields}
            initial={editor}
            title="Salvar lançamento"
            busy={mut.busy}
            onSubmit={(v) =>
              mut.run(
                async () => {
                  if (v.status === "pago" && !v.data_pagamento)
                    throw new Error("Informe a data do pagamento.");
                  await api(
                    `/gestao/financeiro/lancamentos${editor.id_lancamento ? `/${editor.id_lancamento}` : ""}`,
                    {
                      method: editor.id_lancamento ? "PUT" : "POST",
                      body: {
                        ...v,
                        categoria_id: v.categoria_id
                          ? Number(v.categoria_id)
                          : null,
                        data_pagamento:
                          v.status === "pago" ? v.data_pagamento : null,
                      },
                    },
                  );
                },
                async () => {
                  setEditor(null);
                  await refresh();
                },
              )
            }
          />
          <Button
            title="Fechar edição"
            variant="ghost"
            onPress={() => setEditor(null)}
          />
        </Card>
      )}
      <Heading>Lançamentos</Heading>
      <Resource
        state={records}
        empty={!!records.data && !records.data.lancamentos?.length}
      >
        {(records.data?.lancamentos ?? []).map((r) => (
          <Card key={r.id_lancamento}>
            <Heading>{r.descricao}</Heading>
            <Copy>
              {r.tipo} · {money(r.valor)} · {r.status}
            </Copy>
            <Copy muted>Vencimento: {dateTime(r.vencimento)}</Copy>
            <Button
              title="Editar lançamento"
              variant="secondary"
              onPress={() =>
                setEditor({
                  ...r,
                  categoria_id: String(r.categoria_id ?? ""),
                  vencimento: String(r.vencimento ?? "").slice(0, 10),
                  data_pagamento: String(r.data_pagamento ?? "").slice(0, 10),
                })
              }
            />
          </Card>
        ))}
      </Resource>
      <Commissions period={period} done={refresh} />
    </Screen>
  );
}
