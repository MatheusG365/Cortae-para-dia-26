import React, { useState } from "react";
import { Text, View } from "react-native";
import { Button, Card, Loading, Notice, Screen } from "../ui";
import { api } from "../lib/api";
import { useResource } from "../lib/useResource";
import { useSession } from "../lib/session";
import { authStyles as s } from "../features/auth/styles";
import { errorText } from "../features/auth/validation";
export default function Termos() {
  const { user } = useSession();
  const resource = useResource("/termos-uso", null);
  const acceptance = useResource(user ? "/termos-uso/aceite" : null, null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function accept() {
    if (!resource.data?.aceite_habilitado) return;
    setBusy(true);
    setError("");
    try {
      await api("/termos-uso/aceite", {
        method: "POST",
        body: { versao: resource.data.versao, aceito: true },
      });
      await acceptance.reload();
    } catch (error) {
      setError(errorText(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen
      title="Termos de uso"
      subtitle="Informação clara para usar o Cortaê."
      back
      refreshing={resource.loading}
      onRefresh={resource.reload}
    >
      {resource.error ? (
        <Notice
          kind="error"
          message={resource.error}
          onRetry={resource.reload}
        />
      ) : null}
      {resource.loading && !resource.data ? <Loading /> : null}
      {resource.data ? (
        <>
          <Card>
            <View style={s.section}>
              <Text style={s.title}>{resource.data.titulo}</Text>
              <Text style={s.hint}>
                Versão {resource.data.versao} • {resource.data.publicado_em}
              </Text>
              {!resource.data.aceite_habilitado ? (
                <Notice
                  kind="info"
                  message="Documento em rascunho. O aceite ainda não está disponível."
                />
              ) : null}
              {Object.entries(resource.data.responsavel || {})
                .filter(([, value]) => value)
                .map(([key, value]) => (
                  <Text key={key} style={s.body}>
                    {key}: {value}
                  </Text>
                ))}
            </View>
          </Card>
          {resource.data.secoes.map((section) => (
            <Card key={section.titulo}>
              <View style={s.section}>
                <Text style={s.title}>{section.titulo}</Text>
                {section.paragrafos.map((paragraph, i) => (
                  <Text key={i} style={s.body}>
                    {paragraph}
                  </Text>
                ))}
              </View>
            </Card>
          ))}
          {error || acceptance.error ? (
            <Notice kind="error" message={error || acceptance.error || ""} />
          ) : null}
          {acceptance.data?.aceito ? (
            <Notice
              kind="success"
              message="Você já aceitou a versão atual dos termos."
            />
          ) : null}
          {user &&
          resource.data.aceite_habilitado &&
          !acceptance.data?.aceito ? (
            <Button
              title="Li e aceito os termos"
              loading={busy}
              disabled={busy || acceptance.loading}
              onPress={() => void accept()}
            />
          ) : null}
        </>
      ) : null}
    </Screen>
  );
}
