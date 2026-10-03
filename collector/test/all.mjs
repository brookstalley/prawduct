// `node --test collector/test/` resolves this directory as a module (node 25
// does not search a directory argument for test files), which lands here:
// every *.test.mjs beside this file is loaded, so a new test file is picked up
// without being listed.

import { readdirSync } from "node:fs";

const dir = new URL("./", import.meta.url);
for (const name of readdirSync(dir).filter((n) => n.endsWith(".test.mjs")).sort()) {
  await import(new URL(name, dir));
}
