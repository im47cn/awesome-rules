"""状态机扫描器测试。

覆盖：形态 A（状态枚举）/ 形态 C（Spring、Cola 框架）识别、质量分析（死状态/不可达）、
不误匹配普通枚举。参照 test_suffix_map.py 的 path 注入模式。
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from scanner.state_machine import StateMachineScanner  # noqa: E402
from doctypes import StateMachineDoc, StateTransitionDoc  # noqa: E402


def _write(tmp_path: Path, rel: str, content: str) -> Path:
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    return f


def _fi(file_path, class_name, class_type, enum_values=None,
        imports=None, qualified_name=""):
    return {
        "filePath": file_path, "package": "",
        "qualifiedName": qualified_name or class_name,
        "className": class_name, "classType": class_type,
        "annotations": [], "imports": imports or [],
        "methods": [], "fields": [], "enumValues": enum_values or [],
    }


# ── 形态 A：状态枚举 ──────────────────────────────────────

def test_raw_enum_states(tmp_path):
    rel = "domain/order/OrderStatus.java"
    _write(tmp_path, rel,
           "package com.x.order; enum OrderStatus { INIT, PAID, SHIPPED, CANCELLED; }")
    files = [_fi(rel, "OrderStatus", "enum",
                 ["INIT", "PAID", "SHIPPED", "CANCELLED"],
                 qualified_name="com.x.order.OrderStatus")]
    sms = StateMachineScanner(str(tmp_path)).scan(files)
    sm = next(s for s in sms if s.name == "OrderStatus")
    assert sm.framework == "raw"
    assert set(sm.states) == {"INIT", "PAID", "SHIPPED", "CANCELLED"}


def test_non_status_enum_ignored(tmp_path):
    rel = "domain/Color.java"
    _write(tmp_path, rel, "enum Color { RED, GREEN; }")
    files = [_fi(rel, "Color", "enum", ["RED", "GREEN"])]
    assert StateMachineScanner(str(tmp_path)).scan(files) == []


def test_raw_enum_transitions_from_method_guard(tmp_path):
    """模式2：方法内「源守卫(!= Enum.S) + 目标赋值(Enum.T.getCode())」配对提取转换。

    适配「实体方法改状态」风格（如 markSending()），raw enum 的转换常散落于此。
    """
    enum_rel = "domain/OrderStatus.java"
    enum_qn = "com.x.domain.OrderStatus"
    _write(tmp_path, enum_rel,
           "package com.x.domain; enum OrderStatus { PENDING, SENDING, DONE; }")
    enum_fi = _fi(enum_rel, "OrderStatus", "enum",
                  ["PENDING", "SENDING", "DONE"], qualified_name=enum_qn)
    entity_rel = "domain/OrderEntity.java"
    _write(tmp_path, entity_rel,
           "package com.x.domain;\nimport com.x.domain.OrderStatus;\n"
           "public class OrderEntity {\n"
           "    public void markSending() {\n"
           "        OrderStatus current = OrderStatus.fromCode(this.status);\n"
           "        if (current != OrderStatus.PENDING) { throw new IllegalStateException(); }\n"
           "        this.status = OrderStatus.SENDING.getCode();\n"
           "    }\n"
           "}\n")
    entity_fi = _fi(entity_rel, "OrderEntity", "class", imports=[enum_qn])
    sm = next(s for s in StateMachineScanner(str(tmp_path)).scan([enum_fi, entity_fi])
              if s.name == "OrderStatus")
    assert ("PENDING", "SENDING") in {(t.source, t.target) for t in sm.transitions}


def test_raw_enum_no_false_transition_without_guard(tmp_path):
    """反面：方法有目标赋值但无源守卫(!= / == Enum.S)时不配对，避免误报。"""
    enum_rel = "domain/OrderStatus.java"
    enum_qn = "com.x.domain.OrderStatus"
    _write(tmp_path, enum_rel, "package com.x.domain; enum OrderStatus { A, B; }")
    enum_fi = _fi(enum_rel, "OrderStatus", "enum", ["A", "B"], qualified_name=enum_qn)
    entity_rel = "domain/OrderEntity.java"
    _write(tmp_path, entity_rel,
           "package com.x.domain;\nimport com.x.domain.OrderStatus;\n"
           "public class OrderEntity {\n"
           "    public void init() { this.status = OrderStatus.A.getCode(); }\n"
           "}\n")
    entity_fi = _fi(entity_rel, "OrderEntity", "class", imports=[enum_qn])
    sm = next(s for s in StateMachineScanner(str(tmp_path)).scan([enum_fi, entity_fi])
              if s.name == "OrderStatus")
    assert sm.transitions == []  # 无源守卫，不配对


# ── 形态 C：状态机框架 ───────────────────────────────────

def test_spring_state_machine(tmp_path):
    rel = "infra/OrderStateMachineConfig.java"
    _write(tmp_path, rel, """
package com.x;
import org.springframework.statemachine.config.EnumStateMachineConfigurer;
public class OrderStateMachineConfig extends EnumStateMachineConfigurer {
    public void configure() {
        withStates().initial("INIT").states(values()).end("DONE");
        withTransitions().source("INIT").target("PAID").event("PAY");
        withTransitions().source("PAID").target("DONE").event("SHIP");
    }
}
""")
    files = [_fi(rel, "OrderStateMachineConfig", "class",
                 imports=["org.springframework.statemachine.config.EnumStateMachineConfigurer"])]
    sm = next(s for s in StateMachineScanner(str(tmp_path)).scan(files)
              if s.framework == "spring")
    assert sm.initialState == "INIT"
    assert "DONE" in sm.endStates
    trans = {(t.source, t.target, t.event) for t in sm.transitions}
    assert ("INIT", "PAID", "PAY") in trans
    assert ("PAID", "DONE", "SHIP") in trans


def test_cola_state_machine(tmp_path):
    rel = "infra/OrderStateMachine.java"
    _write(tmp_path, rel, """
package com.x;
import com.alibaba.cola.statemachine.StateMachine;
public class OrderStateMachine {
    void build() {
        from("INIT").to("PAID").on("PAY");
        from("PAID").to("DONE").on("SHIP");
    }
}
""")
    files = [_fi(rel, "OrderStateMachine", "class",
                 imports=["com.alibaba.cola.statemachine.StateMachine"])]
    sm = next(s for s in StateMachineScanner(str(tmp_path)).scan(files)
              if s.framework == "cola")
    trans = {(t.source, t.target, t.event) for t in sm.transitions}
    assert ("INIT", "PAID", "PAY") in trans
    assert ("PAID", "DONE", "SHIP") in trans


# ── 质量分析 ─────────────────────────────────────────────

def test_missing_transition_for_raw(tmp_path):
    rel = "domain/TaskStatus.java"
    _write(tmp_path, rel, "enum TaskStatus { A, B, C; }")
    files = [_fi(rel, "TaskStatus", "enum", ["A", "B", "C"],
                 qualified_name="com.x.TaskStatus")]
    sm = next(s for s in StateMachineScanner(str(tmp_path)).scan(files)
              if s.name == "TaskStatus")
    assert "missing_transition" in [i.type for i in sm.issues]


def test_unreachable_via_direct_doc():
    """直接构造 StateMachineDoc 验证 BFS 不可达检测。"""
    scanner = StateMachineScanner(".")
    sm = StateMachineDoc(
        name="X", framework="spring", states=["A", "B", "C"], initialState="A",
        transitions=[StateTransitionDoc(source="A", target="B")],
    )
    scanner._analyze_quality(sm)
    unreachable = [i for i in sm.issues if i.type == "unreachable"]
    assert len(unreachable) == 1            # 仅 C 不可达（A→B 可达）


def test_reachable_no_false_positive():
    """完整链路 A->B->C 不应报不可达。"""
    scanner = StateMachineScanner(".")
    sm = StateMachineDoc(
        name="Y", framework="spring", states=["A", "B", "C"], initialState="A",
        transitions=[
            StateTransitionDoc(source="A", target="B"),
            StateTransitionDoc(source="B", target="C"),
        ],
    )
    scanner._analyze_quality(sm)
    assert not any(i.type == "unreachable" for i in sm.issues)


# ── 去重：raw 被 spring 管理时抑制 ────────────────────────

def test_raw_enum_suppressed_when_managed_by_spring(tmp_path):
    """spring 配置类 import 了状态枚举 → raw 视图被抑制，spring 视图标记 managedEnum。"""
    enum_rel = "domain/OrderStatus.java"
    cfg_rel = "infra/OrderConfig.java"
    _write(tmp_path, enum_rel, "package com.x; enum OrderStatus { INIT, PAID; }")
    _write(tmp_path, cfg_rel, """
package com.x;
import org.springframework.statemachine.config.EnumStateMachineConfigurer;
import com.x.OrderStatus;
public class OrderConfig extends EnumStateMachineConfigurer {
    void c() {
        withStates().initial("INIT");
        withTransitions().source("INIT").target("PAID");
    }
}
""")
    files = [
        _fi(enum_rel, "OrderStatus", "enum", ["INIT", "PAID"],
            qualified_name="com.x.OrderStatus"),
        _fi(cfg_rel, "OrderConfig", "class",
            imports=["org.springframework.statemachine.config.EnumStateMachineConfigurer",
                     "com.x.OrderStatus"]),
    ]
    sms = StateMachineScanner(str(tmp_path)).scan(files)
    names = [s.name for s in sms]
    assert "OrderConfig" in names          # spring 视图保留
    assert "OrderStatus" not in names      # raw 视图被抑制
    spring = next(s for s in sms if s.name == "OrderConfig")
    assert spring.managedEnum == "OrderStatus"


# ── 嵌套枚举（隐式状态机核心）─────────────────────────────

def test_nested_enum_discovered_via_nestedEnums_field(tmp_path):
    """嵌套枚举（class 内的 enum）通过 FileInfo.nestedEnums 索引，识别为 raw 状态机。"""
    outer_rel = "infra/ContractEnum.java"
    _write(tmp_path, outer_rel, "package com.x; public class ContractEnum {}")
    outer_fi = _fi(outer_rel, "ContractEnum", "class", qualified_name="com.x.ContractEnum")
    outer_fi["nestedEnums"] = [{
        "name": "ContFlowStatusEnum",
        "qualifiedName": "com.x.ContractEnum.ContFlowStatusEnum",
        "values": ["CON_INIT", "CON_UNDER", "CON_SUCCESS"],
        "deprecated": False,
    }]
    sms = StateMachineScanner(str(tmp_path)).scan([outer_fi])
    sm = next((s for s in sms if s.name == "ContFlowStatusEnum"), None)
    assert sm is not None
    assert sm.framework == "raw"
    assert sm.detection == "heuristic"
    assert set(sm.states) == {"CON_INIT", "CON_UNDER", "CON_SUCCESS"}


def test_nested_enum_two_level_reference_transition(tmp_path):
    """嵌套枚举双层引用转换：Outer.Enum.X.getCode() 赋值 + StrUtil.equals 守卫配对。"""
    parent_qn = "com.x.ContractEnum"
    outer_rel = "infra/ContractEnum.java"
    _write(tmp_path, outer_rel, "package com.x; public class ContractEnum {}")
    outer_fi = _fi(outer_rel, "ContractEnum", "class", qualified_name=parent_qn)
    outer_fi["nestedEnums"] = [{
        "name": "FlowStatus",
        "qualifiedName": parent_qn + ".FlowStatus",
        "values": ["INIT", "UNDER", "DONE"],
        "deprecated": False,
    }]
    svc_rel = "app/Svc.java"
    _write(tmp_path, svc_rel,
           f"package com.x;\nimport {parent_qn};\n"
           "public class Svc {\n"
           "    public void go() {\n"
           "        if (StrUtil.equals(entity.getStatus(), ContractEnum.FlowStatus.UNDER.getCode())) {\n"
           "            entity.setStatus(ContractEnum.FlowStatus.DONE.getCode());\n"
           "        }\n"
           "    }\n}\n")
    svc_fi = _fi(svc_rel, "Svc", "class", imports=[parent_qn])
    sm = next(s for s in StateMachineScanner(str(tmp_path)).scan([outer_fi, svc_fi])
              if s.name == "FlowStatus")
    assert ("UNDER", "DONE") in {(t.source, t.target) for t in sm.transitions}


def test_nearest_guard_pairing_avoids_cartesian(tmp_path):
    """多守卫×多赋值：每个赋值只配对最近前置守卫，非全组合（消除笛卡尔积误报）。"""
    enum_rel = "domain/FlowStatus.java"
    enum_qn = "com.x.FlowStatus"
    _write(tmp_path, enum_rel, "package com.x; enum FlowStatus { INIT, UNDER, DONE; }")
    enum_fi = _fi(enum_rel, "FlowStatus", "enum",
                 ["INIT", "UNDER", "DONE"], qualified_name=enum_qn)
    svc_rel = "app/Svc.java"
    _write(tmp_path, svc_rel,
           "package com.x;\nimport com.x.FlowStatus;\n"
           "public class Svc {\n"
           "    public void t() {\n"
           "        if (Objects.equals(s.getStatus(), FlowStatus.UNDER.getCode())) {\n"
           "            s.setStatus(FlowStatus.DONE.getCode());\n"
           "        }\n"
           "        if (Objects.equals(s.getStatus(), FlowStatus.INIT.getCode())) {\n"
           "            s.setStatus(FlowStatus.UNDER.getCode());\n"
           "        }\n"
           "    }\n}\n")
    svc_fi = _fi(svc_rel, "Svc", "class", imports=[enum_qn])
    sm = next(s for s in StateMachineScanner(str(tmp_path)).scan([enum_fi, svc_fi])
              if s.name == "FlowStatus")
    trans = {(t.source, t.target) for t in sm.transitions}
    assert ("UNDER", "DONE") in trans
    assert ("INIT", "UNDER") in trans
    assert ("INIT", "DONE") not in trans  # 笛卡尔积误报被消除
