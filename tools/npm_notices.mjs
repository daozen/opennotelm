// Preserve upstream notices for production packages bundled into the web assets.
import {
  readFile,
  readdir,
  mkdir,
  copyFile,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

const root = path.resolve(process.argv[2] ?? "frontend");
const output = path.resolve(process.argv[3] ?? ".release-work/notices/npm");
const lock = JSON.parse(
  await readFile(path.join(root, "package-lock.json"), "utf8"),
);
await mkdir(output, { recursive: true });
const packages = [];
for (const [relative, entry] of Object.entries(lock.packages).sort()) {
  if (!relative || entry.dev) continue;
  const directory = path.join(root, relative);
  const metadata = JSON.parse(
    await readFile(path.join(directory, "package.json"), "utf8"),
  );
  const name = metadata.name;
  const destination = path.join(
    output,
    encodeURIComponent(name) + "@" + metadata.version,
  );
  await mkdir(destination, { recursive: true });
  const notices = [];
  for (const file of await readdir(directory, { withFileTypes: true })) {
    if (
      file.isFile() &&
      /^(licen[cs]e|copying|notice)(\.|$)/i.test(file.name)
    ) {
      await copyFile(
        path.join(directory, file.name),
        path.join(destination, file.name),
      );
      notices.push(file.name);
    }
  }
  if (!notices.length)
    throw new Error(`Missing production license text: ${name}`);
  packages.push({
    name,
    version: metadata.version,
    license: metadata.license ?? entry.license,
    notices,
  });
}
await writeFile(
  path.join(output, "index.json"),
  JSON.stringify(packages, null, 2) + "\n",
);
console.log(
  `Preserved notices for ${packages.length} frontend production packages.`,
);
