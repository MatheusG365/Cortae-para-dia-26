const { transformSync } = require("@babel/core");

// Tests execute the production JavaScript; only native services are mocked by each harness.
function compileJavaScript(source, { jsx = "automatic" } = {}) {
  return transformSync(source, {
    babelrc: false,
    configFile: false,
    sourceType: "module",
    plugins: [
      ["@babel/plugin-transform-react-jsx", { runtime: jsx }],
      ["@babel/plugin-transform-modules-commonjs", { importInterop: "babel" }],
    ],
  }).code;
}

module.exports = { compileJavaScript };
