import React, { useEffect, useRef, useSyncExternalStore } from "react";
import {
  AccessibilityInfo,
  findNodeHandle,
  Keyboard,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors, fonts } from "../theme";
import { Button } from "../ui";
import { getSessionVersion, onSessionExpired } from "./api";
import { useSession } from "./session";
import { confirmationOptions, DialogQueue } from "./dialogQueue";
const queue = new DialogQueue(getSessionVersion);
export function confirmDialog(title, message, action, options = {}) {
  queue.show({
    ...confirmationOptions(title),
    title,
    message,
    onConfirm: action,
    ...options,
  });
}
export function showInformation(title, message) {
  queue.show({ title, message, kind: "information" });
}
/** Mounted once, outside navigation, so every screen shares the same dialog queue. */
export function DialogProvider({ children }) {
  const request = useSyncExternalStore(
    queue.subscribe,
    queue.getSnapshot,
    queue.getSnapshot,
  );
  const { user } = useSession();
  const { height, width, fontScale } = useWindowDimensions();
  const titleRef = useRef(null);
  const identity = user ? `${user.id_usuario}:${user.tipo}` : "anonymous";
  useEffect(() => {
    queue.discardExpired();
    return () => queue.cancelAll();
  }, [identity]);
  useEffect(() => onSessionExpired(queue.discardExpired), []);
  useEffect(() => {
    if (request) Keyboard.dismiss();
  }, [request]);
  const information = request?.kind === "information";
  const terms = request?.kind === "terms";
  const destructive = request?.destructive;
  const accent = destructive ? colors.danger : colors.accent;
  const stacked = width < 360 || fontScale > 1.2 || terms;
  const dismiss = () => request && queue.dismiss(request.id);
  return (
    <>
      {children}
      <Modal
        transparent
        visible={!!request}
        animationType="fade"
        statusBarTranslucent
        navigationBarTranslucent
        onRequestClose={dismiss}
        onShow={() => {
          const node = findNodeHandle(titleRef.current);
          if (node) AccessibilityInfo.setAccessibilityFocus(node);
        }}
      >
        {!!request && (
          <SafeAreaView style={styles.overlay}>
            <Pressable
              style={StyleSheet.absoluteFill}
              onPress={dismiss}
              accessible={false}
              importantForAccessibility="no"
            />
            <View
              accessibilityViewIsModal
              importantForAccessibility="yes"
              onAccessibilityEscape={dismiss}
              style={[styles.card, { maxHeight: height * 0.85 }]}
            >
              <View style={[styles.topLine, { backgroundColor: accent }]} />
              <ScrollView
                style={styles.cardScroll}
                contentContainerStyle={styles.content}
                keyboardShouldPersistTaps="handled"
                showsVerticalScrollIndicator={false}
              >
                <View style={styles.topRow}>
                  <View
                    style={[
                      styles.icon,
                      {
                        backgroundColor: `${accent}18`,
                        borderColor: `${accent}38`,
                      },
                    ]}
                    accessibilityElementsHidden
                    importantForAccessibility="no-hide-descendants"
                  >
                    <Ionicons
                      name={
                        information
                          ? "information-circle-outline"
                          : terms
                            ? "document-text-outline"
                            : destructive
                              ? "alert-circle-outline"
                              : "checkmark-circle-outline"
                      }
                      size={29}
                      color={accent}
                    />
                  </View>
                  <Pressable
                    onPress={dismiss}
                    accessibilityRole="button"
                    accessibilityLabel="Fechar mensagem"
                    hitSlop={8}
                    style={({ pressed }) => [
                      styles.close,
                      pressed && { opacity: 0.6 },
                    ]}
                  >
                    <Ionicons name="close" size={22} color={colors.muted} />
                  </Pressable>
                </View>
                <Text style={[styles.eyebrow, { color: accent }]}>
                  {information
                    ? "CORTAÊ · INFORMAÇÃO"
                    : terms
                      ? "CORTAÊ · TERMOS DE USO"
                      : "ANTES DE CONTINUAR"}
                </Text>
                <Text
                  ref={titleRef}
                  accessibilityRole="header"
                  style={styles.title}
                >
                  {request.title}
                </Text>
                <ScrollView
                  key={request.id}
                  nestedScrollEnabled
                  style={{
                    maxHeight: height * (terms ? 0.38 : 0.3),
                    flexShrink: 1,
                  }}
                  contentContainerStyle={styles.messageContent}
                  showsVerticalScrollIndicator
                  keyboardShouldPersistTaps="handled"
                >
                  <Text selectable style={styles.message}>
                    {request.message}
                  </Text>
                </ScrollView>
                <View style={[styles.actions, stacked && styles.stacked]}>
                  {!information && (
                    <Button
                      title={request.cancelLabel || "Voltar"}
                      variant="secondary"
                      style={[styles.action, stacked && styles.stackedAction]}
                      onPress={dismiss}
                    />
                  )}
                  <Button
                    title={
                      information
                        ? "Entendi"
                        : request.confirmLabel || "Confirmar"
                    }
                    accent={accent}
                    style={[styles.action, stacked && styles.stackedAction]}
                    onPress={() => queue.confirm(request.id)}
                  />
                </View>
              </ScrollView>
            </View>
          </SafeAreaView>
        )}
      </Modal>
    </>
  );
}
const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
    backgroundColor: "rgba(0,0,0,0.76)",
  },
  card: {
    width: "100%",
    maxWidth: 440,
    backgroundColor: colors.surface,
    borderRadius: 28,
    borderColor: "#3A3E44",
    borderWidth: 1,
    overflow: "hidden",
    elevation: 24,
    boxShadow: "0 20px 70px rgba(0,0,0,0.45)",
  },
  topLine: { height: 4 },
  content: { padding: 24, gap: 14 },
  cardScroll: { flexShrink: 1 },
  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  icon: {
    width: 58,
    height: 58,
    borderRadius: 20,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  close: {
    minHeight: 44,
    minWidth: 44,
    alignItems: "center",
    justifyContent: "center",
    marginRight: -10,
    marginTop: -8,
  },
  eyebrow: {
    fontFamily: fonts.bold,
    fontSize: 10,
    letterSpacing: 1.4,
    marginTop: 4,
  },
  title: {
    fontFamily: fonts.bold,
    color: colors.text,
    fontSize: 23,
    lineHeight: 31,
  },
  messageContent: { paddingBottom: 4, paddingRight: 4 },
  message: {
    fontFamily: fonts.regular,
    color: "#C6CAD0",
    fontSize: 14,
    lineHeight: 23,
  },
  actions: {
    flexDirection: "row",
    gap: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: 20,
    marginTop: 2,
  },
  stacked: { flexDirection: "column-reverse" },
  action: { flexGrow: 1, flexBasis: 0, flexShrink: 1 },
  stackedAction: { flexGrow: 0, flexBasis: "auto" },
});
