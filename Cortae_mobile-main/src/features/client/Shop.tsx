import React, { useState } from "react";
import { FlatList, View } from "react-native";
import { query } from "../../lib/api";
import { useResource } from "../../lib/useResource";
import { Button, Card, Empty, Input, Screen, Select } from "../../ui";
import { Data, ProductCard, Resource, go, s } from "./common";
export default function Shop({
  mode = "all",
}: {
  mode?: "all" | "favorites" | "wishlist";
}) {
  const [search, setSearch] = useState(""),
    [filters, setFilters] = useState({
      busca: "",
      categoria: "",
      id_barbearia: "",
      ordem: "recentes",
      destaque: "",
    });
  const path =
    mode === "favorites"
      ? "/marketplace/favoritos"
      : mode === "wishlist"
        ? "/marketplace/lista-desejos"
        : query("/marketplace/produtos", filters);
  const state = useResource<Data>(path, {});
  return (
    <Screen
      title={
        mode === "favorites"
          ? "Seus favoritos"
          : mode === "wishlist"
            ? "Lista de desejos"
            : "Sua rotina de cuidados"
      }
      subtitle={
        mode === "all"
          ? "Produtos das barbearias. Seu cuidado continua em casa."
          : "Produtos que você escolheu guardar"
      }
      scroll={false}
    >
      <Resource state={state}>
        <FlatList
          data={state.data.produtos || []}
          keyExtractor={(item: Data) => String(item.id_produto)}
          renderItem={({ item }: { item: Data }) => (
            <ProductCard product={item} />
          )}
          refreshing={state.loading}
          onRefresh={state.reload}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={{ gap: 16, paddingBottom: 28 }}
          initialNumToRender={6}
          maxToRenderPerBatch={5}
          windowSize={5}
          ListEmptyComponent={
            <Empty
              title="Nenhum produto encontrado"
              message="Tente ajustar os filtros ou confira novamente mais tarde."
            />
          }
          ListHeaderComponent={
            <View style={{ gap: 16 }}>
              <View style={s.wrap}>
                <Button
                  title="Carrinho"
                  variant="secondary"
                  onPress={() => go("/cliente/carrinho")}
                />
                <Button
                  title="Meus pedidos"
                  variant="secondary"
                  onPress={() => go("/cliente/pedidos")}
                />
                <Button
                  title="Favoritos"
                  variant="ghost"
                  onPress={() => go("/cliente/favoritos")}
                />
                <Button
                  title="Desejos"
                  variant="ghost"
                  onPress={() => go("/cliente/desejos")}
                />
              </View>
              {mode === "all" && (
                <Card>
                  <Input
                    label="O que procura?"
                    placeholder="Produto, marca ou descrição"
                    value={search}
                    onChangeText={setSearch}
                  />
                  <Button
                    title="Buscar produtos"
                    variant="secondary"
                    onPress={() => setFilters((v) => ({ ...v, busca: search }))}
                  />
                  <Select
                    label="Loja"
                    value={filters.id_barbearia}
                    onChange={(v: string) =>
                      setFilters((f) => ({ ...f, id_barbearia: v }))
                    }
                    options={[
                      { label: "Todas as lojas", value: "" },
                      ...(state.data.barbearias || []).map((b: Data) => ({
                        label: b.nome,
                        value: String(b.id_barbearia ?? b.id),
                      })),
                    ]}
                  />
                  <Select
                    label="Categoria"
                    value={filters.categoria}
                    onChange={(v: string) =>
                      setFilters((f) => ({ ...f, categoria: v }))
                    }
                    options={[
                      { label: "Todas as categorias", value: "" },
                      ...(state.data.categorias || []).map((v: string) => ({
                        label: v,
                        value: v,
                      })),
                    ]}
                  />
                  <Select
                    label="Ordenar"
                    value={filters.ordem}
                    onChange={(v: string) =>
                      setFilters((f) => ({ ...f, ordem: v }))
                    }
                    options={[
                      { label: "Mais recentes", value: "recentes" },
                      { label: "Menor preço", value: "preco_asc" },
                      { label: "Maior preço", value: "preco_desc" },
                      { label: "Nome", value: "nome" },
                    ]}
                  />
                  <Select
                    label="Destaques"
                    value={filters.destaque}
                    onChange={(v: string) =>
                      setFilters((f) => ({ ...f, destaque: v }))
                    }
                    options={[
                      { label: "Todos os produtos", value: "" },
                      { label: "Em promoção", value: "promocoes" },
                      { label: "Lançamentos", value: "lancamentos" },
                    ]}
                  />
                </Card>
              )}
            </View>
          }
          ListFooterComponent={
            mode !== "all" ? (
              <Button
                title="Explorar todos os produtos"
                onPress={() => go("/cliente/loja")}
              />
            ) : null
          }
        />
      </Resource>
    </Screen>
  );
}
