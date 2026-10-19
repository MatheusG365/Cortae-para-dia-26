import React, { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useResource } from "../../lib/useResource";
import { assetUrl, query } from "../../lib/api";
import { Button, Card, Empty, Input, RemoteImage, Screen } from "../../ui";
import { colors, fonts } from "../../theme";
import { Heading, Label, ProductCard, Resource, go, money, s } from "./common";
export function Discover() {
  const state = useResource("/barbearias-disponiveis", []);
  const [search, setSearch] = useState("");
  const list = (
    Array.isArray(state.data) ? state.data : state.data.barbearias || []
  ).filter((b) => String(b.nome).toLowerCase().includes(search.toLowerCase()));
  return (
    <Screen
      title="Selecione a Barbearia"
      back
      refreshing={state.loading}
      onRefresh={state.reload}
    >
      <Input
        accessibilityLabel="Buscar barbearia"
        placeholder="Buscar barbearia..."
        leadingIcon="search-outline"
        value={search}
        onChangeText={setSearch}
      />
      <Text style={layout.caption}>BARBEARIAS DISPONÍVEIS</Text>
      <Resource state={state}>
        {list.map((b) => (
          <Card key={b.id || b.id_barbearia} style={layout.shop}>
            <RemoteImage
              uri={assetUrl(b.imagem || b.logo)}
              style={layout.photo}
              accessibilityLabel={b.nome}
            />
            <View style={layout.details}>
              <Text style={layout.name}>{b.nome}</Text>
              <Label muted>
                {b.endereco ||
                  "Consulte o endereço na página do estabelecimento"}
              </Label>
              <Label>{b.horario}</Label>
              <Button
                title={
                  b.personalizada === false
                    ? "Em configuração"
                    : "Agendar Agora"
                }
                disabled={b.personalizada === false}
                onPress={() =>
                  go(`/cliente/barbearia/${b.id || b.id_barbearia}`)
                }
              />
            </View>
          </Card>
        ))}
        {!list.length && (
          <Empty
            title="Nenhuma barbearia encontrada"
            message="Tente outro nome ou atualize a lista."
          />
        )}
      </Resource>
      <Button
        title="Explorar todas as lojas"
        variant="secondary"
        onPress={() => go("/cliente/loja")}
      />
    </Screen>
  );
}
const layout = StyleSheet.create({
  caption: {
    color: colors.muted,
    fontFamily: fonts.medium,
    fontSize: 10,
    letterSpacing: 1.2,
    marginTop: 3,
  },
  shop: { padding: 0, overflow: "hidden", gap: 0 },
  photo: { height: 174, borderRadius: 0 },
  details: { padding: 14, gap: 8 },
  name: {
    color: colors.text,
    fontFamily: fonts.bold,
    fontSize: 16,
    lineHeight: 22,
  },
});
export function Establishment() {
  const { id } = useLocalSearchParams();
  const state = useResource(
    query("/barbearia/personalizacao", { id_usuario: id }),
    {},
  );
  const services = useResource(
    query("/barbearia/servicos", { id_usuario: id }),
    {},
  );
  const shop = useResource(`/marketplace/barbearias/${id}`, {});
  const d = state.data;
  const personal = d.personalizacao || {};
  const accent = /^#[0-9a-f]{3,6}$/i.test(personal.cor_primaria || "")
    ? personal.cor_primaria
    : colors.accent;
  return (
    <Screen
      title={d.nome_barbearia || "Barbearia"}
      subtitle="Serviços, profissionais e loja em um só lugar"
      back
      refreshing={state.loading}
      onRefresh={() => {
        state.reload();
        services.reload();
        shop.reload();
      }}
    >
      <Resource state={state}>
        <View
          style={{
            borderBottomWidth: 4,
            borderBottomColor: accent,
            borderRadius: 22,
          }}
        >
          <RemoteImage
            uri={assetUrl(d.fotos?.[0]?.url || d.logo)}
            style={s.hero}
          />
        </View>
        <View
          style={{
            borderLeftColor: accent,
            borderLeftWidth: 4,
            paddingLeft: 14,
            gap: 5,
          }}
        >
          <Heading>{d.nome_barbearia || "Conheça o estabelecimento"}</Heading>
          <Label muted>{personal.localizacao}</Label>
          <Label>{personal.historia}</Label>
          <Label muted>
            {personal.contato_telefone} · {personal.contato_email}
          </Label>
        </View>
        <Button
          accent={accent}
          title="Escolher serviços e agendar"
          onPress={() => go("/cliente/servicos", { barbearia: id })}
        />
        <Heading>Serviços para você</Heading>
        <Resource state={services}>
          {(services.data.servicos || []).map((v) => (
            <Card key={v.id_servico}>
              <Heading>{v.nome}</Heading>
              <Label>
                {money(v.preco)} · {v.duracao} minutos
              </Label>
              <Button
                accent={accent}
                title="Agendar serviço"
                onPress={() =>
                  go("/cliente/servicos", {
                    barbearia: id,
                    selecionado: v.id_servico,
                  })
                }
              />
            </Card>
          ))}
        </Resource>
        <Heading>Quem cuida de você</Heading>
        {(d.funcionarios || []).map((f) => (
          <Card key={f.id_funcionario}>
            <Heading>{f.nome}</Heading>
            <Label muted>{f.descricao || "Profissional da equipe"}</Label>
            <Button
              accent={accent}
              title="Agendar com este profissional"
              onPress={() =>
                go("/cliente/servicos", {
                  barbearia: id,
                  funcionario: f.id_funcionario,
                })
              }
            />
          </Card>
        ))}
        <Heading>Loja · {d.nome_barbearia}</Heading>
        <View style={{ height: 3, backgroundColor: accent, borderRadius: 2 }} />
        <Resource state={shop} empty={!shop.data.produtos?.length}>
          {(shop.data.produtos || []).map((product) => (
            <ProductCard
              key={product.id_produto}
              product={product}
              accent={accent}
            />
          ))}
        </Resource>
        <Button
          title="Ver produtos de todas as lojas"
          variant="ghost"
          onPress={() => go("/cliente/loja")}
        />
      </Resource>
    </Screen>
  );
}
