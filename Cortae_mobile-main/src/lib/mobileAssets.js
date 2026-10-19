import { assetUrl, getApiUrl } from "./api";
// Names are stable API aliases; Drive IDs and credentials stay on the server.
export const mobileAssets = {
  logo: "logo-cortae.png",
  loginBackground: "fundo-login.png",
  banner: "banner-1.png",
};
export function mobileAssetUrl(name) {
  const path = `/midia/mobile/${encodeURIComponent(mobileAssets[name])}`;
  const url = assetUrl(path);
  return getApiUrl() ? url : undefined;
}
