export { initRepository } from "./core/init-repository.js";
export { checkRepositorySetup, isRepositoryInitialized, setupRepository } from "./core/setup-repository.js";
export { installCi } from "./core/install-ci.js";
export { installHook } from "./core/hooks.js";
export { listProtectedFiles } from "./core/list-protected-files.js";
export {
  addProtectedFile,
  addProtectedFiles,
  removeProtectedFile,
  removeProtectedFiles,
  renameProtectedFile,
  updateProtectedFile,
  updateProtectedFiles
} from "./core/protected-files.js";
export { getRepositoryStatus } from "./core/status.js";
export { verifyRepository } from "./core/verify-repository.js";
