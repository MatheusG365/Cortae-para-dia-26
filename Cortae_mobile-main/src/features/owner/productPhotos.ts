export const MAX_PRODUCT_PHOTOS = 8;
export type ProductPhoto = {
  uri: string;
  fileSize?: number;
  mimeType?: string;
  fileName?: string | null;
};
export function productImageUrl(value: string) {
  if (/^\/uploads\/marketplace\/[a-f0-9]{32}\.webp$/.test(value)) return value;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password
      ? value
      : "";
  } catch {
    return "";
  }
}
export function productImageLinks(text: string) {
  const links = text
    .split(/\r?\n/)
    .map((value) => value.trim())
    .filter(Boolean);
  if (links.some((value) => !productImageUrl(value)))
    throw new Error("Use fotos da loja ou links HTTPS válidos.");
  return links;
}
export function validateProductPhotos(links: string[], photos: ProductPhoto[]) {
  if (links.length + photos.length > MAX_PRODUCT_PHOTOS)
    throw new Error("Cada produto pode ter até oito fotos.");
  for (const photo of photos) {
    if (
      !photo.uri ||
      (photo.mimeType && !/^image\/(jpeg|png|webp|gif)$/i.test(photo.mimeType))
    )
      throw new Error("Escolha fotos JPEG, PNG, WebP ou GIF estático.");
    if (
      photo.fileSize != null &&
      (!photo.fileSize || photo.fileSize > 10 * 1024 * 1024)
    )
      throw new Error("Cada foto deve ter até 10 MB.");
  }
}
export async function productPhotoBody<T extends ProductPhoto>(
  data: Record<string, any>,
  photos: T[],
  append: (form: FormData, key: string, photo: T) => Promise<void>,
) {
  validateProductPhotos(data.imagens ?? [], photos);
  if (!photos.length) return data;
  const form = new FormData();
  form.append("dados", JSON.stringify(data));
  for (const photo of photos) await append(form, "imagens", photo);
  return form;
}
