import React, { useState } from "react";
import { Share, View } from "react-native";
import { api, query } from "../../lib/api";
import { showInformation } from "../../lib/dialogs";
import { useResource } from "../../lib/useResource";
import { Button, Card, Chip, Input, Screen, Select } from "../../ui";
import {
  Badge,
  Copy,
  Feedback,
  Form,
  Heading,
  Resource,
  Field,
  confirmAction,
  money,
  s,
  today,
  useMutation,
} from "./shared";

const weekdays = [
  "segunda",
  "terca",
  "quarta",
  "quinta",
  "sexta",
  "sabado",
  "domingo",
];
const serviceFields: Field[] = [
  { key: "nome", label: "Nome do serviço", required: true },
  { key: "descricao", label: "Descrição", type: "multiline" },
  {
    key: "genero",
    label: "Público",
    options: [
      { label: "Masculino", value: "masculino" },
      { label: "Feminino", value: "feminino" },
      { label: "Unissex", value: "unissex" },
    ],
  },
  {
    key: "preco",
    label: "Preço padrão (R$)",
    type: "number",
    required: true,
    min: 0,
    max: 1000000,
  },
  {
    key: "duracao",
    label: "Duração (minutos)",
    type: "number",
    required: true,
    min: 1,
    max: 1440,
  },
];
function Professional({ person, services }: { person: any; services: any[] }) {
  const [opened, setOpened] = useState(false);
  const state = useResource<any>(
    opened ? `/gestao/profissionais/${person.id_funcionario}/config` : null,
    null,
  );
  const [draft, setDraft] = useState<any>(null);
  const mut = useMutation();
  const config = draft ?? state.data;
  const edit = (k: string, v: any) => setDraft({ ...config, [k]: v });
  return (
    <Card>
      <Badge>{person.ativo === false ? "Inativo" : "Ativo"}</Badge>
      <Heading>{person.nome}</Heading>
      <Copy muted>Comissão, preço por serviço e turnos individuais.</Copy>
      <Button
        title={opened ? "Fechar configuração" : "Configurar profissional"}
        variant="secondary"
        onPress={() => setOpened((v) => !v)}
      />
      {opened && (
        <Resource state={state}>
          {config && (
            <>
              <Feedback state={mut} />
              <Select
                label="Comissão"
                value={config.comissao_tipo || "percentual"}
                onChange={(v) => edit("comissao_tipo", v)}
                options={[
                  { label: "Percentual (%)", value: "percentual" },
                  { label: "Valor fixo (R$)", value: "fixa" },
                ]}
              />
              <Input
                label="Valor da comissão"
                keyboardType="decimal-pad"
                value={String(config.comissao_valor ?? 0)}
                onChangeText={(v) => edit("comissao_valor", v)}
              />
              <Heading>Turnos e intervalos</Heading>
              <Copy muted>
                Cadastre turnos separados para os intervalos. Sem turnos, o
                profissional fica indisponível.
              </Copy>
              {(config.horarios ?? []).map((h: any, i: number) => (
                <View key={i} style={s.divider}>
                  <Select
                    label={`Dia do turno ${i + 1}`}
                    value={h.dia}
                    options={weekdays.map((d) => ({ label: d, value: d }))}
                    onChange={(v) =>
                      edit(
                        "horarios",
                        config.horarios.map((a: any, j: number) =>
                          i === j ? { ...a, dia: v } : a,
                        ),
                      )
                    }
                  />
                  {[
                    ["inicio", "Entrada"],
                    ["fim", "Saída"],
                  ].map(([k, label]) => (
                    <Input
                      key={k}
                      label={`${label} (HH:MM)`}
                      value={h[k]}
                      onChangeText={(v) =>
                        edit(
                          "horarios",
                          config.horarios.map((a: any, j: number) =>
                            i === j ? { ...a, [k]: v } : a,
                          ),
                        )
                      }
                    />
                  ))}
                  <Button
                    title="Remover turno"
                    variant="ghost"
                    onPress={() =>
                      edit(
                        "horarios",
                        config.horarios.filter((_: any, j: number) => i !== j),
                      )
                    }
                  />
                </View>
              ))}
              <Button
                title="Adicionar turno"
                variant="secondary"
                onPress={() =>
                  edit("horarios", [
                    ...(config.horarios ?? []),
                    { dia: "segunda", inicio: "08:00", fim: "12:00" },
                  ])
                }
              />
              <Heading>Preços específicos</Heading>
              {services
                .filter((v) =>
                  (config.ids_servicos_vinculados ?? []).includes(v.id_servico),
                )
                .map((v) => (
                  <Input
                    key={v.id_servico}
                    label={`${v.nome} · padrão ${money(v.preco)}`}
                    keyboardType="decimal-pad"
                    placeholder="Vazio usa o preço padrão"
                    value={String(
                      config.precos?.find(
                        (p: any) => p.id_servico === v.id_servico,
                      )?.preco ?? "",
                    )}
                    onChangeText={(price) =>
                      edit("precos", [
                        ...(config.precos ?? []).filter(
                          (p: any) => p.id_servico !== v.id_servico,
                        ),
                        ...(price === ""
                          ? []
                          : [{ id_servico: v.id_servico, preco: price }]),
                      ])
                    }
                  />
                ))}
              <Button
                title="Salvar profissional"
                loading={mut.busy}
                onPress={() => {
                  void mut.run(
                    () => {
                      const commission = Number(
                        String(config.comissao_valor).replace(",", "."),
                      );
                      const prices = (config.precos ?? []).map((p: any) => ({
                        ...p,
                        preco: Number(String(p.preco).replace(",", ".")),
                      }));
                      if (
                        !Number.isFinite(commission) ||
                        prices.some((p: any) => !Number.isFinite(p.preco))
                      )
                        throw new Error("Informe valores numéricos válidos.");
                      return api(
                        `/gestao/profissionais/${person.id_funcionario}/config`,
                        {
                          method: "PUT",
                          body: {
                            ...config,
                            comissao_valor: commission,
                            precos: prices,
                          },
                        },
                      );
                    },
                    async () => {
                      setDraft(null);
                      await state.reload();
                    },
                  );
                }}
              />
            </>
          )}
        </Resource>
      )}
    </Card>
  );
}
function TeamAccess({
  person,
  salon,
  refresh,
}: {
  person: any;
  salon: number;
  refresh: () => any;
}) {
  const mut = useMutation();
  return (
    <Card>
      <Heading>Acesso de {person.nome}</Heading>
      <Feedback state={mut} />
      <Button
        title={
          person.ativo === false
            ? "Reativar profissional"
            : "Desativar profissional"
        }
        variant={person.ativo === false ? "secondary" : "danger"}
        loading={mut.busy}
        onPress={() =>
          confirmAction(
            person.ativo === false
              ? "Reativar profissional?"
              : "Desativar profissional?",
            person.ativo === false
              ? "O profissional voltará a atender conforme seus turnos e serviços."
              : "O acesso será desativado. Havendo reservas futuras, será necessário remarcar ou cancelar primeiro.",
            () => {
              void mut.run(
                () =>
                  api(
                    `/barbearia/funcionarios/${person.id_funcionario}/estado`,
                    {
                      method: "PATCH",
                      body: { ativo: person.ativo === false },
                    },
                  ),
                refresh,
              );
            },
          )
        }
      />
      <Button
        title="Reenviar convite de acesso"
        variant="ghost"
        loading={mut.busy}
        onPress={() =>
          confirmAction(
            "Enviar convite?",
            "Será enviado um e-mail de ativação ao profissional cadastrado.",
            () => {
              void mut.run(
                async () => {
                  const data: any = await api(
                    `/barbearias/${salon}/funcionarios/${person.id_funcionario}/convite`,
                    { method: "POST" },
                  );
                  const failed = (data.convites ?? []).some(
                    (c: any) => c.email_enviado === false,
                  );
                  if (failed)
                    throw new Error(
                      "O convite foi gerado, mas o envio do e-mail falhou. Tente reenviar mais tarde.",
                    );
                },
                undefined,
                "Convite solicitado. Confira a caixa de entrada do profissional.",
              );
            },
          )
        }
      />
    </Card>
  );
}
function NewProfessional({
  refresh,
  services,
}: {
  refresh: () => any;
  services: any[];
}) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const mut = useMutation();
  return (
    <Card>
      <Heading>Cadastrar profissional</Heading>
      <Copy muted>
        O profissional receberá um convite por e-mail para criar sua senha.
        Configure os turnos depois do cadastro.
      </Copy>
      <Feedback state={mut} />
      <Button
        title={open ? "Fechar cadastro" : "Adicionar profissional"}
        variant="secondary"
        onPress={() => setOpen((v) => !v)}
      />
      {open && (
        <>
          <Heading>Serviços atendidos</Heading>
          <View style={s.row}>
            {services
              .filter(
                (v) => v.ativo !== false || selected.includes(v.id_servico),
              )
              .map((v) => (
                <Chip
                  key={v.id_servico}
                  active={selected.includes(v.id_servico)}
                  onPress={() =>
                    setSelected((a) =>
                      a.includes(v.id_servico)
                        ? a.filter((id) => id !== v.id_servico)
                        : v.ativo === false
                          ? a
                          : [...a, v.id_servico],
                    )
                  }
                >
                  {v.nome}
                  {v.ativo === false ? " · Inativo: toque para remover" : ""}
                </Chip>
              ))}
          </View>
          <Form
            fields={[
              { key: "nome", label: "Nome", required: true },
              {
                key: "descricao",
                label: "Sobre o profissional",
                type: "multiline",
              },
              {
                key: "email",
                label: "E-mail de acesso",
                type: "email",
                required: true,
              },
              { key: "telefone", label: "Telefone com DDD", required: true },
              {
                key: "comissao_percentual",
                label: "Comissão (%)",
                type: "number",
                required: true,
                min: 0,
                max: 100,
              },
            ]}
            initial={{
              nome: "",
              descricao: "",
              email: "",
              telefone: "",
              comissao_percentual: 0,
            }}
            busy={mut.busy}
            title="Cadastrar e enviar convite"
            onSubmit={(body) =>
              mut.run(
                async () => {
                  const result: any = await api("/barbearia/funcionarios", {
                    method: "POST",
                    body: { ...body, ids_servicos: selected },
                  });
                  if (result.convite_email_enviado === false)
                    showInformation(
                      "Profissional cadastrado",
                      "O e-mail de convite não pôde ser enviado. Use Reenviar convite de acesso depois.",
                    );
                },
                async () => {
                  setOpen(false);
                  setSelected([]);
                  await refresh();
                },
                "Profissional cadastrado. Configure os turnos para permitir agendamentos.",
              )
            }
          />
        </>
      )}
    </Card>
  );
}
function ServiceLinks({
  person,
  services,
  refresh,
}: {
  person: any;
  services: any[];
  refresh: () => any;
}) {
  const [selected, setSelected] = useState<number[]>(
    person.ids_servicos ?? person.servicos ?? [],
  );
  const mut = useMutation();
  return (
    <Card>
      <Heading>Serviços de {person.nome}</Heading>
      <Copy muted>
        Selecione quais serviços o profissional realiza. Remova os serviços
        inativos da seleção para salvar. Preços específicos ficam na
        configuração acima.
      </Copy>
      <Feedback state={mut} />
      <View style={s.row}>
        {services
          .filter((v) => v.ativo !== false || selected.includes(v.id_servico))
          .map((v) => (
            <Chip
              key={v.id_servico}
              active={selected.includes(v.id_servico)}
              onPress={() =>
                setSelected((a) =>
                  a.includes(v.id_servico)
                    ? a.filter((id) => id !== v.id_servico)
                    : v.ativo === false
                      ? a
                      : [...a, v.id_servico],
                )
              }
            >
              {v.nome}
              {v.ativo === false ? " · Inativo: toque para remover" : ""}
            </Chip>
          ))}
      </View>
      <Button
        title="Salvar serviços do profissional"
        variant="secondary"
        loading={mut.busy}
        onPress={() => {
          void mut.run(
            () =>
              api(`/barbearia/funcionarios/${person.id_funcionario}/servicos`, {
                method: "PUT",
                body: { ids_servicos: selected },
              }),
            refresh,
          );
        }}
      />
    </Card>
  );
}
export default function OwnerTeam() {
  const state = useResource<any>(
    query("/gestao/agenda", { inicio: today(), fim: today() }),
    null,
  );
  const services = useResource<any>("/barbearia/servicos", null);
  const [editor, setEditor] = useState<any>(null);
  const mut = useMutation();
  const list = services.data?.servicos ?? [];
  return (
    <Screen
      back
      title="Equipe e serviços"
      subtitle="Seu catálogo e a rotina dos profissionais."
      onRefresh={() => {
        void state.reload();
        void services.reload();
      }}
      refreshing={state.loading}
    >
      <Feedback state={mut} />
      <Button
        title="Adicionar serviço"
        onPress={() =>
          setEditor({
            nome: "",
            descricao: "",
            genero: "unissex",
            preco: "",
            duracao: 30,
          })
        }
      />
      {editor && (
        <Card>
          <Heading>
            {editor.id_servico ? "Editar serviço" : "Novo serviço"}
          </Heading>
          <Form
            key={editor.id_servico ?? "new"}
            fields={serviceFields}
            initial={editor}
            busy={mut.busy}
            title="Salvar serviço"
            onSubmit={(v) =>
              mut.run(
                () =>
                  api(
                    `/barbearia/servicos${editor.id_servico ? `/${editor.id_servico}` : ""}`,
                    { method: editor.id_servico ? "PUT" : "POST", body: v },
                  ),
                async () => {
                  setEditor(null);
                  await services.reload();
                  await state.reload();
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
      <Heading>Serviços do salão</Heading>
      <Resource state={services} empty={!!services.data && !list.length}>
        {list.map((v: any) => (
          <Card key={v.id_servico}>
            <Badge>{v.ativo === false ? "Inativo" : "Ativo"}</Badge>
            <Heading>{v.nome}</Heading>
            <Copy>
              {money(v.preco)} · {v.duracao} minutos
            </Copy>
            <Copy muted>{v.descricao}</Copy>
            <Button
              title="Editar serviço"
              variant="secondary"
              onPress={() => setEditor(v)}
            />
            <Button
              title={v.ativo === false ? "Ativar serviço" : "Desativar serviço"}
              variant="ghost"
              disabled={mut.busy}
              onPress={() => {
                void mut.run(
                  () =>
                    api(`/gestao/servicos/${v.id_servico}/ativo`, {
                      method: "PUT",
                      body: { ativo: v.ativo === false },
                    }),
                  services.reload,
                );
              }}
            />
          </Card>
        ))}
      </Resource>
      <Heading>Profissionais</Heading>
      <NewProfessional refresh={state.reload} services={list} />
      <Resource state={state}>
        {(state.data?.funcionarios ?? []).map((p: any) => (
          <View key={p.id_funcionario} style={s.spacer}>
            <Professional
              key={`${p.id_funcionario}:${(p.ids_servicos ?? p.servicos ?? []).join(",")}`}
              person={p}
              services={list}
            />
            <ServiceLinks
              key={`links:${p.id_funcionario}:${(p.ids_servicos ?? p.servicos ?? []).join(",")}`}
              person={p}
              services={list}
              refresh={state.reload}
            />
            <TeamAccess
              person={p}
              salon={state.data.id_barbearia}
              refresh={state.reload}
            />
          </View>
        ))}
      </Resource>
      <Card>
        <Heading>Compartilhar agendamento</Heading>
        <Copy muted>Compartilhe o identificador público da sua barbearia.</Copy>
        <Button
          title="Compartilhar link da barbearia"
          variant="secondary"
          onPress={() => {
            const web = process.env.EXPO_PUBLIC_WEB_URL;
            if (!web) {
              showInformation(
                "Link público indisponível",
                "Configure EXPO_PUBLIC_WEB_URL com o endereço público do site para compartilhar o agendamento.",
              );
              return;
            }
            void Share.share({
              message: `Cortaê · Agende na nossa barbearia: ${web.replace(/\/+$/, "")}/selecionar-servicos?barbearia=${state.data?.id_barbearia}`,
            });
          }}
        />
      </Card>
    </Screen>
  );
}
