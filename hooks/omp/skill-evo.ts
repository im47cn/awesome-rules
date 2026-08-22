/**
 * awesome-rules skill-evo — omp 会话结束触发器
 *
 * 安装（覆盖用户所有 omp 会话；项目级 .pi/extensions 只在单仓库内生效，故用用户级 hook）：
 *   cp hooks/omp/skill-evo.ts ~/.omp/agent/hooks/pre/
 * omp 自动发现 ~/.omp/agent/hooks/pre/*.ts 并以 Bun 原生加载（见 ~/.omp/agent/hooks/pre/claude-mem.ts 头注）。
 *
 * 模式契约（抄 claude-mem.ts）：
 *  - handler 有 30s 上限 → 同步返回，子进程 detached fire-and-forget
 *  - 事件：session_shutdown（会话结束）。ctx 上确定可用的只有 cwd，
 *    会话文件定位交给 Python 侧（evo_session.find_latest_omp_sessions）
 *  - 防递归链：子进程 env 带 AR_SKILL_EVO_CHILD=1 → evo.py 内部 claude -p 继承该标记
 *    → CC 侧 SessionEnd hook 见标记即退；state.json 增量去重兜底
 *  - 总开关：AR_SKILL_EVO_ENABLED=0 时短路
 *
 * 脚本定位：AR_SKILL_EVO_SCRIPT 环境变量 > 默认 ~/sources/awesome-rules/...
 */

const DEFAULT_SCRIPT = `${process.env.HOME}/sources/awesome-rules/skills/skill-evo/scripts/evo.py`;

export default function skillEvoHook(pi: any): void {
  pi.on("session_shutdown", async (_event: unknown, ctx: any) => {
    if (process.env.AR_SKILL_EVO_ENABLED === "0") return;
    const script = process.env.AR_SKILL_EVO_SCRIPT || DEFAULT_SCRIPT;
    const cwd = ctx?.cwd ?? "";
    try {
      Bun.spawn(["python3", script, "run", "--agent", "omp", "--cwd", cwd, "--no-omp"], {
        env: { ...process.env, AR_SKILL_EVO_CHILD: "1" },
        stdout: "ignore",
        stderr: "ignore",
        stdin: "ignore",
      });
      // 若宿主非 Bun，退路：
      // const { spawn } = await import("node:child_process");
      // spawn("python3", [script, "run", "--agent", "omp", "--cwd", cwd, "--no-omp"],
      //       { env: { ...process.env, AR_SKILL_EVO_CHILD: "1" },
      //         detached: true, stdio: "ignore" }).unref();
    } catch {
      /* hook 永不抛 */
    }
  });
}
