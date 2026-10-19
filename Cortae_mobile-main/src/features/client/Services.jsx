import React, { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";
import { colors, fonts } from "../../theme";
import { useLocalSearchParams } from "expo-router";
import { query } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, Screen } from "../../ui";
import { Heading, Label, Resource, go, money } from "./common";
export default function Services() {
  const p = useLocalSearchParams();
  const state = useResource(
    query("/barbearia/servicos", { id_usuario: p.barbearia }),
    {},
  );
  const [ids, setIds] = useState(p.selecionado ? [String(p.selecionado)] : []);
  const values = (state.data.servicos || []).filter((v) =>
    ids.includes(String(v.id_servico)),
  );
  function next() {
    const names = values.map((v) => v.nome.toLowerCase()).join(" ");
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
    <Screen title="Selecionar Serviços" back>
      <Resource state={state} empty={!state.data.servicos?.length}>
        {(state.data.servicos || []).map((v) => {
          const selected = ids.includes(String(v.id_servico));
          return (
            <Pressable
              key={v.id_servico}
              accessibilityRole="checkbox"
              accessibilityLabel={v.nome}
              accessibilityState={{ checked: selected }}
              style={[layout.option, selected && layout.selected]}
              onPress={() =>
                setIds((old) =>
                  selected
                    ? old.filter((id) => id !== String(v.id_servico))
                    : [...old, String(v.id_servico)],
                )
              }
            >
              <View style={layout.details}>
                <Text style={layout.name}>{v.nome}</Text>
                <Text style={layout.meta}>
                  {v.duracao} minutos · {v.genero || "Unissex"}
                </Text>
                <Text style={layout.price}>{money(v.preco)}</Text>
              </View>
              <Ionicons
                name={selected ? "checkbox" : "add-circle-outline"}
                size={24}
                color={selected ? colors.accent : colors.muted}
              />
            </Pressable>
          );
        })}
      </Resource>
      <Card>
        <Label>
          {ids.length} serviço(s) ·{" "}
          {values.reduce((sum, v) => sum + Number(v.duracao || 0), 0)} minutos
        </Label>
        <Heading>
          {money(values.reduce((sum, v) => sum + Number(v.preco || 0), 0))}
        </Heading>
        <Label muted>
          O preço final considera o profissional escolhido na próxima etapa.
        </Label>
        <Button title="Continuar" disabled={!ids.length} onPress={next} />
      </Card>
    </Screen>
  );
}
const layout = StyleSheet.create({
  option: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    backgroundColor: colors.surfaceAlt,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 16,
  },
  selected: { borderColor: colors.accent, backgroundColor: "#FF8A0009" },
  details: { flex: 1, gap: 6 },
  name: { color: colors.text, fontFamily: fonts.semibold, fontSize: 14 },
  meta: { color: colors.muted, fontFamily: fonts.regular, fontSize: 11 },
  price: { color: colors.accent, fontFamily: fonts.semibold, fontSize: 13 },
});
