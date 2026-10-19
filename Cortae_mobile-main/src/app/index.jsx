import React from "react";
import { Redirect } from "expo-router";
import { useSession } from "../lib/session";
export default function Index() {
  const { user } = useSession();
  return (
    <Redirect
      href={
        user?.tipo === 2
          ? "/barbearia"
          : user?.tipo === 1
            ? "/cliente"
            : "/entrar"
      }
    />
  );
}
