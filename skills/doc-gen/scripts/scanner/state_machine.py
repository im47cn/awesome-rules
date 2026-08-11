"""状态机扫描器。

从 Java 源码识别状态机，产出 ``StateMachineDoc``（状态集 + 转换 + 质量审查）。

识别两类形态：

- **形态 A（raw）**：状态枚举（``enum XxxStatus/State``）+ 业务流转
  （``switch(xxxStatus)``/``case`` 或枚举内 ``transitTo`` 方法）。
- **形态 C（框架）**：
    * Spring StateMachine —— ``@StateMachine`` / ``extends StateMachineConfigurer`` /
      ``withStates().initial()..end()`` / ``withTransitions().source().target().event()``
    * Cola Statemachine ---- ``from(A).to(B).on(E)``

形态 B（State 设计模式）暂不支持（YAGNI）。

方法体提取走「候选文件重读」（仿 :class:`POScanner`），**不增强全局** ``JavaScanner``，
避免污染 ``FileInfo``。质量分析（死状态/不可达/缺失流转）是经典图问题，扫描器持有
完整状态图，直接做 BFS 可达性分析，无需外部分析器。
"""

import re
from pathlib import Path
from typing import Optional

from doctypes import (
    FileInfo, StateMachineDoc, StateTransitionDoc, StateMachineIssueDoc,
)


def _first_group(m: Optional[re.Match]) -> str:
    """从含多个可选 group 的 match 里取第一个非空 group。

    各 *_RE 正则同时兼容 ``States.X`` 枚举引用与 ``"X"`` 字符串两种写法，
    分别落在不同 group，取首个非空即可。
    """
    if not m:
        return ""
    for g in m.groups():
        if g:
            return g
    return ""


class StateMachineScanner:
    """从 Java 源码识别状态机，产出 StateMachineDoc 列表。"""

    # ── 形态 C：状态机框架特征 ──────────────────────────────
    FRAMEWORK_IMPORTS = {
        "spring": re.compile(r"org\.springframework\.statemachine"),
        "cola": re.compile(r"com\.alibaba\.cola\.statemachine"),
    }
    # Spring StateMachine builder 链：兼容 States.X 与 "X"
    SPRING_INITIAL_RE = re.compile(r'\.initial\(\s*(?:States?\.(\w+)|"(\w+)")\s*\)')
    SPRING_END_RE = re.compile(r'\.end\(\s*(?:States?\.(\w+)|"(\w+)")\s*\)')
    SPRING_SOURCE_RE = re.compile(r'\.source\(\s*(?:States?\.(\w+)|"(\w+)")\s*\)')
    SPRING_TARGET_RE = re.compile(r'\.target\(\s*(?:States?\.(\w+)|"(\w+)")\s*\)')
    SPRING_EVENT_RE = re.compile(r'\.event\(\s*(?:Events?\.(\w+)|"(\w+)")\s*\)')

    # Cola Statemachine：from(A).to(B).on(E)
    COLA_FROM_RE = re.compile(r'\bfrom\(\s*(?:States?\.(\w+)|"(\w+)")\s*\)')
    COLA_TO_RE = re.compile(r'\.to\(\s*(?:States?\.(\w+)|"(\w+)")\s*\)')
    COLA_ON_RE = re.compile(r'\.on\(\s*(?:Events?\.(\w+)|"(\w+)")\s*\)')

    # ── 形态 A：状态枚举 + 流转启发式 ───────────────────────
    # 名称含 Status/State/Flow 即为状态枚举候选（兼容 XxxStatusEnum、ContFlowStatusEnum 等命名）
    STATUS_NAME_RE = re.compile(r"(Status|State|Flow)", re.IGNORECASE)
    CASE_LABEL_RE = re.compile(r"case\s+([A-Z][A-Z0-9_]*)\s*:")
    # setStatus(X) / changeStatus(X) / status = X 等赋值目标（X 为全大写枚举常量）
    SET_STATUS_RE = re.compile(
        r"set\w*(?:Status|State)\s*\(\s*(?:\w+\.)?([A-Z][A-Z0-9_]*)\s*\)"
    )

    def _is_status_enum(self, name: str, values) -> bool:
        """状态枚举候选：名称含 Status/State/Flow 且至少 2 个常量。"""
        vals = values or []
        return len(vals) >= 2 and bool(self.STATUS_NAME_RE.search(name or ""))

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()

    def scan(self, java_files: list[FileInfo]) -> list[StateMachineDoc]:
        """扫描 java_files，识别状态机并完成质量分析。"""
        machines: list[StateMachineDoc] = []

        # 第一遍：索引形态 A 状态枚举（顶层 enum + class 内嵌套 enum）
        enum_index: dict[str, dict] = {}
        for fi in java_files:
            class_name = fi.get("className", "")
            # 顶层 enum
            if (fi.get("classType") == "enum"
                    and self._is_status_enum(class_name, fi.get("enumValues"))):
                enum_index[class_name] = {
                    "values": list(fi["enumValues"]),
                    "sourcePath": fi.get("filePath", ""),
                    "qualifiedName": fi.get("qualifiedName", ""),
                    "parentClass": "",
                    "parentQName": "",
                }
            # 嵌套枚举（外层 class 内的 enum，通常不可见于顶层扫描）
            for ne in (fi.get("nestedEnums") or []):
                ne_name = ne.get("name", "")
                if self._is_status_enum(ne_name, ne.get("values")):
                    enum_index[ne_name] = {
                        "values": list(ne.get("values", [])),
                        "sourcePath": fi.get("filePath", ""),
                        "qualifiedName": ne.get("qualifiedName", ""),
                        "parentClass": class_name,
                        "parentQName": fi.get("qualifiedName", ""),
                    }

        # enum qname → className 反查（用于去重关联）
        enum_qname_to_name = {info["qualifiedName"]: name
                              for name, info in enum_index.items()}

        # 形态 C：识别框架配置类 + 收集被其 import 的状态枚举（去重依据）
        managed_qnames: set[str] = set()
        framework_fis: list[tuple[FileInfo, str]] = []
        for fi in java_files:
            fw = self._detect_framework(fi)
            if fw:
                framework_fis.append((fi, fw))
                for imp in (fi.get("imports") or []):
                    if imp in enum_qname_to_name:
                        managed_qnames.add(imp)

        for fi, fw in framework_fis:
            content = self._read_file(fi.get("filePath", ""))
            if not content:
                continue
            sm = (self._extract_spring(fi.get("className", ""), fi.get("filePath", ""), content)
                  if fw == "spring"
                  else self._extract_cola(fi.get("className", ""), fi.get("filePath", ""), content))
            if not sm:
                continue
            # 关联被管理的状态枚举（取首个 import 的项目内状态枚举）
            for imp in (fi.get("imports") or []):
                if imp in enum_qname_to_name:
                    sm.managedEnum = enum_qname_to_name[imp]
                    break
            machines.append(sm)

        # 形态 A：状态枚举（被框架管理的 enum 跳过，避免与形态 C 视图冗余）
        for enum_name, info in enum_index.items():
            if info["qualifiedName"] in managed_qnames:
                continue
            machines.append(self._scan_raw_enum(enum_name, info, java_files))

        # 质量分析
        for sm in machines:
            self._analyze_quality(sm)

        return machines

    # ── 形态 C ──────────────────────────────────────────────

    def _detect_framework(self, fi: FileInfo) -> Optional[str]:
        """识别状态机框架类型，返回 'spring'/'cola'/None。

        基于 import 判断：extends/@StateMachine 等必然伴随对应框架 import，
        故 import 命中即可覆盖 configurer/annotation 场景。
        """
        imports = "\n".join(fi.get("imports") or [])
        if self.FRAMEWORK_IMPORTS["cola"].search(imports):
            return "cola"
        if self.FRAMEWORK_IMPORTS["spring"].search(imports):
            return "spring"
        return None

    def _extract_spring(self, class_name, source_path,
                        content) -> Optional[StateMachineDoc]:
        transitions = self._extract_spring_transitions(content)
        has_initial = self.SPRING_INITIAL_RE.search(content)
        if not transitions and not has_initial:
            return None
        initial = _first_group(has_initial)
        ends = [_first_group(m) for m in self.SPRING_END_RE.finditer(content)]
        ends = [e for e in ends if e]
        states = self._collect_states(transitions, initial, ends)
        return StateMachineDoc(
            name=class_name or "SpringStateMachine",
            framework="spring", sourceClass=class_name, sourcePath=source_path,
            states=states, initialState=initial, endStates=ends, transitions=transitions,
        )

    def _extract_spring_transitions(self, content) -> list[StateTransitionDoc]:
        """提取 Spring ``withTransitions()`` 块内的 source/target/event。

        builder 链跨行，先按 ``.withTransitions`` 切片，每片到下一个 ``.with(States|Transitions)``
        截断，片内按出现顺序配对 source/target/event。
        """
        trans: list[StateTransitionDoc] = []
        for block in re.split(r"\bwithTransitions\b", content)[1:]:
            seg = re.split(r"\bwith(?:States|Transitions)\b", block, maxsplit=1)[0]
            sources = [_first_group(m) for m in self.SPRING_SOURCE_RE.finditer(seg)]
            targets = [_first_group(m) for m in self.SPRING_TARGET_RE.finditer(seg)]
            events = [_first_group(m) for m in self.SPRING_EVENT_RE.finditer(seg)]
            for i in range(max(len(sources), len(targets))):
                trans.append(StateTransitionDoc(
                    source=sources[i] if i < len(sources) else "",
                    target=targets[i] if i < len(targets) else "",
                    event=events[i] if i < len(events) else "",
                ))
        return trans

    def _extract_cola(self, class_name, source_path,
                      content) -> Optional[StateMachineDoc]:
        froms = [_first_group(m) for m in self.COLA_FROM_RE.finditer(content)]
        tos = [_first_group(m) for m in self.COLA_TO_RE.finditer(content)]
        ons = [_first_group(m) for m in self.COLA_ON_RE.finditer(content)]
        n = max(len(froms), len(tos))
        if not n:
            return None
        transitions = [
            StateTransitionDoc(
                source=froms[i] if i < len(froms) else "",
                target=tos[i] if i < len(tos) else "",
                event=ons[i] if i < len(ons) else "",
            )
            for i in range(n)
        ]
        return StateMachineDoc(
            name=class_name or "ColaStateMachine",
            framework="cola", sourceClass=class_name, sourcePath=source_path,
            states=self._collect_states(transitions, "", []),
            transitions=transitions,
        )

    # ── 形态 A ──────────────────────────────────────────────

    def _scan_raw_enum(self, enum_name, info,
                       java_files) -> StateMachineDoc:
        """状态枚举：states=enumValues；转换靠扫描引用该枚举的守卫/赋值（启发式）。"""
        transitions = self._extract_raw_transitions(enum_name, info, java_files)
        return StateMachineDoc(
            name=enum_name, framework="raw", detection="heuristic",
            sourceClass=enum_name, sourcePath=info["sourcePath"],
            states=list(info["values"]), transitions=transitions,
        )

    def _extract_raw_transitions(self, enum_name, info,
                                 java_files) -> list[StateTransitionDoc]:
        """启发式提取 raw enum 的状态转换。

        兼容三种真实写法：
        - 模式1 switch：``case <S>: ... setStatus(<T>)``
        - 模式2 方法守卫+赋值：方法体内守卫源 + 赋值目标 → ``S→T``
          · 目标：``EnumName.X.getCode()`` 或 MyBatis ``.set(::getXxxStatus, EnumName.X.getCode())``
          · 守卫：``Objects.equals(getXxxStatus(), EnumName.X...)`` / ``StrUtil.equals(...)`` 或 ``==/!=``
        - 嵌套枚举引用：``OuterClass.EnumName.X``（双层，按父类 import 定位文件）

        无明确守卫或目标时不强行配对，避免误报。
        """
        transitions: list[StateTransitionDoc] = []
        seen: set[tuple[str, str]] = set()

        def add(src: str, tgt: str) -> None:
            if src and tgt and src != tgt and (src, tgt) not in seen:
                seen.add((src, tgt))
                transitions.append(StateTransitionDoc(source=src, target=tgt))

        enum = re.escape(enum_name)
        parent = info.get("parentClass", "")
        parent_qname = info.get("parentQName", "")
        enum_qname = info.get("qualifiedName", "")
        # 引用模式：兼容 EnumName.X 与 OuterClass.EnumName.X（嵌套两层）
        parent_pat = (re.escape(parent) + r"\.") if parent else ""
        ref = rf"(?:{parent_pat})?{enum}"

        # 目标：赋值流转（EnumName.X.getCode()；.set 内的赋值同样命中）
        target_re = re.compile(rf"{ref}\.([A-Z][A-Z0-9_]*)\.(?:getCode|get\w*)\s*\(\s*\)")
        # 源守卫：Objects/StrUtil.equals(getXxxStatus(), EnumName.X...) 或 ==/!= EnumName.X
        source_re = re.compile(
            rf"(?:Objects|StrUtil)\.equals\w*\([^)]*?get\w*(?:Status|State|Flow)\w*\s*\(\s*\)\s*,\s*{ref}\.([A-Z][A-Z0-9_]*)"
            rf"|[!=]=\s*{ref}\.([A-Z][A-Z0-9_]*)"
        )

        for fi in java_files:
            imports = "\n".join(fi.get("imports") or [])
            same_class = (enum_name == fi.get("className", "")
                          or (parent and parent == fi.get("className", "")))
            # 文件须 import 枚举自身或其外层类（嵌套枚举按父类 import 定位）
            imported = ((enum_qname and enum_qname in imports)
                        or (parent_qname and parent_qname in imports)
                        or same_class)
            if not imported:
                continue
            content = self._read_file(fi.get("filePath", ""))
            if not content:
                continue
            # 模式1：switch(case S) → setStatus(T)
            for sw in re.split(r"\bswitch\s*\(", content)[1:]:
                seg = re.split(r"\n\s*\}", sw, maxsplit=1)[0]
                parts = re.split(r"(case\s+[A-Z][A-Z0-9_]*\s*:)", seg)
                current_src = ""
                for part in parts:
                    cm = re.match(r"case\s+([A-Z][A-Z0-9_]*)\s*:", part)
                    if cm:
                        current_src = cm.group(1)
                    elif current_src:
                        for tgt in self.SET_STATUS_RE.findall(part):
                            add(current_src, tgt)
            # 模式2：方法体内赋值配对最近前置守卫（替代笛卡尔积，避免 N×M 误报）
            for body in self._iter_method_bodies(content):
                self._pair_nearest_guard(body, source_re, target_re, add)
        return transitions

    @staticmethod
    def _pair_nearest_guard(body, source_re, target_re, add):
        """方法体内：每个赋值 target 配对它之前最近的守卫 source（按代码位置）。

        比笛卡尔积精确：每个 target 只配对一个最近前置 source，
        避免「多守卫 × 多赋值」全组合误报（如把无关守卫与赋值错配）。
        兼容两种风格：
        - 肯定守卫：``if(status == S) { ...set(T)... }``  → S→T
        - 否定守卫：``if(status != S) throw; set(T)``       → S→T（T 在守卫之后）
        """
        guards = sorted(
            (m.start(), m.group(1) or m.group(2))
            for m in source_re.finditer(body)
            if (m.group(1) or m.group(2))
        )
        assigns = sorted(
            (m.start(), m.group(1))
            for m in target_re.finditer(body)
            if m.group(1)
        )
        for t_pos, t_state in assigns:
            recent = None
            for g_pos, g_state in guards:
                if g_pos < t_pos:
                    recent = g_state
                else:
                    break
            if recent:
                add(recent, t_state)

    @staticmethod
    def _iter_method_bodies(content: str):
        """粗略切分方法体（按大括号深度匹配），yield 每个方法体文本。

        仅匹配带访问修饰符的方法签名，跳过 if/for 等控制块。
        """
        sig_re = re.compile(
            r"(?:public|protected|private)\s+[^\n{};=]*?\b\w+\s*\([^)]*\)\s*\{")
        for m in sig_re.finditer(content):
            start = m.end()
            depth, i, n = 1, start, len(content)
            while i < n and depth > 0:
                c = content[i]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                i += 1
            if depth == 0:
                yield content[start:i - 1]

    # ── 质量分析（图算法）──────────────────────────────────

    def _analyze_quality(self, sm: StateMachineDoc):
        """对单个状态机做可达性/完整性检查，结果写入 sm.issues。"""
        issues: list[StateMachineIssueDoc] = []
        states = set(sm.states)
        sources = {t.source for t in sm.transitions if t.source}
        targets = {t.target for t in sm.transitions if t.target}
        involved = sources | targets
        end_set = set(sm.endStates)

        # 无初始状态（仅 Spring 强制要求 initial）
        if not sm.initialState and sm.framework == "spring":
            issues.append(StateMachineIssueDoc(
                type="no_initial", severity="warning",
                message=f"{sm.name}: 框架状态机未声明 initial 状态"))

        # 不可达：BFS from initial（仅在有初始且有转换时分析，避免无图误报）
        if sm.initialState and sm.transitions:
            reachable = self._bfs(sm.initialState, sm.transitions)
            for s in sorted(states):
                if s not in reachable:
                    issues.append(StateMachineIssueDoc(
                        type="unreachable", severity="critical",
                        message=f"{sm.name}: 状态 {s} 从初始状态 {sm.initialState} 不可达"))

        # 缺失流转：未参与任何转换（且非初始/终止）
        for s in sorted(states):
            if s not in involved and s != sm.initialState and s not in end_set:
                sev = "info" if sm.framework == "raw" else "warning"
                issues.append(StateMachineIssueDoc(
                    type="missing_transition", severity=sev,
                    message=f"{sm.name}: 状态 {s} 未出现在任何转换中"))

        # 无终止状态（仅 Spring 习惯要求 end）
        if sm.framework == "spring" and not sm.endStates:
            issues.append(StateMachineIssueDoc(
                type="no_end", severity="info",
                message=f"{sm.name}: 未声明 end/终止状态"))

        # 形态 A 未识别到显式转换
        if sm.framework == "raw" and not sm.transitions and len(states) > 1:
            issues.append(StateMachineIssueDoc(
                type="missing_transition", severity="info",
                message=f"{sm.name}: 识别到状态枚举但未发现显式转换，流转可能分散在 switch/if 中"))

        sm.issues = issues

    @staticmethod
    def _bfs(start: str, transitions: list[StateTransitionDoc]) -> set:
        adj: dict[str, list[str]] = {}
        for t in transitions:
            adj.setdefault(t.source, []).append(t.target)
        visited: set[str] = set()
        queue = [start]
        while queue:
            n = queue.pop(0)
            if n in visited:
                continue
            visited.add(n)
            queue.extend(adj.get(n, []))
        return visited

    # ── 工具 ────────────────────────────────────────────────

    def _collect_states(self, transitions, initial, ends) -> list:
        states = set()
        for t in transitions:
            if t.source:
                states.add(t.source)
            if t.target:
                states.add(t.target)
        if initial:
            states.add(initial)
        states.update(ends)
        return sorted(states)

    def _read_file(self, rel_path: str) -> str:
        if not rel_path:
            return ""
        try:
            return (self.root_path / rel_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
