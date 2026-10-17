const { defineConfig } = require("eslint/config");
const expoConfig = require("eslint-config-expo/flat");

module.exports = defineConfig([
  expoConfig,
  {
    ignores: [
      "dist/**",
      "android/**",
      "ios/**",
      "Screens/**",
      "Services/**",
      "components/**",
      "App.js",
      "index.js",
    ],
  },
]);
