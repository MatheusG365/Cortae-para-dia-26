import React, { useState } from "react";
import { validQuantity } from "./clientRules";
import { View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { api, assetUrl } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, Input, RemoteImage, Screen, Select } from "../../ui";
import { colors } from "../../theme";
import {
  Feedback,
  Heading,
  Label,
  ProductCard,
  Resource,
  go,
  money,
  s,
  useAction,
} from "./common";
export default function Product() {
  const { id } = useLocalSearchParams();
  const state = useResource(`/marketplace/produtos/${id}`, {});
  const action = useAction();
  const [variant, setVariant] = useState(""),
    [quantity, setQuantity] = useState("1"),
    [note, setNote] = useState("5"),
    [comment, setComment] = useState(""),
    [image, setImage] = useState(0);
  const p = state.data.produto;
  const brand = useResource(
    p?.id_barbearia ? `/marketplace/barbearias/${p.id_barbearia}/perfil` : null,
    {},
  );
  const accent = /^#[0-9a-f]{3,6}$/i.test(
    brand.data.personalizacao?.cor_primaria || "",
  )
    ? brand.data.personalizacao.cor_primaria
    : colors.accent;
  const chosen = p?.variacoes?.find((v) => String(v.id_variacao) === variant);
  const stock = (chosen?.estoque ?? (p?.tem_variacoes ? 0 : p?.estoque)) || 0;
  async function mutate(path, body, message) {
    await action.run(async () => {
      await api(path, { method: "PUT", body });
      await state.reload();
    }, message);
  }
  return (
    <Screen
      title={p?.nome || "Detalhes do produto"}
      subtitle={p?.barbearia || "Conheça os detalhes antes de comprar"}
      back
    >
      <Feedback state={action} />
      <Resource state={state}>
        {p && (
          <>
            <RemoteImage uri={assetUrl(p.imagens?.[image])} style={s.hero} />
            <View style={s.wrap}>
              {(p.imagens || []).map((uri, index) => (
                <Button
                  key={uri + index}
                  title={`Foto ${index + 1}`}
                  variant="ghost"
                  onPress={() => setImage(index)}
                />
              ))}
            </View>
            <Label muted>
              {p.categoria} · {p.marca}
            </Label>
            <Heading>{p.nome}</Heading>
            <Label>{p.descricao}</Label>
            <Label>
              ★ {Number(p.media_avaliacoes || 0).toFixed(1)} ·{" "}
              {p.total_avaliacoes || 0} avaliações
            </Label>
            <Heading>{money(chosen?.preco ?? p.preco)}</Heading>
            {p.tem_variacoes && (
              <Select
                label="Tamanho, cor ou volume"
                value={variant}
                onChange={(v) => {
                  setVariant(v);
                  setQuantity("1");
                }}
                options={[
                  { label: "Selecione uma variação", value: "" },
                  ...(p.variacoes || [])
                    .filter((v) => v.ativo !== false)
                    .map((v) => ({
                      label: `${v.nome} · ${[v.tamanho, v.cor, v.volume].filter(Boolean).join(" / ")} · ${money(v.preco)} · estoque ${v.estoque}`,
                      value: String(v.id_variacao),
                    })),
                ]}
              />
            )}
            <Label muted>
              {stock > 0
                ? `${stock} unidade(s) em estoque`
                : p.tem_variacoes && !chosen
                  ? "Selecione uma variação"
                  : "Esgotado"}
            </Label>
            <Input
              label="Quantidade"
              keyboardType="number-pad"
              value={quantity}
              onChangeText={setQuantity}
            />
            <Button
              accent={accent}
              title="Adicionar ao carrinho"
              loading={action.busy}
              disabled={!validQuantity(quantity, stock)}
              onPress={() =>
                mutate(
                  `/marketplace/carrinho/${id}`,
                  {
                    quantidade: Number(quantity),
                    adicionar: true,
                    id_variacao: chosen?.id_variacao ?? null,
                  },
                  "Produto adicionado ao carrinho.",
                )
              }
            />
            <View style={s.wrap}>
              <Button
                title={p.favorito ? "♥ Favoritado" : "♡ Favoritar"}
                variant="secondary"
                disabled={action.busy}
                onPress={() =>
                  mutate(
                    `/marketplace/favoritos/${id}`,
                    { favorito: !p.favorito },
                    p.favorito
                      ? "Removido dos favoritos."
                      : "Adicionado aos favoritos.",
                  )
                }
              />
              <Button
                title={
                  p.desejado ? "✓ Na lista de desejos" : "Guardar para depois"
                }
                variant="secondary"
                disabled={action.busy}
                onPress={() =>
                  mutate(
                    `/marketplace/lista-desejos/${id}`,
                    { desejado: !p.desejado },
                    "Lista de desejos atualizada.",
                  )
                }
              />
            </View>
            <Button
              title="Ver carrinho"
              variant="ghost"
              onPress={() => go("/cliente/carrinho")}
            />
            <Card>
              <Heading>Sobre o produto</Heading>
              <Label>
                {p.detalhes ||
                  p.descricao ||
                  "Nenhum detalhe adicional informado."}
              </Label>
              <Button
                title={`Conhecer a loja de ${p.barbearia}`}
                variant="ghost"
                onPress={() => go(`/cliente/barbearia/${p.id_barbearia}`)}
              />
            </Card>
            <Heading>Avaliações de quem comprou</Heading>
            {(state.data.avaliacoes || []).map((a, i) => (
              <Card key={a.id_avaliacao ?? i}>
                <Heading>
                  ★ {a.nota}/5 · {a.cliente || a.nome || "Cliente"}
                </Heading>
                <Label>{a.comentario || "Sem comentário"}</Label>
              </Card>
            ))}
            {(p.pode_avaliar || state.data.pode_avaliar) && (
              <Card>
                <Heading>Avalie sua compra</Heading>
                <Label muted>Disponível para quem recebeu este produto.</Label>
                <Select
                  label="Nota"
                  value={note}
                  onChange={setNote}
                  options={[5, 4, 3, 2, 1].map((n) => ({
                    label: `${n} estrelas`,
                    value: String(n),
                  }))}
                />
                <Input
                  label="Comentário"
                  value={comment}
                  onChangeText={setComment}
                  multiline
                  maxLength={1000}
                />
                <Button
                  title="Salvar avaliação"
                  loading={action.busy}
                  onPress={() =>
                    mutate(
                      `/marketplace/produtos/${id}/avaliacao`,
                      { nota: Number(note), comentario: comment },
                      "Avaliação salva.",
                    )
                  }
                />
              </Card>
            )}
            {state.data.relacionados?.length > 0 && (
              <Heading>Você também pode gostar</Heading>
            )}
            {(state.data.relacionados || []).map((v) => (
              <ProductCard key={v.id_produto} product={v} accent={accent} />
            ))}
          </>
        )}
      </Resource>
    </Screen>
  );
}
