import { useEffect, useState } from "react";
import { AppState } from "react-native";
import { initializeApi, onSessionExpired } from "./api";
import { mobileAssetUrl } from "./mobileAssets";
export function useMobileAsset(name) {
  const [source, setSource] = useState();
  useEffect(() => {
    let active = true;
    const refresh = () => {
      if (active) setSource({ name, uri: mobileAssetUrl(name) });
    };
    // ApiClient emits when its automatically selected server changes. Returning
    // to the app also rechecks the host, including on the unauthenticated screen.
    const unsubscribe = onSessionExpired(refresh);
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") refresh();
    });
    void initializeApi()
      .then(refresh)
      .catch(() => {
        if (active) setSource({ name, uri: undefined });
      });
    return () => {
      active = false;
      unsubscribe();
      subscription.remove();
    };
  }, [name]);
  return source?.name === name ? source.uri : undefined;
}
