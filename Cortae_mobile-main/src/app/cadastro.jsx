import React, { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { router } from "expo-router";
import { Button, Input, Notice } from "../ui";
import { api } from "../lib/api";
import { useResource } from "../lib/useResource";
import { authStyles as s } from "../features/auth/styles";
import {
  errorText,
  passwordProblem,
  validEmail,
  customerRegistration,
} from "../features/auth/validation";
import AuthScreen from "../features/auth/AuthScreen";
export default function Cadastro() {
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [telefone, setTelefone] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [aceito, setAceito] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const terms = useResource("/termos-uso", null);
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
        body: customerRegistration(
          { nome, email, telefone, senha, confirmar, aceito },
          terms.data,
        ),
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
    <AuthScreen signup>
      {error ? <Notice kind="error" message={error} /> : null}
      <View style={s.section}>
        <Input
          label="NOME COMPLETO"
          labelStyle={s.fieldLabel}
          accessibilityLabel="Nome completo"
          placeholder="Seu nome completo"
          value={nome}
          onChangeText={setNome}
          autoComplete="name"
        />
        <Input
          label="E-MAIL"
          labelStyle={s.fieldLabel}
          accessibilityLabel="E-mail"
          placeholder="seuemail@exemplo.com"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoComplete="email"
        />
        <Input
          label="TELEFONE"
          labelStyle={s.fieldLabel}
          accessibilityLabel="Telefone com DDD"
          placeholder="(00) 00000-0000"
          value={telefone}
          onChangeText={setTelefone}
          keyboardType="phone-pad"
          autoComplete="tel"
          maxLength={20}
        />
        <Input
          label="SENHA"
          labelStyle={s.fieldLabel}
          accessibilityLabel="Senha"
          placeholder="Digite sua senha"
          password
          value={senha}
          onChangeText={setSenha}
          autoComplete="new-password"
        />
        <Text style={[s.hint, { fontSize: 11, lineHeight: 17 }]}>
          Pelo menos 8 caracteres, maiúscula, minúscula, número e símbolo.
        </Text>
        <Input
          label="CONFIRME SUA SENHA"
          labelStyle={s.fieldLabel}
          accessibilityLabel="Confirme sua senha"
          placeholder="Repita sua senha"
          password
          value={confirmar}
          onChangeText={setConfirmar}
          autoComplete="new-password"
        />
      </View>
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
          <Text style={[s.body, { flex: 1, fontSize: 12, lineHeight: 19 }]}>
            Li e aceito os termos de uso.
          </Text>
        </Pressable>
      ) : null}
      <Button
        title="CRIAR CONTA"
        onPress={() => void submit()}
        loading={busy}
        disabled={busy || terms.loading || !terms.data}
      />
      <View style={s.footer}>
        <Text style={s.footerText}>Já possui conta?</Text>
        <Pressable
          accessibilityRole="link"
          accessibilityLabel="Entrar na minha conta"
          onPress={() => router.replace("/entrar")}
        >
          <Text style={s.footerLink}>Login</Text>
        </Pressable>
      </View>
    </AuthScreen>
  );
}
