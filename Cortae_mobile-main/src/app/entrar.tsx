import React, { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { router } from "expo-router";
import { Button, Card, Input, Notice, RemoteImage, Screen } from "../ui";
import { ApiError } from "../lib/api";
import { useSession } from "../lib/session";
import { authStyles as s } from "../features/auth/styles";
import { errorText, validEmail } from "../features/auth/validation";
import { useMobileAsset } from "../lib/useMobileAsset";

export default function Entrar() {
  const { signIn } = useSession();
  const logoUri = useMobileAsset("logo");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [verify, setVerify] = useState(false);
  async function submit() {
    if (!validEmail(email) || !senha) {
      setError("Informe um e-mail válido e sua senha.");
      return;
    }
    setBusy(true);
    setError("");
    setVerify(false);
    try {
      const user = await signIn(email, senha);
      router.replace(user.tipo === 2 ? "/barbearia" : "/cliente");
    } catch (problem) {
      setError(errorText(problem));
      setVerify(
        problem instanceof ApiError && problem.data?.email_confirmacao === true,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen
      title="Seu estilo começa aqui"
      subtitle="Entre para cuidar de você ou do seu negócio."
      back
    >
      <RemoteImage
        uri={logoUri}
        style={s.logo}
        accessibilityLabel="Cortaê"
        fallback="CORTAÊ"
      />
      <Card>
        <View style={s.section}>
          <Text style={s.title}>Bem-vindo de volta</Text>
          {error ? <Notice message={error} kind="error" /> : null}
          <Input
            label="E-mail"
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
          />
          <Input
            label="Senha"
            password
            value={senha}
            onChangeText={setSenha}
            autoComplete="current-password"
            onSubmitEditing={() => void submit()}
          />
          <Pressable
            onPress={() => router.push("/recuperar-senha")}
            accessibilityRole="link"
          >
            <Text style={s.link}>Esqueci minha senha</Text>
          </Pressable>
          <Button
            title="Entrar"
            onPress={() => void submit()}
            loading={busy}
            disabled={busy}
          />
          {verify ? (
            <Button
              title="Confirmar meu e-mail"
              variant="secondary"
              onPress={() =>
                router.push({
                  pathname: "/verificar-codigo",
                  params: { email: email.trim() },
                })
              }
            />
          ) : null}
        </View>
      </Card>
      <Button
        title="Criar uma conta"
        variant="secondary"
        onPress={() => router.push("/cadastro")}
      />
    </Screen>
  );
}
