import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const presentationDirectories = ["app", "components", "features"];
const webRoot = join(process.cwd());

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return /\.(?:ts|tsx)$/.test(entry.name) ? [path] : [];
  });
}

describe("frontend architecture boundaries", () => {
  it("keeps raw fixtures out of presentation modules", () => {
    const files = presentationDirectories.flatMap((directory) => sourceFiles(join(webRoot, directory)));
    const violations = files.filter((file) => /from\s+["']@\/mock\//.test(readFileSync(file, "utf8")));

    expect(violations).toEqual([]);
  });

  it("keeps browser transport calls inside service adapters", () => {
    const files = presentationDirectories.flatMap((directory) => sourceFiles(join(webRoot, directory)));
    const violations = files.filter((file) => /\bfetch\s*\(/.test(readFileSync(file, "utf8")));

    expect(violations).toEqual([]);
  });
});
