import { StyleSheet } from "react-native";
import { colors, fonts } from "../../theme";
export const authStyles = StyleSheet.create({
  title: {
    color: colors.text,
    fontFamily: fonts.bold,
    fontSize: 22,
    marginBottom: 6,
  },
  hint: {
    color: colors.muted,
    fontFamily: fonts.regular,
    fontSize: 13,
    lineHeight: 20,
  },
  link: {
    color: colors.accent,
    fontFamily: fonts.semibold,
    fontSize: 14,
    paddingVertical: 8,
  },
  section: { gap: 20 },
  fieldLabel: {
    color: "#A0A0A0",
    fontFamily: fonts.medium,
    fontSize: 10,
    letterSpacing: 1.1,
  },
  forgot: { alignSelf: "flex-end", paddingVertical: 8, marginTop: 2 },
  forgotText: { color: colors.accent, fontFamily: fonts.medium, fontSize: 12 },
  loginActions: { gap: 14, marginTop: 26 },
  outlineButton: {
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: "transparent",
  },
  footer: {
    flexDirection: "row",
    justifyContent: "center",
    gap: 5,
    marginTop: 22,
    flexWrap: "wrap",
  },
  footerText: { color: colors.muted, fontFamily: fonts.regular, fontSize: 12 },
  footerLink: {
    color: colors.accent,
    fontFamily: fonts.semibold,
    fontSize: 12,
  },
  status: {
    color: colors.accent,
    fontFamily: fonts.bold,
    fontSize: 12,
    letterSpacing: 1.5,
  },
  body: {
    color: colors.text,
    fontFamily: fonts.regular,
    fontSize: 14,
    lineHeight: 22,
  },
  check: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 12,
  },
  checkBox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  checkText: { color: colors.text, fontSize: 15 },
});
