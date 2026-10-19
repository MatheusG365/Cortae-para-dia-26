import React from "react";
import { Tabs } from "expo-router";
import Ionicons from "@expo/vector-icons/Ionicons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, fonts } from "../../theme";
export default function OwnerTabs() {
  const insets = useSafeAreaInsets();
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.muted,
        sceneStyle: { backgroundColor: colors.background },
        tabBarStyle: {
          backgroundColor: "#131518",
          borderTopColor: colors.border,
          height: 64 + insets.bottom,
          paddingTop: 9,
          paddingBottom: Math.max(9, insets.bottom),
        },
        tabBarLabelStyle: {
          fontFamily: fonts.semibold,
          fontSize: 10,
          marginTop: 3,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Visão geral",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="grid-outline" color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="agenda"
        options={{
          title: "Agenda",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="calendar-outline" color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="loja"
        options={{
          title: "Minha loja",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="storefront-outline" color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="mais"
        options={{
          title: "Gestão",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="options-outline" color={color} size={size} />
          ),
        }}
      />
      {[
        "novo-agendamento",
        "equipe",
        "clientes",
        "financeiro",
        "ranking",
        "metas",
        "relatorios",
        "pedidos",
        "pedido",
        "perfil",
        "produto",
        "variacoes",
        "estoque",
        "fornecedores",
        "cupons",
        "vendas",
        "entregas",
      ].map((name) => (
        <Tabs.Screen key={name} name={name} options={{ href: null }} />
      ))}
    </Tabs>
  );
}
