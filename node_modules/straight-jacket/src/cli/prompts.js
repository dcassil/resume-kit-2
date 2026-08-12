import { createCodedError } from "../core/errors.js";

export async function readPromptLines(stdin) {
  const chunks = [];
  for await (const chunk of stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }

  return Buffer.concat(chunks).toString("utf8").split(/\r?\n/);
}

export async function readPassword(stdin, stderr) {
  if (stdin.isTTY && stderr?.isTTY) {
    return readHiddenLine(stdin, stderr, "Straight Jacket password: ");
  }

  const [password] = await readPromptLines(stdin);
  return password ?? "";
}

export async function readPasswordConfirmation(stdin, stderr) {
  if (stdin.isTTY && stderr?.isTTY) {
    const password = await readHiddenLine(stdin, stderr, "Create Straight Jacket password: ");
    const confirmation = await readHiddenLine(stdin, stderr, "Confirm Straight Jacket password: ");
    return { password, confirmation };
  }

  const [password, confirmation] = await readPromptLines(stdin);
  return {
    password: password ?? "",
    confirmation: confirmation ?? ""
  };
}

function readHiddenLine(stdin, stderr, prompt) {
  return new Promise((resolve, reject) => {
    let value = "";
    let previousRawMode = false;

    const cleanup = () => {
      stdin.off("data", onData);
      if (typeof stdin.setRawMode === "function") {
        stdin.setRawMode(previousRawMode);
      }
      stdin.pause();
    };

    const finish = () => {
      cleanup();
      stderr.write("\n");
      resolve(value);
    };

    const cancel = () => {
      cleanup();
      stderr.write("^C\n");
      reject(createCodedError("USAGE_ERROR", "Prompt cancelled"));
    };

    const onData = (chunk) => {
      for (const character of chunk.toString("utf8")) {
        const code = character.charCodeAt(0);
        if (code === 3) {
          cancel();
          return;
        }
        if (character === "\r" || character === "\n") {
          finish();
          return;
        }
        if (code === 127 || code === 8) {
          value = value.slice(0, -1);
          continue;
        }
        if (code >= 32) {
          value += character;
        }
      }
    };

    stderr.write(prompt);
    if (typeof stdin.setRawMode === "function") {
      previousRawMode = stdin.isRaw === true;
      stdin.setRawMode(true);
    }
    stdin.resume();
    stdin.on("data", onData);
  });
}
