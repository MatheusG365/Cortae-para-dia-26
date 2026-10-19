import React from "react";
import { router } from "expo-router";
import { Screen, Empty, Button } from "../ui";
export default function NotFound() {
  return (
    <Screen title="Página não encontrada">
      <Empty
        title="Esse caminho não existe no aplicativo."
        action={
          <Button
            title="Voltar ao início"
            onPress={() => router.replace("/")}
          />
        }
      />
    </Screen>
  );
}
