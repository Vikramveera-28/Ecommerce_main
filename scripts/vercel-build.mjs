import { cp, mkdir, rm } from "node:fs/promises";
import { spawn } from "node:child_process";

const run = (command, args, options = {}) =>
  new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      stdio: "inherit",
      shell: process.platform === "win32",
      ...options,
    });

    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`${command} ${args.join(" ")} failed with exit code ${code}`));
    });
  });

await run("vite", ["build"]);
await rm("public", { recursive: true, force: true });
await mkdir("public", { recursive: true });
await cp("dist", "public", { recursive: true });
