import React from "react";
import {
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  SafeAreaView,
  useSafeAreaInsets,
} from "react-native-safe-area-context";
import Ionicons from "@expo/vector-icons/Ionicons";
import { LinearGradient } from "expo-linear-gradient";
import { router } from "expo-router";
import { imageSource } from "../../lib/api";
import { useMobileAsset } from "../../lib/useMobileAsset";
import { RemoteImage } from "../../ui";
import { colors, fonts } from "../../theme";

// Login Screen / Signup Screen from the APP page of the supplied Figma.
export default function AuthScreen({ children, signup = false }) {
  const insets = useSafeAreaInsets();
  const background = useMobileAsset("loginBackground");
  const logo = useMobileAsset("logo");
  return (
    <SafeAreaView edges={["left", "right", "bottom"]} style={styles.screen}>
      <KeyboardAvoidingView
        style={styles.screen}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
          contentContainerStyle={[
            styles.content,
            { paddingTop: insets.top + 16 },
          ]}
        >
          <View
            pointerEvents="none"
            style={[styles.photo, signup && styles.signupPhoto]}
          >
            {background && (
              <Image
                source={imageSource(background)}
                style={StyleSheet.absoluteFill}
                resizeMode="cover"
                accessibilityElementsHidden
                importantForAccessibility="no-hide-descendants"
              />
            )}
            <LinearGradient
              colors={["#10101025", "#10101070", colors.background]}
              locations={[0, 0.45, 1]}
              style={StyleSheet.absoluteFill}
            />
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Voltar"
            hitSlop={10}
            style={styles.back}
            onPress={() =>
              router.canGoBack() ? router.back() : router.replace("/")
            }
          >
            <Ionicons name="arrow-back" color={colors.text} size={19} />
          </Pressable>
          {signup ? (
            <View style={styles.signupHeading}>
              <Text accessibilityRole="header" style={styles.title}>
                Criar Conta
              </Text>
            </View>
          ) : (
            <View style={styles.brand}>
              <RemoteImage
                uri={logo}
                accessibilityLabel="Cortaê"
                fallback="CORTAÊ"
                style={styles.logo}
              />
              <Text style={styles.tagline}>
                Experiência Premium de{"\n"}Barbearia
              </Text>
            </View>
          )}
          {children}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: 24, paddingBottom: 32, flexGrow: 1 },
  photo: { position: "absolute", top: 0, left: 0, right: 0, height: 355 },
  signupPhoto: { height: 240 },
  back: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: "#FFFFFF12",
    alignItems: "center",
    justifyContent: "center",
  },
  brand: { alignItems: "center", marginTop: 54, marginBottom: 42 },
  logo: {
    width: "100%",
    maxWidth: 300,
    height: 94,
    resizeMode: "contain",
    backgroundColor: "transparent",
    borderRadius: 0,
  },
  tagline: {
    fontFamily: fonts.regular,
    color: "#ADADAD",
    fontSize: 12,
    lineHeight: 19,
    textAlign: "center",
    marginTop: 10,
  },
  signupHeading: { height: 128, justifyContent: "flex-end", paddingBottom: 28 },
  title: {
    color: colors.text,
    fontFamily: fonts.bold,
    fontSize: 26,
    letterSpacing: -0.8,
  },
});
