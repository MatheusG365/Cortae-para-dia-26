import React, { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { router } from "expo-router";
import { Button, Card, Input, Notice, Screen, Select } from "../ui";
import { api } from "../lib/api";
import { useResource } from "../lib/useResource";
import { authStyles as s } from "../features/auth/styles";
import {
  errorText,
  passwordProblem,
  validEmail,
} from "../features/auth/validation";

export default function Cadastro() {
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [telefone, setTelefone] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [tipo, setTipo] = useState("1");
  const [genero, setGenero] = useState("");
  const [aceito, setAceito] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const terms = useResource<any>("/termos-uso", null);
  async function submit() {
    const problem = passwordProblem(senha);
    if (
      !nome.trim() ||
      !validEmail(email) ||
      ![10, 11].includes(telefone.replace(/\D/g, "").length)
    ) {
      setError("Preencha nome, e-mail válido e telefone com DDD.");
      return;
    }
    if (problem) {
      setError(problem);
      return;
    }
    if (senha !== confirmar) {
      setError("As senhas não coincidem.");
      return;
    }
    if (!terms.data) {
      setError("Carregue os termos antes de continuar.");
      return;
    }
    if (terms.data.aceite_habilitado && !aceito) {
      setError("Leia e aceite os termos de uso.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api("/cadastro", {
        method: "POST",
        body: {
          nome: nome.trim(),
          email: email.trim(),
          telefone,
          senha,
          confirmarSenha: confirmar,
          tipo: Number(tipo),
          genero,
          termos_aceitos: aceito,
          termos_versao: terms.data.versao,
        },
      });
      router.replace({
        pathname: "/verificar-codigo",
        params: { email: email.trim() },
      });
    } catch (error) {
      setError(errorText(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen
      title="Crie sua conta"
      subtitle="Seu próximo cuidado começa no Cortaê."
      back
    >
      {error ? <Notice kind="error" message={error} /> : null}
      <Card>
        <View style={s.section}>
          <Select
            label="Como você vai usar o Cortaê?"
            value={tipo}
            options={[
              { label: "Sou cliente", value: "1" },
              { label: "Tenho uma barbearia ou salão", value: "2" },
            ]}
            onChange={setTipo}
          />
          <Input
            label="Nome completo"
            value={nome}
            onChangeText={setNome}
            autoComplete="name"
          />
          <Input
            label="E-mail"
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
          />
          <Input
            label="Telefone com DDD"
            value={telefone}
            onChangeText={setTelefone}
            keyboardType="phone-pad"
            autoComplete="tel"
            maxLength={20}
          />
          <Select
            label="Gênero (opcional)"
            value={genero}
            options={[
              { label: "Prefiro não informar", value: "" },
              { label: "Masculino", value: "masculino" },
              { label: "Feminino", value: "feminino" },
              { label: "Outro", value: "outro" },
            ]}
            onChange={setGenero}
          />
          <Input
            label="Senha"
            password
            value={senha}
            onChangeText={setSenha}
            autoComplete="new-password"
          />
          <Text style={s.hint}>
            Pelo menos 8 caracteres, maiúscula, minúscula, número e símbolo.
          </Text>
          <Input
            label="Confirme sua senha"
            password
            value={confirmar}
            onChangeText={setConfirmar}
            autoComplete="new-password"
          />
        </View>
      </Card>
      {terms.error ? (
        <Notice kind="error" message={terms.error} onRetry={terms.reload} />
      ) : null}
      <Pressable
        onPress={() => router.push("/termos")}
        accessibilityRole="link"
      >
        <Text style={s.link}>Ler os termos de uso</Text>
      </Pressable>
      {terms.data?.aceite_habilitado ? (
        <Pressable
          style={s.check}
          accessibilityRole="checkbox"
          accessibilityState={{ checked: aceito }}
          onPress={() => setAceito(!aceito)}
        >
          <View style={s.checkBox}>
            <Text style={s.checkText}>{aceito ? "✓" : ""}</Text>
          </View>
          <Text style={[s.body, { flex: 1 }]}>
            Li e aceito os termos de uso.
          </Text>
        </Pressable>
      ) : null}
      <Button
        title="Criar conta"
        onPress={() => void submit()}
        loading={busy}
        disabled={busy || terms.loading || !terms.data}
      />
    </Screen>
  );
}
