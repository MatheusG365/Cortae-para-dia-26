import React, { useState } from "react";
import { Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { Button, Card, Input, Notice, Screen } from "../ui";
import { api, messageFrom } from "../lib/api";
import { authStyles as s } from "../features/auth/styles";
import { errorText, validEmail } from "../features/auth/validation";
export default function VerificarCodigo() {
  const params = useLocalSearchParams();
  const [email, setEmail] = useState(
    typeof params.email === "string" ? params.email : "",
  );
  const [codigo, setCodigo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  async function submit() {
    if (!validEmail(email) || !/^\d{6}$/.test(codigo)) {
      setError("Informe o e-mail e o código de 6 números.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await api("/verificar-codigo", {
        method: "POST",
        body: { email: email.trim(), codigo },
      });
      setSuccess(messageFrom(response));
    } catch (error) {
      setError(errorText(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen
      title="Confirme seu e-mail"
      subtitle="Falta pouco para começar."
      back
    >
      <Card>
        <View style={s.section}>
          <Text style={s.body}>
            Digite o código enviado para seu e-mail. Confira também a pasta de
            spam.
          </Text>
          {error ? <Notice message={error} kind="error" /> : null}
          {success ? <Notice message={success} kind="success" /> : null}
          <Input
            label="E-mail da conta"
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            editable={!success}
          />
          <Input
            label="Código de confirmação"
            value={codigo}
            onChangeText={(value) => setCodigo(value.replace(/\D/g, ""))}
            keyboardType="number-pad"
            maxLength={6}
            autoComplete="one-time-code"
            editable={!success}
          />
          {success ? (
            <Button
              title="Ir para o login"
              onPress={() => router.replace("/entrar")}
            />
          ) : (
            <Button
              title="Confirmar e-mail"
              onPress={() => void submit()}
              loading={busy}
              disabled={busy}
            />
          )}
        </View>
      </Card>
      <Text style={s.hint}>
        Não recebeu o código? Tente entrar novamente para solicitar o reenvio
        pelo sistema.
      </Text>
      <Button
        title="Voltar para o login"
        variant="ghost"
        onPress={() => router.replace("/entrar")}
      />
    </Screen>
  );
}
