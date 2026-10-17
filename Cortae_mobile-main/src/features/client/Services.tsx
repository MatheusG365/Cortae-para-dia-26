import React, { useState } from "react";
import { View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { query } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, Screen } from "../../ui";
import { Data, Heading, Label, Resource, go, money, s } from "./common";
export default function Services() {
  const p = useLocalSearchParams<{
    barbearia: string;
    funcionario: string;
    selecionado: string;
  }>();
  const state = useResource<Data>(
    query("/barbearia/servicos", { id_usuario: p.barbearia }),
    {},
  );
  const [ids, setIds] = useState<string[]>(
    p.selecionado ? [String(p.selecionado)] : [],
  );
  const values = (state.data.servicos || []).filter((v: Data) =>
    ids.includes(String(v.id_servico)),
  );
  function next() {
    const names = values.map((v: Data) => v.nome.toLowerCase()).join(" ");
    const painting = /pintar|color|tinta/.test(names);
    go("/cliente/visagismo", {
      barbearia: p.barbearia,
      funcionario: p.funcionario || "",
      servicos: ids.join(","),
      tem_pintar: painting ? "true" : "false",
      apenas_cor:
        painting &&
        !/corte|barba|bigode|progressiva|alisamento|hidrat/.test(names)
          ? "true"
          : "false",
      alvo:
        painting && /barba/.test(names)
          ? /cabelo/.test(names)
            ? "ambos"
            : "barba"
          : "cabelo",
    });
  }
  return (
    <Screen
      title="Seu atendimento"
      subtitle="Escolha os serviços que combinam com seu momento"
      back
    >
      <Resource state={state} empty={!state.data.servicos?.length}>
        {(state.data.servicos || []).map((v: Data) => {
          const selected = ids.includes(String(v.id_servico));
          return (
            <View key={v.id_servico} style={selected ? s.selected : undefined}>
              <Card>
                <Heading>{v.nome}</Heading>
                <Label muted>
                  {v.duracao} minutos · {v.genero || "Unissex"}
                </Label>
                <Heading>{money(v.preco)}</Heading>
                <Button
                  title={selected ? "✓ Selecionado" : "Adicionar serviço"}
                  variant={selected ? "primary" : "secondary"}
                  onPress={() =>
                    setIds((old) =>
                      selected
                        ? old.filter((id) => id !== String(v.id_servico))
                        : [...old, String(v.id_servico)],
                    )
                  }
                />
              </Card>
            </View>
          );
        })}
      </Resource>
      <Card>
        <Label>
          {ids.length} serviço(s) ·{" "}
          {values.reduce(
            (sum: number, v: Data) => sum + Number(v.duracao || 0),
            0,
          )}{" "}
          minutos
        </Label>
        <Heading>
          {money(
            values.reduce(
              (sum: number, v: Data) => sum + Number(v.preco || 0),
              0,
            ),
          )}
        </Heading>
        <Label muted>
          O preço final considera o profissional escolhido na próxima etapa.
        </Label>
        <Button
          title="Continuar para escolha do visual"
          disabled={!ids.length}
          onPress={next}
        />
      </Card>
    </Screen>
  );
}
