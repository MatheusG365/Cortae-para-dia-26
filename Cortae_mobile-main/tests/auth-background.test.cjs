const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { compileJavaScript } = require("./helpers/compile.cjs");

test("native auth photo and gradient fill the frame using the supported StyleSheet API", () => {
  const fill = { position: "absolute", top: 0, bottom: 0, left: 0, right: 0 };
  const jsx = (type, props) => ({ type, props });
  const imports = {
    react: {},
    "react/jsx-runtime": { jsx, jsxs: jsx },
    "react-native": {
      Image: "Image",
      KeyboardAvoidingView: "KeyboardAvoidingView",
      Platform: { OS: "android" },
      Pressable: "Pressable",
      ScrollView: "ScrollView",
      StyleSheet: { create: (styles) => styles, absoluteFill: fill },
      Text: "Text",
      View: "View",
    },
    "react-native-safe-area-context": {
      SafeAreaView: "SafeAreaView",
      useSafeAreaInsets: () => ({ top: 24 }),
    },
    "@expo/vector-icons/Ionicons": "Icon",
    "expo-linear-gradient": { LinearGradient: "Gradient" },
    "expo-router": { router: {} },
    "../../lib/api": { imageSource: (uri) => ({ uri }) },
    "../../lib/useMobileAsset": {
      useMobileAsset: (name) =>
        `http://api.example.invalid/midia/mobile/${name}`,
    },
    "../../ui": { RemoteImage: "RemoteImage" },
    "../../theme": {
      colors: { background: "#101010", text: "#FAFAFA" },
      fonts: {},
    },
  };
  const module = { exports: {} };
  vm.runInNewContext(
    compileJavaScript(
      fs.readFileSync(
        path.join(__dirname, "../src/features/auth/AuthScreen.jsx"),
        "utf8",
      ),
    ),
    {
      module,
      exports: module.exports,
      require: (name) => {
        assert.ok(name in imports, name);
        return imports[name];
      },
    },
  );
  function nodes(tree) {
    if (!tree || typeof tree !== "object") return [];
    if (Array.isArray(tree)) return tree.flatMap(nodes);
    return [tree, ...nodes(tree.props?.children)];
  }
  for (const signup of [false, true]) {
    const tree = nodes(module.exports.default({ signup }));
    const image = tree.find((node) => node.type === "Image");
    const gradient = tree.find((node) => node.type === "Gradient");
    assert.ok(image.props.source.uri.endsWith("/loginBackground"));
    assert.equal(image.props.style, fill);
    assert.equal(gradient.props.style, fill);
    assert.equal(gradient.props.colors.at(-1), "#101010");
  }
});
