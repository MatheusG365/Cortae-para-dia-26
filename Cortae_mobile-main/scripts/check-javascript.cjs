const fs = require("node:fs");
const path = require("node:path");
const { parseSync } = require("@babel/core");

const root = path.resolve(__dirname, "../src");
function files(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(dir, entry.name);
    return entry.isDirectory() ? files(file) : [file];
  });
}
const sourceFiles = files(root);
const errors = [];
for (const filename of sourceFiles) {
  if (/\.tsx?$/.test(filename)) {
    errors.push(`${filename}: fonte TypeScript restante`);
    continue;
  }
  if (!/\.jsx?$/.test(filename)) continue;
  try {
    const ast = parseSync(fs.readFileSync(filename, "utf8"), {
      filename,
      babelrc: false,
      configFile: false,
      sourceType: "module",
      parserOpts: { plugins: ["jsx"] },
    });
    for (const node of ast.program.body) {
      if (
        ![
          "ImportDeclaration",
          "ExportNamedDeclaration",
          "ExportAllDeclaration",
        ].includes(node.type)
      )
        continue;
      const dependency = node.source?.value;
      if (!dependency?.startsWith(".")) continue;
      const target = path.resolve(path.dirname(filename), dependency);
      const candidates = [
        target,
        ...[".js", ".jsx", ".json", "/index.js", "/index.jsx"].map(
          (ext) => target + ext,
        ),
      ];
      if (
        !candidates.some(
          (file) => fs.existsSync(file) && fs.statSync(file).isFile(),
        )
      ) {
        errors.push(`${filename}: import local não encontrado: ${dependency}`);
      }
    }
  } catch (error) {
    errors.push(error.message);
  }
}
if (errors.length) {
  console.error(errors.join("\n"));
  process.exitCode = 1;
} else {
  console.log(
    `${sourceFiles.filter((file) => /\.jsx?$/.test(file)).length} fontes JavaScript/JSX válidas; imports locais encontrados.`,
  );
}
