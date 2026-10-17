import { StyleSheet } from "react-native";
import { colors, fonts } from "../../theme";
export const authStyles = StyleSheet.create({
  logo: {
    width: 156,
    height: 72,
    resizeMode: "contain",
    alignSelf: "center",
    marginBottom: 10,
  },
  intro: {
    color: colors.muted,
    fontFamily: fonts.regular,
    fontSize: 15,
    lineHeight: 23,
  },
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
  section: { gap: 16 },
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
