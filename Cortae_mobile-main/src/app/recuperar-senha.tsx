import React, { useState } from "react";
import { Text, View } from "react-native";
import { router } from "expo-router";
import { Button, Card, Input, Notice, Screen } from "../ui";
import { api, messageFrom } from "../lib/api";
import { authStyles as s } from "../features/auth/styles";
import {
  errorText,
  passwordProblem,
  validEmail,
} from "../features/auth/validation";

export default function RecuperarSenha() {
  const [etapa, setEtapa] = useState(1);
  const [email, setEmail] = useState("");
  const [codigo, setCodigo] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [done, setDone] = useState(false);
  async function submit() {
    if (!validEmail(email)) {
      setError("Informe um e-mail válido.");
      return;
    }
    if (etapa > 1 && !/^\d{6}$/.test(codigo)) {
      setError("Informe o código de 6 números recebido por e-mail.");
      return;
    }
    if (etapa === 3) {
      const problem = passwordProblem(senha);
      if (problem) {
        setError(problem);
        return;
      }
      if (senha !== confirmar) {
        setError("As senhas não coincidem.");
        return;
      }
    }
    setBusy(true);
    setError("");
    setInfo("");
    try {
      const response = await api("/recuperar-senha", {
        method: "POST",
        body: {
          etapa,
          email: email.trim(),
          ...(etapa > 1 ? { codigo } : {}),
          ...(etapa === 3 ? { senha, confirmarSenha: confirmar } : {}),
        },
      });
      setInfo(messageFrom(response));
      if (etapa === 3) {
        setDone(true);
        setSenha("");
        setConfirmar("");
      } else setEtapa(etapa + 1);
    } catch (error) {
      setError(errorText(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen
      title="Recupere seu acesso"
      subtitle="Vamos ajudar você a voltar."
      back
    >
      <Card>
        <View style={s.section}>
          <Text style={s.status}>
            {done ? "ACESSO RECUPERADO" : `PASSO ${etapa} DE 3`}
          </Text>
          <Text style={s.title}>
            {done
              ? "Sua nova senha está pronta"
              : [
                  "Informe seu e-mail",
                  "Confira seu e-mail",
                  "Crie uma nova senha",
                ][etapa - 1]}
          </Text>
          {error ? <Notice message={error} kind="error" /> : null}
          {info ? <Notice message={info} kind="success" /> : null}
          {!done ? (
            <>
              <Input
                label="E-mail"
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                editable={etapa === 1 && !busy}
              />
              {etapa > 1 ? (
                <Input
                  label="Código recebido"
                  value={codigo}
                  onChangeText={(value) => setCodigo(value.replace(/\D/g, ""))}
                  maxLength={6}
                  keyboardType="number-pad"
                  autoComplete="one-time-code"
                  editable={etapa === 2 && !busy}
                />
              ) : null}
              {etapa === 3 ? (
                <>
                  <Input
                    label="Nova senha"
                    password
                    value={senha}
                    onChangeText={setSenha}
                    autoComplete="new-password"
                  />
                  <Input
                    label="Confirmar nova senha"
                    password
                    value={confirmar}
                    onChangeText={setConfirmar}
                    autoComplete="new-password"
                  />
                  <Text style={s.hint}>
                    Use 8 ou mais caracteres com maiúscula, minúscula, número e
                    símbolo.
                  </Text>
                </>
              ) : null}
              <Button
                title={
                  etapa === 1
                    ? "Enviar código"
                    : etapa === 2
                      ? "Verificar código"
                      : "Salvar nova senha"
                }
                onPress={() => void submit()}
                loading={busy}
                disabled={busy}
              />
            </>
          ) : (
            <Button
              title="Entrar com nova senha"
              onPress={() => router.replace("/entrar")}
            />
          )}
        </View>
      </Card>
      {etapa > 1 && !done ? (
        <Button
          title="Usar outro e-mail ou reenviar código"
          variant="ghost"
          disabled={busy}
          onPress={() => {
            setEtapa(1);
            setCodigo("");
            setInfo("");
            setError("");
          }}
        />
      ) : null}
    </Screen>
  );
}
