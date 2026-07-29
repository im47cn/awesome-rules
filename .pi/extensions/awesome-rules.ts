import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const extensionDir = dirname(fileURLToPath(import.meta.url))
const packageRoot = resolve(extensionDir, "../..")
const skillsDir = resolve(packageRoot, "skills")

export default function awesomeRulesPiExtension(pi: any) {
  pi.on("resources_discover", async () => ({
    skillPaths: [skillsDir],
  }))
}
