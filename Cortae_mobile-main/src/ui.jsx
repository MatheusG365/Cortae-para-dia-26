import React, { useState } from "react";
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import { colors, fonts } from "./theme";
import { assetUrl, imageSource } from "./lib/api";
export function Screen({
  children,
  title,
  subtitle,
  back = false,
  scroll = true,
  refreshing = false,
  onRefresh,
  action,
  style,
}) {
  const content = (
    <>
      {(title || back) && (
        <View style={s.header}>
          {back && (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Voltar"
              hitSlop={12}
              onPress={() =>
                router.canGoBack() ? router.back() : router.replace("/")
              }
              style={s.back}
            >
              <Ionicons name="arrow-back" color={colors.text} size={21} />
            </Pressable>
          )}
          <View style={s.grow}>
            {title && (
              <Text accessibilityRole="header" style={s.title}>
                {title}
              </Text>
            )}
            {subtitle && <Text style={s.subtitle}>{subtitle}</Text>}
          </View>
          {action}
        </View>
      )}
      {children}
    </>
  );
  return (
    <SafeAreaView edges={["top", "left", "right"]} style={s.screen}>
      <KeyboardAvoidingView
        style={s.grow}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        {scroll ? (
          <ScrollView
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
            contentContainerStyle={[s.content, style]}
            refreshControl={
              onRefresh ? (
                <RefreshControl
                  refreshing={refreshing}
                  onRefresh={onRefresh}
                  tintColor={colors.accent}
                  colors={[colors.accent]}
                />
              ) : undefined
            }
          >
            {content}
          </ScrollView>
        ) : (
          <View style={[s.content, s.grow, style]}>{content}</View>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
export function Card({ children, style, onPress }) {
  return onPress ? (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [s.card, pressed && s.pressed, style]}
    >
      {children}
    </Pressable>
  ) : (
    <View style={[s.card, style]}>{children}</View>
  );
}
export function Button({
  title,
  onPress,
  variant = "primary",
  loading = false,
  disabled = false,
  icon,
  style,
  accent,
}) {
  const background =
    accent && /^#[0-9a-f]{6}$/i.test(accent) ? accent : colors.accent;
  const channels = [1, 3, 5].map((position) =>
    parseInt(background.slice(position, position + 2), 16),
  );
  const light =
    channels[0] * 0.299 + channels[1] * 0.587 + channels[2] * 0.114 > 150;
  const foreground =
    variant === "primary"
      ? light
        ? "#17100A"
        : "#FFFFFF"
      : variant === "danger"
        ? colors.danger
        : colors.text;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      accessibilityRole="button"
      accessibilityState={{ disabled: disabled || loading, busy: loading }}
      style={({ pressed }) => [
        s.button,
        variant === "primary"
          ? [s.primary, { backgroundColor: background }]
          : variant === "ghost"
            ? s.ghost
            : s.secondary,
        variant === "danger" && s.danger,
        pressed && s.pressed,
        (disabled || loading) && s.disabled,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator size="small" color={foreground} />
      ) : (
        icon && <Ionicons name={icon} size={18} color={foreground} />
      )}
      <Text style={[s.buttonText, { color: foreground }]}>{title}</Text>
    </Pressable>
  );
}
export function Input({
  label,
  password = false,
  error,
  style,
  labelStyle,
  leadingIcon,
  ...props
}) {
  const [visible, setVisible] = useState(false);
  return (
    <View style={s.field}>
      {label && <Text style={[s.label, labelStyle]}>{label}</Text>}
      <View style={[s.inputWrap, error ? s.invalid : undefined]}>
        {leadingIcon && (
          <Ionicons
            name={leadingIcon}
            size={16}
            color={colors.muted}
            style={{ marginLeft: 14 }}
          />
        )}
        <TextInput
          {...props}
          accessibilityLabel={props.accessibilityLabel || label}
          placeholderTextColor={colors.muted}
          selectionColor={colors.accent}
          secureTextEntry={password ? !visible : props.secureTextEntry}
          autoCapitalize={password ? "none" : props.autoCapitalize}
          autoCorrect={password ? false : props.autoCorrect}
          style={[s.input, props.multiline && s.multiline, style]}
        />
        {password && (
          <Pressable
            onPress={() => setVisible((v) => !v)}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel={visible ? "Ocultar senha" : "Mostrar senha"}
            style={s.eye}
          >
            <Ionicons
              name={visible ? "eye-off-outline" : "eye-outline"}
              size={22}
              color={colors.muted}
            />
          </Pressable>
        )}
      </View>
      {error && (
        <Text accessibilityRole="alert" style={s.error}>
          {error}
        </Text>
      )}
    </View>
  );
}
export function Select({ label, value, options, onChange }) {
  const [open, setOpen] = useState(false);
  const selected = options.find((o) => o.value === value);
  return (
    <View style={s.field}>
      {label && <Text style={s.label}>{label}</Text>}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label || "Selecionar"}
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen(true)}
        style={s.select}
      >
        <Text numberOfLines={1} style={[s.selectText, !selected && s.muted]}>
          {selected?.label || "Selecione uma opção"}
        </Text>
        <Ionicons name="chevron-down" size={18} color={colors.accent} />
      </Pressable>
      <Modal
        visible={open}
        transparent
        animationType="slide"
        onRequestClose={() => setOpen(false)}
      >
        <View style={s.scrim}>
          <Pressable
            style={s.dismiss}
            accessibilityLabel="Fechar opções"
            onPress={() => setOpen(false)}
          />
          <SafeAreaView edges={["bottom"]} style={s.sheet}>
            <View style={s.sheetHandle} />
            <Row>
              <Text accessibilityRole="header" style={[s.sectionTitle, s.grow]}>
                {label || "Escolha uma opção"}
              </Text>
              <Pressable
                hitSlop={12}
                onPress={() => setOpen(false)}
                accessibilityLabel="Fechar opções"
                accessibilityRole="button"
              >
                <Ionicons name="close" size={24} color={colors.text} />
              </Pressable>
            </Row>
            <ScrollView>
              {options.map((option) => (
                <Pressable
                  key={String(option.value)}
                  accessibilityRole="radio"
                  accessibilityState={{ checked: option.value === value }}
                  onPress={() => {
                    onChange(option.value);
                    setOpen(false);
                  }}
                  style={[s.option, option.value === value && s.selected]}
                >
                  <Text
                    style={[
                      s.optionText,
                      option.value === value && { color: colors.accent },
                    ]}
                  >
                    {option.label}
                  </Text>
                  {option.value === value && (
                    <Ionicons
                      name="checkmark-circle"
                      size={21}
                      color={colors.accent}
                    />
                  )}
                </Pressable>
              ))}
            </ScrollView>
          </SafeAreaView>
        </View>
      </Modal>
    </View>
  );
}

export function Row({ children, style }) {
  return <View style={[s.row, style]}>{children}</View>;
}
export function Chip({ children, active, onPress }) {
  return (
    <Pressable
      disabled={!onPress}
      onPress={onPress}
      accessibilityRole={onPress ? "button" : undefined}
      style={[s.chip, active && s.chipActive]}
    >
      <Text style={[s.chipText, active && { color: colors.accent }]}>
        {children}
      </Text>
    </Pressable>
  );
}
export function Stat({ label, value }) {
  return (
    <Card style={s.stat}>
      <Text style={s.statLabel}>{label}</Text>
      <Text style={s.statValue}>{value}</Text>
    </Card>
  );
}
export function Notice({ message, kind = "info", onRetry }) {
  if (!message) return null;
  const color =
    kind === "error"
      ? colors.danger
      : kind === "success"
        ? colors.success
        : colors.accent;
  return (
    <View
      accessibilityRole={kind === "error" ? "alert" : undefined}
      style={[s.notice, { borderLeftColor: color }]}
    >
      <Ionicons
        name={
          kind === "error"
            ? "alert-circle-outline"
            : "information-circle-outline"
        }
        color={color}
        size={21}
      />
      <View style={s.grow}>
        <Text style={s.noticeText}>{message}</Text>
        {onRetry && (
          <Pressable
            accessibilityRole="button"
            onPress={onRetry}
            style={s.retry}
          >
            <Text style={{ color, fontFamily: fonts.bold }}>
              Tentar novamente
            </Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}
export function Empty({ title, message, action }) {
  return (
    <View style={s.empty}>
      <Ionicons name="layers-outline" size={32} color={colors.muted} />
      <Text style={s.emptyTitle}>{title}</Text>
      {message && <Text style={s.emptyText}>{message}</Text>}
      {action}
    </View>
  );
}
export function Loading() {
  return (
    <View style={s.loading}>
      <ActivityIndicator color={colors.accent} />
      <Text style={s.subtitle}>Carregando…</Text>
    </View>
  );
}
export function RemoteImage({ uri, style, accessibilityLabel, fallback }) {
  const [failedUri, setFailedUri] = useState(null);
  const resolvedUri = assetUrl(uri);
  return resolvedUri && resolvedUri !== failedUri ? (
    <Image
      key={resolvedUri}
      source={imageSource(resolvedUri)}
      accessibilityLabel={accessibilityLabel}
      accessibilityIgnoresInvertColors
      onError={() => setFailedUri(resolvedUri)}
      style={[s.image, style]}
    />
  ) : (
    <View style={[s.image, s.imageFallback, style]}>
      {fallback ? (
        <Text
          accessibilityRole="image"
          accessibilityLabel={accessibilityLabel}
          style={s.imageFallbackText}
        >
          {fallback}
        </Text>
      ) : (
        <Ionicons name="image-outline" size={30} color={colors.muted} />
      )}
    </View>
  );
}
const s = StyleSheet.create({
  imageFallbackText: {
    color: colors.text,
    fontFamily: fonts.extra,
    fontSize: 27,
    letterSpacing: -1,
  },
  grow: { flex: 1, minWidth: 0 },
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 32, gap: 16, flexGrow: 1 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginBottom: 8,
    paddingVertical: 8,
  },
  back: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  title: {
    fontFamily: fonts.bold,
    fontSize: 18,
    lineHeight: 25,
    color: colors.text,
    letterSpacing: -0.3,
  },
  subtitle: {
    fontFamily: fonts.regular,
    color: colors.muted,
    fontSize: 12,
    lineHeight: 19,
    marginTop: 5,
  },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 16,
    padding: 16,
    gap: 12,
  },
  pressed: { opacity: 0.78 },
  disabled: { opacity: 0.48 },
  button: {
    minHeight: 50,
    paddingHorizontal: 18,
    paddingVertical: 13,
    borderRadius: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 9,
  },
  primary: { backgroundColor: colors.accent },
  secondary: {
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
  },
  ghost: { backgroundColor: "transparent" },
  danger: { borderColor: "#70333C", backgroundColor: "#301C22" },
  buttonText: { fontFamily: fonts.bold, fontSize: 13, textAlign: "center" },
  field: { gap: 8 },
  label: { fontFamily: fonts.semibold, color: colors.text, fontSize: 12 },
  inputWrap: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 13,
  },
  input: {
    flex: 1,
    minHeight: 50,
    fontFamily: fonts.regular,
    color: colors.text,
    fontSize: 14,
    paddingHorizontal: 15,
    paddingVertical: 12,
  },
  multiline: { minHeight: 100, textAlignVertical: "top" },
  eye: { padding: 13 },
  invalid: { borderColor: colors.danger },
  error: { color: colors.danger, fontSize: 12, fontFamily: fonts.regular },
  select: {
    minHeight: 50,
    paddingHorizontal: 15,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 13,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  selectText: {
    fontFamily: fonts.medium,
    color: colors.text,
    flex: 1,
    fontSize: 13,
  },
  muted: { color: colors.muted },
  scrim: { flex: 1, backgroundColor: "#00000099", justifyContent: "flex-end" },
  dismiss: { flex: 1 },
  sheet: {
    maxHeight: "75%",
    backgroundColor: colors.surface,
    padding: 22,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    gap: 15,
  },
  sheetHandle: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 5,
    backgroundColor: colors.border,
    marginBottom: 5,
  },
  option: {
    padding: 16,
    borderRadius: 12,
    marginVertical: 3,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  optionText: {
    color: colors.text,
    fontFamily: fonts.medium,
    fontSize: 14,
    flex: 1,
  },
  selected: { backgroundColor: "#FF8A1818" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    flexWrap: "wrap",
  },
  sectionTitle: {
    color: colors.text,
    fontFamily: fonts.bold,
    fontSize: 18,
    lineHeight: 25,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: { borderColor: colors.accent, backgroundColor: "#FF8A1812" },
  chipText: { fontSize: 11, fontFamily: fonts.semibold, color: colors.muted },
  stat: { flexGrow: 1, flexBasis: "43%", minWidth: 120, gap: 8 },
  statLabel: {
    fontFamily: fonts.medium,
    color: colors.muted,
    fontSize: 11,
    lineHeight: 17,
  },
  statValue: {
    fontFamily: fonts.bold,
    color: colors.text,
    fontSize: 22,
    lineHeight: 29,
  },
  notice: {
    flexDirection: "row",
    gap: 10,
    padding: 15,
    borderRadius: 12,
    borderLeftWidth: 3,
    backgroundColor: colors.surfaceAlt,
  },
  noticeText: {
    color: colors.text,
    fontFamily: fonts.regular,
    fontSize: 12,
    lineHeight: 19,
  },
  retry: { paddingTop: 12, paddingBottom: 3 },
  empty: {
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    paddingVertical: 35,
    paddingHorizontal: 18,
  },
  emptyTitle: {
    color: colors.text,
    fontFamily: fonts.semibold,
    fontSize: 16,
    textAlign: "center",
  },
  emptyText: {
    fontFamily: fonts.regular,
    color: colors.muted,
    textAlign: "center",
    fontSize: 13,
    lineHeight: 21,
  },
  loading: { padding: 30, gap: 12, alignItems: "center" },
  image: {
    width: "100%",
    height: 180,
    borderRadius: 14,
    backgroundColor: colors.surfaceAlt,
  },
  imageFallback: { alignItems: "center", justifyContent: "center" },
});
