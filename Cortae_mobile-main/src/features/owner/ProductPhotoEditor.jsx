import React, { useState } from "react";
import { Image, View } from "react-native";
import * as ImagePicker from "expo-image-picker";
import { Button, Input, Notice, RemoteImage } from "../../ui";
import { Copy, Heading } from "./shared";
import { productImageLinks, validateProductPhotos } from "./productPhotos";
export default function ProductPhotoEditor({
  links,
  setLinks,
  photos,
  setPhotos,
  busy,
}) {
  const [error, setError] = useState("");
  const [picking, setPicking] = useState(false);
  const existing = links
    .split(/\r?\n/)
    .map((value) => value.trim())
    .filter(Boolean);
  async function choose() {
    setError("");
    setPicking(true);
    try {
      const validLinks = productImageLinks(links);
      const remaining = 8 - validLinks.length - photos.length;
      if (remaining < 1)
        throw new Error("Cada produto pode ter até oito fotos.");
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        allowsMultipleSelection: true,
        orderedSelection: true,
        selectionLimit: remaining,
        quality: 1,
      });
      if (!result.canceled) {
        const selected = [...photos, ...result.assets];
        validateProductPhotos(validLinks, selected);
        setPhotos(selected);
      }
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Não foi possível selecionar as fotos.",
      );
    } finally {
      setPicking(false);
    }
  }
  return (
    <View style={{ gap: 12 }}>
      <Heading>Fotos do produto</Heading>
      <Copy muted>
        {existing.length + photos.length}/8 fotos · A primeira será a capa.
        Fotos otimizadas automaticamente.
      </Copy>
      <Button
        title="Escolher fotos da galeria"
        icon="images-outline"
        variant="secondary"
        disabled={busy || picking || existing.length + photos.length >= 8}
        onPress={choose}
      />
      <Copy muted>Até 10 MB por foto.</Copy>
      {!!error && <Notice kind="error" message={error} />}
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 12 }}>
        {existing.map((uri, index) => (
          <View key={`${uri}:${index}`} style={{ width: 130, gap: 6 }}>
            <RemoteImage
              uri={uri}
              style={{ width: 130, height: 110, borderRadius: 10 }}
            />
            <Button
              title="Remover"
              variant="secondary"
              disabled={busy || picking}
              onPress={() =>
                setLinks(existing.filter((_, i) => i !== index).join("\n"))
              }
            />
          </View>
        ))}
        {photos.map((photo, index) => (
          <View key={`${photo.uri}:${index}`} style={{ width: 130, gap: 6 }}>
            <Image
              source={{ uri: photo.uri }}
              accessibilityLabel={`Nova foto ${index + 1}`}
              style={{ width: 130, height: 110, borderRadius: 10 }}
            />
            <Button
              title="Remover"
              variant="secondary"
              disabled={busy || picking}
              onPress={() => setPhotos(photos.filter((_, i) => i !== index))}
            />
          </View>
        ))}
      </View>
      <Input
        label="Links de fotos existentes: um por linha"
        value={links}
        onChangeText={setLinks}
        multiline
        editable={!busy && !picking}
      />
    </View>
  );
}
