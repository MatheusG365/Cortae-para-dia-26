import React, { useState } from "react";
import { View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { api, assetUrl, query } from "../../lib/api";
import { showInformation } from "../../lib/dialogs";
import { useResource } from "../../lib/useResource";
import { Button, Card, Input, RemoteImage, Screen, Select } from "../../ui";
import {
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
export default function Visagismo() {
  const p = useLocalSearchParams();
  const state = useResource(
    query("/visagismo/cortes", {
      id_barbearia: p.barbearia,
      ids_servicos: p.servicos,
    }),
    {},
  );
  const action = useAction();
  const [photo, setPhoto] = useState(null),
    [analysis, setAnalysis] = useState(null),
    [cut, setCut] = useState(null),
    [choice, setChoice] = useState("na_hora"),
    [skip, setSkip] = useState(true),
    [simulation, setSimulation] = useState(""),
    [color, setColor] = useState(""),
    [search, setSearch] = useState("");
  const paint = p.tem_pintar === "true",
    colorOnly = p.apenas_cor === "true";
  const female =
    (state.data.generos_servico || []).length === 1 &&
    state.data.generos_servico[0] === "feminino";
  const cuts =
    analysis && !skip
      ? analysis.recomendacoes || []
      : (state.data.cortes || []).filter((v) =>
          v.nome.toLowerCase().includes(search.toLowerCase()),
        );
  function reset() {
    setAnalysis(null);
    setCut(null);
    setSimulation("");
    setSkip(true);
  }
  async function analyze() {
    if (!photo)
      throw new Error("Escolha uma foto de frente, em um local iluminado.");
    const form = new FormData();
    await appendPhoto(form, "imagem", photo);
    form.append("id_barbearia", p.barbearia);
    form.append("ids_servicos", p.servicos);
    const d = await api(
      colorOnly ? "/visagismo/salvar-foto" : "/visagismo/analisar",
      { method: "POST", body: form, timeout: 120000 },
    );
    if (!d.id_visagismo || !d.foto_url)
      throw new Error("O servidor não confirmou a foto.");
    if (
      !colorOnly &&
      (d.recomendacoes?.length !== 1 ||
        !d.recomendacoes[0]?.motivo ||
        d.recomendacoes[0]?.compativel_com_cabelo_existente !== true)
    )
      throw new Error(
        "A análise não trouxe uma recomendação compatível. Tente novamente.",
      );
    setAnalysis(d);
    setCut(d.recomendacoes?.[0] || null);
    setChoice("catalogo");
    setSkip(false);
    setSimulation("");
  }
  async function simulate() {
    if (!analysis?.id_visagismo)
      throw new Error("Analise ou envie sua foto antes da simulação.");
    if (!colorOnly && !cut)
      throw new Error("Escolha o corte antes de simular.");
    if (paint && !/^#[0-9a-f]{6}$/i.test(color))
      throw new Error("Escolha uma cor.");
    const d = await api(`/visagismo/${analysis.id_visagismo}/simular`, {
      method: "POST",
      timeout: 300000,
      body: {
        id_corte: cut?.id_corte,
        cor: paint ? color : null,
        alvo: p.alvo || "cabelo",
      },
    });
    if (!d.imagem_url) throw new Error("O servidor não retornou a imagem.");
    setSimulation(d.imagem_url);
  }
  const canNext =
    (skip && !paint && (choice !== "catalogo" || !!cut)) || !!simulation;
  return (
    <Screen
      title="Seu próximo visual"
      subtitle="Catálogo do estabelecimento ou recomendação a partir da sua foto"
      back
    >
      <Feedback state={action} />
      <Card>
        <Heading>Visagismo com sua foto</Heading>
        <Label muted>
          A foto será enviada para análise de características e simulação.
          Escolha uma foto sua, de frente e bem iluminada.
        </Label>
        {photo && <RemoteImage uri={photo.uri} style={s.hero} />}
        <Button
          title="Escolher foto"
          variant="secondary"
          disabled={action.busy}
          onPress={() =>
            action.run(async () => {
              const next = await pickPhoto();
              if (next) {
                setPhoto(next);
                reset();
              }
            })
          }
        />
        <Button
          title="Tirar uma selfie"
          variant="ghost"
          disabled={action.busy}
          onPress={() =>
            action.run(async () => {
              const next = await pickPhoto(true);
              if (next) {
                setPhoto(next);
                reset();
              }
            })
          }
        />
        <Button
          title={
            colorOnly ? "Enviar foto para testar a cor" : "Analisar minha foto"
          }
          loading={action.busy}
          disabled={!photo}
          onPress={() =>
            ask(
              "Analisar sua foto?",
              "Sua foto será enviada ao serviço de visagismo para esta análise.",
              () => action.run(analyze),
            )
          }
        />
        {!paint && (
          <Button
            title="Pular análise e escolher manualmente"
            variant="ghost"
            onPress={() => {
              reset();
              setChoice("na_hora");
            }}
          />
        )}
      </Card>
      {analysis && !skip && (
        <Card>
          <Heading>Características observadas</Heading>
          {Object.entries(analysis.caracteristicas || {}).map(
            ([key, value]) => (
              <Label key={key}>
                {key.replaceAll("_", " ")}: {String(value)}
              </Label>
            ),
          )}
          <Label>{analysis.cabelo_atual}</Label>
          <Label>{analysis.observacoes}</Label>
          {cut?.motivo && (
            <>
              <Heading>Por que este corte?</Heading>
              <Label>{cut.motivo}</Label>
            </>
          )}
        </Card>
      )}
      {skip && !paint && (
        <Card>
          <Heading>Prefere decidir no atendimento?</Heading>
          <Button
            title={
              choice === "na_hora" ? "✓ Escolho na hora" : "Escolho na hora"
            }
            variant="secondary"
            onPress={() => {
              setChoice("na_hora");
              setCut(null);
            }}
          />
          <Button
            title={`${choice === "profissional" ? "✓ " : ""}${female ? "A cabeleireira escolhe" : "O profissional escolhe"}`}
            variant="secondary"
            onPress={() => {
              setChoice("profissional");
              setCut(null);
            }}
          />
        </Card>
      )}
      {!colorOnly && (
        <>
          <Heading>
            {analysis && !skip
              ? "Seu único corte recomendado"
              : "Explore o catálogo de cortes"}
          </Heading>
          {skip && (
            <Input
              label="Buscar corte"
              value={search}
              onChangeText={setSearch}
              placeholder="Nome do corte"
            />
          )}
          <Resource state={state}>
            {cuts.slice(0, 30).map((c) => (
              <View
                key={c.id_corte}
                style={cut?.id_corte === c.id_corte ? s.selected : undefined}
              >
                <Card>
                  <RemoteImage
                    uri={assetUrl(c.imagem_url)}
                    style={s.productImage}
                  />
                  <Heading>{c.nome}</Heading>
                  <Label muted>
                    {c.genero} ·{" "}
                    {String(c.categoria || "").replaceAll("_", " ")}
                  </Label>
                  <Button
                    title="Ver mais detalhes"
                    variant="ghost"
                    onPress={() =>
                      showInformation(
                        c.nome,
                        c.descricao ||
                          "O estabelecimento ainda não informou detalhes adicionais.",
                      )
                    }
                  />
                  <Button
                    title={
                      cut?.id_corte === c.id_corte
                        ? "✓ Corte selecionado"
                        : "Escolher este corte"
                    }
                    variant="secondary"
                    onPress={() => {
                      setCut(c);
                      setChoice("catalogo");
                      setSimulation("");
                    }}
                  />
                </Card>
              </View>
            ))}
            {cuts.length > 30 && (
              <Label muted>
                Refine a busca para encontrar os demais cortes.
              </Label>
            )}
          </Resource>
        </>
      )}
      {paint && (
        <Card>
          <Heading>Cor da simulação</Heading>
          <Select
            label="Escolha a cor"
            value={color}
            onChange={(v) => {
              setColor(v);
              setSimulation("");
            }}
            options={[
              { label: "Selecione uma cor", value: "" },
              { label: "Preto", value: "#1a1a1a" },
              { label: "Castanho escuro", value: "#432818" },
              { label: "Castanho", value: "#7f5539" },
              { label: "Loiro", value: "#ddb892" },
              { label: "Ruivo", value: "#d62828" },
              { label: "Azul", value: "#219ebc" },
            ]}
          />
        </Card>
      )}
      {!skip || paint ? (
        <Button
          title="Gerar simulação do visual"
          disabled={!analysis || (!colorOnly && !cut) || (paint && !color)}
          loading={action.busy}
          onPress={() =>
            ask(
              "Gerar simulação?",
              "O serviço criará uma imagem a partir da sua foto e da escolha atual.",
              () => action.run(simulate),
            )
          }
        />
      ) : null}
      {simulation && (
        <Card>
          <Heading>Prévia do seu visual</Heading>
          <RemoteImage uri={assetUrl(simulation)} style={s.hero} />
          <Label muted>
            Simulação ilustrativa; converse com o profissional sobre a execução.
          </Label>
        </Card>
      )}
      <Button
        title="Escolher dia e horário"
        disabled={!canNext || action.busy}
        onPress={() =>
          go("/cliente/agendar", {
            ...p,
            escolha_corte: choice === "catalogo" && !cut ? "" : choice,
            id_corte: choice === "catalogo" ? String(cut?.id_corte || "") : "",
            id_visagismo:
              choice === "catalogo" ? String(analysis?.id_visagismo || "") : "",
          })
        }
      />
    </Screen>
  );
}
