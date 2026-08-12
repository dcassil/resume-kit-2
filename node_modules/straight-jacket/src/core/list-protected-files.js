import { loadVerifiedManifest } from "./manifest-state.js";

export async function listProtectedFiles({ repoRoot } = {}) {
  const { manifest } = await loadVerifiedManifest(repoRoot);

  return {
    ok: true,
    entries: manifest.entries.map((entry) => ({ ...entry }))
  };
}
