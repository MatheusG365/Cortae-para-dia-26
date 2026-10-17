import React from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { useFonts } from "expo-font";
import { Montserrat_400Regular } from "@expo-google-fonts/montserrat/400Regular";
import { Montserrat_500Medium } from "@expo-google-fonts/montserrat/500Medium";
import { Montserrat_600SemiBold } from "@expo-google-fonts/montserrat/600SemiBold";
import { Montserrat_700Bold } from "@expo-google-fonts/montserrat/700Bold";
import { Montserrat_800ExtraBold } from "@expo-google-fonts/montserrat/800ExtraBold";
import { SessionProvider, useSession } from "../lib/session";
import { DialogProvider } from "../lib/dialogs";
import { colors } from "../theme";
import { Loading, Screen } from "../ui";

function Navigation() {
  const { user, loading } = useSession();
  if (loading)
    return (
      <Screen>
        <Loading />
      </Screen>
    );
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.background },
        animation: "slide_from_right",
      }}
    >
      <Stack.Screen name="index" />
      <Stack.Protected guard={!user}>
        <Stack.Screen name="entrar" />
        <Stack.Screen name="cadastro" />
        <Stack.Screen name="verificar-codigo" />
        <Stack.Screen name="recuperar-senha" />
      </Stack.Protected>
      <Stack.Screen name="termos" />
      <Stack.Protected guard={user?.tipo === 1}>
        <Stack.Screen name="cliente" />
      </Stack.Protected>
      <Stack.Protected guard={user?.tipo === 2}>
        <Stack.Screen name="barbearia" />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  const [loaded, error] = useFonts({
    Montserrat_400Regular,
    Montserrat_500Medium,
    Montserrat_600SemiBold,
    Montserrat_700Bold,
    Montserrat_800ExtraBold,
  });
  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      {!loaded && !error ? (
        <Screen>
          <Loading />
        </Screen>
      ) : (
        <SessionProvider>
          <DialogProvider>
            <Navigation />
          </DialogProvider>
        </SessionProvider>
      )}
    </SafeAreaProvider>
  );
}
