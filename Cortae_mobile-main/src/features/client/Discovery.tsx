import React, { useState } from "react";
import { Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useSession } from "../../lib/session";
import { useResource } from "../../lib/useResource";
import { assetUrl, query } from "../../lib/api";
import { Button, Card, Empty, Input, RemoteImage, Screen } from "../../ui";
import { colors } from "../../theme";
import {
  Data,
  Heading,
  Label,
  ProductCard,
  Resource,
  go,
  money,
  s,
} from "./common";
export function Discover() {
  const { user } = useSession();
  const state = useResource<any>("/barbearias-disponiveis", []);
  const [search, setSearch] = useState("");
  const list = (
    Array.isArray(state.data) ? state.data : state.data.barbearias || []
  ).filter((b: Data) =>
    String(b.nome).toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <Screen
      title={`Olá, ${user?.nome?.split(" ")[0] || "bem-vindo"} 👋`}
      subtitle="Seu próximo estilo começa aqui."
      refreshing={state.loading}
      onRefresh={state.reload}
    >
      <Card>
        <Label muted>CORTAÊ · SEU MOMENTO</Label>
        <Text style={[s.heading, { fontSize: 30, lineHeight: 38 }]}>
          Cuide do seu estilo. Reserve seu momento.
        </Text>
        <Label muted>
          Encontre sua barbearia e escolha quem cuida de você.
        </Label>
      </Card>
      <Input
        label="Encontre uma barbearia"
        placeholder="Nome do estabelecimento"
        value={search}
        onChangeText={setSearch}
      />
      <Heading>Explore estabelecimentos</Heading>
      <Resource state={state}>
        {list.map((b: Data) => (
          <Card key={b.id || b.id_barbearia}>
            <RemoteImage uri={assetUrl(b.imagem || b.logo)} style={s.hero} />
            <Heading>{b.nome}</Heading>
            <Label muted>
              {b.endereco || "Consulte o endereço na página do estabelecimento"}
            </Label>
            <Label>
              {b.dias} · {b.horario}
            </Label>
            <Button
              title={
                b.personalizada === false
                  ? "Em configuração"
                  : "Conhecer barbearia"
              }
              disabled={b.personalizada === false}
              onPress={() => go(`/cliente/barbearia/${b.id || b.id_barbearia}`)}
            />
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
export function Establishment() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const state = useResource<Data>(
    query("/barbearia/personalizacao", { id_usuario: id }),
    {},
  );
  const services = useResource<Data>(
    query("/barbearia/servicos", { id_usuario: id }),
    {},
  );
  const shop = useResource<Data>(`/marketplace/barbearias/${id}`, {});
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
          {(services.data.servicos || []).map((v: Data) => (
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
        {(d.funcionarios || []).map((f: Data) => (
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
          {(shop.data.produtos || []).map((product: Data) => (
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
