import { useEffect, useState } from "react";
import { getApiUrl, getSessionVersion, messageFrom } from "../../lib/api";
import { createProductSaver } from "./productSave";
export function useProductSave() {
  const [state, setState] = useState({
    busy: false,
    error: "",
    success: "",
  });
  const [saver] = useState(() =>
    createProductSaver({
      sessionVersion: getSessionVersion,
      apiUrl: getApiUrl,
      message: messageFrom,
      update: setState,
    }),
  );
  useEffect(() => {
    saver.mount();
    return () => saver.dispose();
  }, [saver]);
  return { ...state, run: saver.run, setError: saver.setError };
}
