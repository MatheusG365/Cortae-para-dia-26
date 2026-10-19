import React, { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { router } from "expo-router";
import { Button, Input, Notice } from "../ui";
import { ApiError } from "../lib/api";
import { useSession } from "../lib/session";
import { authStyles as s } from "../features/auth/styles";
import { errorText, validEmail } from "../features/auth/validation";
import AuthScreen from "../features/auth/AuthScreen";
export default function Entrar() {
  const { signIn } = useSession();
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
    <AuthScreen>
      <View style={s.section}>
        {error ? <Notice message={error} kind="error" /> : null}
        <Input
          label="E-MAIL"
          labelStyle={s.fieldLabel}
          accessibilityLabel="E-mail"
          placeholder="Digite seu e-mail"
          leadingIcon="mail-outline"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoComplete="email"
        />
        <Input
          label="SENHA"
          labelStyle={s.fieldLabel}
          accessibilityLabel="Senha"
          placeholder="Digite sua senha"
          leadingIcon="lock-closed-outline"
          password
          value={senha}
          onChangeText={setSenha}
          autoComplete="current-password"
          onSubmitEditing={() => void submit()}
        />
      </View>
      <Pressable
        style={s.forgot}
        onPress={() => router.push("/recuperar-senha")}
        accessibilityRole="link"
      >
        <Text style={s.forgotText}>Esqueceu a senha?</Text>
      </Pressable>
      <View style={s.loginActions}>
        <Button
          title="Entrar na Conta"
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
        <Button
          title="Criar Conta"
          variant="ghost"
          style={s.outlineButton}
          onPress={() => router.push("/cadastro")}
        />
      </View>
    </AuthScreen>
  );
}
