export { initRepository } from "./core/init-repository.js";
export { installCi } from "./core/install-ci.js";
export { installHook } from "./core/hooks.js";
export { listProtectedFiles } from "./core/list-protected-files.js";
export {
  addProtectedFile,
  removeProtectedFile,
  renameProtectedFile,
  updateProtectedFile
} from "./core/protected-files.js";
export { getRepositoryStatus } from "./core/status.js";
export { verifyRepository } from "./core/verify-repository.js";
