import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const scanRoots = ["packages", "infrastructure"];
const rootConfigFiles = ["package.json", "pnpm-workspace.yaml"];
const codeAndConfigExtensions = new Set([
  ".cjs",
  ".cfg",
  ".env",
  ".ini",
  ".js",
  ".json",
  ".jsx",
  ".mjs",
  ".ps1",
  ".py",
  ".sh",
  ".toml",
  ".ts",
  ".tsx",
  ".yaml",
  ".yml",
]);
const specialConfigNames = new Set(["Dockerfile"]);

// Match old/ and old\ path segments, including ../old/ and quoted imports.
const legacyPathPattern = /(^|[\s'"`(=:[{,])(?:\.\.[/\\])*(?:\.[/\\])?old[/\\]/i;
const legacyPythonImportPattern = /^\s*(?:from|import)\s+old(?:\.|\s|$)/i;

async function collectFiles(relativePath) {
  const absolutePath = path.join(root, relativePath);
  let entries;

  try {
    entries = await readdir(absolutePath, { withFileTypes: true });
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw error;
  }

  const files = [];
  for (const entry of entries) {
    const child = path.join(relativePath, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectFiles(child)));
      continue;
    }

    if (
      entry.isFile() &&
      (codeAndConfigExtensions.has(path.extname(entry.name).toLowerCase()) ||
        specialConfigNames.has(entry.name))
    ) {
      files.push(child);
    }
  }
  return files;
}

const files = [];
for (const scanRoot of scanRoots) {
  files.push(...(await collectFiles(scanRoot)));
}
files.push(...rootConfigFiles);

const violations = [];
for (const relativePath of files) {
  let content;
  try {
    content = await readFile(path.join(root, relativePath), "utf8");
  } catch (error) {
    if (error?.code === "ENOENT") continue;
    throw error;
  }

  content.split(/\r?\n/).forEach((line, index) => {
    if (legacyPathPattern.test(line) || legacyPythonImportPattern.test(line)) {
      violations.push(`${relativePath}:${index + 1}: ${line.trim()}`);
    }
  });
}

if (violations.length > 0) {
  console.error("Legacy boundary check failed.");
  console.error("Active application code/config must not reference files under old/.\n");
  for (const violation of violations) console.error(violation);
  process.exit(1);
}

console.log(`Legacy boundary check passed (${files.length} active files checked).`);
