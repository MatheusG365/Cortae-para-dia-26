import React, { useState } from "react";
import { api, assetUrl } from "../../lib/api";
import { useSession } from "../../lib/session";
import { useResource } from "../../lib/useResource";
import { Button, Card, Input, RemoteImage, Screen, Select } from "../../ui";
import {
  Data,
  Feedback,
  Heading,
  Label,
  Resource,
  ask,
  go,
  s,
  useAction,
} from "./common";
import { appendPhoto, pickPhoto } from "./Photo";
export default function Profile() {
  const { user, signOut, refreshUser } = useSession();
  const id = user?.id_usuario ?? user?.id;
  const state = useResource<Data>(id ? `/dados-perfil/${id}` : null, {});
  const [draft, setDraft] = useState<Data>({}),
    [password, setPassword] = useState(""),
    [confirm, setConfirm] = useState(""),
    [photo, setPhoto] = useState<any>(null);
  const action = useAction();
  const u = state.data.usuario || {};
  const form = {
    nome: u.nome || "",
    email: u.email || "",
    telefone: u.telefone || "",
    genero: u.genero || "",
    ...draft,
  };
  const update = (key: string, value: string) =>
    setDraft((v) => ({ ...v, [key]: value }));
  async function save() {
    if (!form.nome.trim()) throw new Error("Informe seu nome.");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email))
      throw new Error("Informe um e-mail válido.");
    if (form.telefone && !/^\d{10,11}$/.test(form.telefone.replace(/\D/g, "")))
      throw new Error("Use um telefone com DDD, de 10 ou 11 dígitos.");
    if (password && password !== confirm)
      throw new Error("As senhas não coincidem.");
    const data = new FormData();
    Object.entries(form).forEach(([k, v]) =>
      data.append(k, k === "telefone" ? v.replace(/\D/g, "") : v.trim()),
    );
    if (password) data.append("senha", password);
    if (photo) await appendPhoto(data, "foto", photo);
    await api(`/editar-usuario/${id}`, { method: "PUT", body: data });
    setPassword("");
    setConfirm("");
    await refreshUser();
    await state.reload();
  }
  return (
    <Screen
      title="Meu perfil"
      subtitle="Seu contato sempre atualizado, seu cuidado mais próximo"
      refreshing={state.loading}
      onRefresh={state.reload}
    >
      <Resource state={state}>
        <Card>
          <RemoteImage
            uri={photo?.uri || assetUrl(state.data.usuario?.foto_perfil)}
            style={{
              ...s.avatar,
              width: 94,
              height: 94,
              borderRadius: 47,
              alignSelf: "center",
            }}
          />
          <Heading>{state.data.usuario?.nome || user?.nome}</Heading>
          <Button
            title="Alterar foto"
            variant="secondary"
            disabled={action.busy}
            onPress={() =>
              action.run(async () => {
                const selected = await pickPhoto();
                if (selected) setPhoto(selected);
              })
            }
          />
          <Input
            label="Nome"
            value={form.nome}
            onChangeText={(v: string) => update("nome", v)}
            autoComplete="name"
          />
          <Input
            label="E-mail"
            value={form.email}
            onChangeText={(v: string) => update("email", v)}
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
          />
          <Input
            label="Telefone com DDD"
            value={form.telefone}
            onChangeText={(v: string) => update("telefone", v)}
            keyboardType="phone-pad"
            autoComplete="tel"
          />
          <Select
            label="Gênero"
            value={form.genero}
            onChange={(v: string) => update("genero", v)}
            options={[
              { label: "Prefiro não informar", value: "" },
              { label: "Masculino", value: "masculino" },
              { label: "Feminino", value: "feminino" },
              { label: "Outro", value: "outro" },
            ]}
          />
          <Heading>Alterar senha</Heading>
          <Label muted>Deixe em branco para manter a senha atual.</Label>
          <Input
            label="Nova senha"
            password
            value={password}
            onChangeText={setPassword}
            autoComplete="new-password"
          />
          <Input
            label="Confirme a nova senha"
            password
            value={confirm}
            onChangeText={setConfirm}
          />
          <Feedback state={action} />
          <Button
            title="Salvar minhas informações"
            loading={action.busy}
            onPress={() => action.run(save, "Seu perfil foi atualizado.")}
          />
        </Card>
      </Resource>
      <Button
        title="Meus pedidos"
        variant="secondary"
        onPress={() => go("/cliente/pedidos")}
      />
      <Button
        title="Produtos favoritos"
        variant="secondary"
        onPress={() => go("/cliente/favoritos")}
      />
      <Button
        title="Lista de desejos"
        variant="secondary"
        onPress={() => go("/cliente/desejos")}
      />
      <Button
        title="Sair da conta"
        variant="ghost"
        onPress={() =>
          ask(
            "Sair da conta?",
            "Você poderá entrar novamente com seu e-mail e senha.",
            () => {
              void signOut();
            },
          )
        }
      />
    </Screen>
  );
}
