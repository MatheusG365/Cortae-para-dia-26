import { Platform } from "react-native";
import * as ImagePicker from "expo-image-picker";
export async function pickPhoto(camera = false) {
  if (camera) {
    const p = await ImagePicker.requestCameraPermissionsAsync();
    if (!p.granted)
      throw new Error(
        "Permita o acesso à câmera nas configurações do aparelho.",
      );
  }
  const result = camera
    ? await ImagePicker.launchCameraAsync({
        mediaTypes: ["images"],
        quality: 0.85,
      })
    : await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        quality: 0.85,
      });
  return result.canceled ? null : result.assets[0];
}
export async function appendPhoto(form, key, photo) {
  if (Platform.OS === "web") {
    const response = await fetch(photo.uri);
    form.append(key, await response.blob(), photo.fileName || "foto.jpg");
  } else
    form.append(key, {
      uri: photo.uri,
      name: photo.fileName || "foto.jpg",
      type: photo.mimeType || "image/jpeg",
    });
}
