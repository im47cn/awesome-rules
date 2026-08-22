"""SUFFIX_TYPE_MAP_ORDERED 结构不变量与分类契约测试

设计依据（第一性分析）：
classify() 遍历 SUFFIX_TYPE_MAP_ORDERED，返回第一个 endswith 命中的后缀。
因此「顺序敏感」当且仅当存在两个后缀 A、B，使得某个类名同时 endswith 两者
—— 等价于 A endswith B（一个后缀是另一个的后缀）。

经分析，当前表内无此类重叠对，故分类结果与顺序无关。本测试用两层保护：
1. 结构不变量：断言表内无重叠后缀对（保证顺序无关）；
   将来若加入会冲突的后缀（如 Impl、Service），本测试立即失败，强制处理顺序。
2. 行为契约：通过 LayerIdentifier.classify 验证关键类名的分类正确。
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from doctypes import SUFFIX_TYPE_MAP_ORDERED, FileInfo
from generator.layers import LayerIdentifier


# ── 结构不变量：表内无重叠后缀对 ──────────────────────────────────────────────


def test_should_have_no_overlapping_suffix_pairs_when_table_is_safe():
    """表内任意两个后缀不得互为彼此的后缀（A≠B 且 A endswith B）。

    若违反，则分类结果取决于两者在表中的先后顺序 —— 即引入真正的顺序依赖。
    此时必须显式保证长后缀排在短后缀之前，否则 classify 会误匹配。
    """
    suffixes = [s for s, _, _ in SUFFIX_TYPE_MAP_ORDERED]
    overlaps = []
    for a in suffixes:
        for b in suffixes:
            if a != b and a.endswith(b):
                overlaps.append((a, b))
    assert not overlaps, (
        "发现重叠后缀对，分类结果将依赖顺序，必须保证长后缀在短后缀之前: "
        + ", ".join(f"{a!r} contains {b!r}" for a, b in overlaps)
    )


def test_should_have_no_duplicate_suffix_when_table_is_defined():
    """后缀不得重复（否则一条规则被覆盖，且暗示维护者意图不清）。"""
    suffixes = [s for s, _, _ in SUFFIX_TYPE_MAP_ORDERED]
    assert len(suffixes) == len(set(suffixes)), "存在重复后缀"


# ── 行为契约：多词后缀分类正确 ────────────────────────────────────────────────


@pytest.mark.parametrize("class_name,qualified_name,expected_layer,expected_type", [
    # 多词后缀（曾被认为是「顺序敏感」的案例，实际依赖无重叠性质）
    ("OrderRepositoryImpl", "com.example.order.infrastructure.OrderRepositoryImpl",
     "infrastructure", "repositoryImpl"),
    ("OrderGatewayImpl", "com.example.order.infrastructure.OrderGatewayImpl",
     "infrastructure", "gatewayImpl"),
    ("OrderCmdExe", "com.example.order.application.OrderCmdExe",
     "application", "executor"),
    ("OrderQryExe", "com.example.order.application.OrderQryExe",
     "application", "executor"),
    ("OrderDomainService", "com.example.order.domain.OrderDomainService",
     "domain", "domainService"),
    # 单词后缀
    ("OrderController", "com.example.order.adapter.OrderController",
     "adapter", "controller"),
    ("OrderE", "com.example.order.domain.entity.OrderE", "domain", "entity"),
    ("OrderV", "com.example.order.domain.valueobject.OrderV",
     "domain", "valueObject"),
    ("OrderCO", "com.example.order.client.OrderCO", "client", "clientObject"),
    ("OrderDO", "com.example.order.infrastructure.OrderDO",
     "infrastructure", "dataObject"),
    ("OrderEvent", "com.example.order.domain.event.OrderEvent",
     "domain", "domainEvent"),
    # GTSP 命名补充（02-naming §1）
    ("OrderInter", "com.example.order.client.OrderInter",
     "client", "feignInterface"),
    ("OrderDTO", "com.example.order.client.OrderDTO",
     "client", "dataTransferObject"),
    ("OrderCommand", "com.example.order.client.OrderCommand",
     "client", "command"),
    ("OrderAppService", "com.example.order.application.OrderAppService",
     "application", "appService"),
    ("OrderPO", "com.example.order.infrastructure.OrderPO",
     "infrastructure", "persistentObject"),
    ("OrderBO", "com.example.order.domain.entity.OrderBO",
     "domain", "entity"),
    ("OrderConverter", "com.example.order.infrastructure.OrderConverter",
     "infrastructure", "converter"),
    # COLA 命名补充（对外契约 ServiceI + Gateway 网关接口）
    ("OrderServiceI", "com.example.order.client.OrderServiceI",
     "client", "serviceInterface"),
    ("OrderGateway", "com.example.order.infrastructure.OrderGateway",
     "infrastructure", "gateway"),
], ids=[
    "RepositoryImpl", "GatewayImpl", "CmdExe", "QryExe", "DomainService",
    "Controller", "Entity-E", "ValueObject-V", "ClientObject-CO",
    "DataObject-DO", "DomainEvent",
    "GTSP-Inter", "GTSP-DTO", "GTSP-Command", "GTSP-AppService",
    "GTSP-PO", "GTSP-BO", "GTSP-Converter",
    "COLA-ServiceI", "COLA-Gateway",
])
def test_should_classify_correctly_when_suffix_matches(
    class_name, qualified_name, expected_layer, expected_type
):
    """类名后缀 → (layer, componentType) 分类契约。"""
    identifier = LayerIdentifier()
    file_info: FileInfo = {
        "filePath": qualified_name.replace(".", "/") + ".java",
        "package": "",
        "qualifiedName": qualified_name,
        "className": class_name,
        "classType": "class",
        "annotations": [],
        "imports": [],
        "methods": [],
        "fields": [],
    }
    result = identifier.classify(file_info)
    assert result == (expected_layer, expected_type), (
        f"{class_name} 期望 ({expected_layer}, {expected_type})，实际 {result}"
    )


# ── 包路径优先级契约（DDD 按层分包，优先于类名后缀）──────────────────────────


def test_should_prefer_package_layer_over_suffix_when_conflict():
    """infrastructure/repository/XRepositoryImpl 必须归到 infrastructure。

    包路径中的层段（application/interfaces/infrastructure/domain）最权威，
    覆盖类名后缀与子目录关键字，避免 infrastructure/repository/ 被 domain
    的 /repository/ 路径模式误判。
    """
    identifier = LayerIdentifier()
    file_info: FileInfo = {
        "filePath": "infra/src/main/java/com/example/order/infrastructure/repository/OrderRepositoryImpl.java",
        "package": "",
        "qualifiedName": "com.example.order.infrastructure.repository.OrderRepositoryImpl",
        "className": "OrderRepositoryImpl",
        "classType": "class",
        "annotations": [],
        "imports": [],
        "methods": [],
        "fields": [],
    }
    result = identifier.classify(file_info)
    assert result is not None
    layer, _ = result
    assert layer == "infrastructure", "包路径层段应优先于类名后缀与子目录关键字"


def test_should_return_none_when_no_layer_indicator_found():
    """无包路径层段、无已知后缀、无 Controller 注解的类应返回 None。"""
    identifier = LayerIdentifier()
    file_info: FileInfo = {
        "filePath": "src/main/java/com/example/UnknownThing.java",
        "package": "",
        "qualifiedName": "com.example.UnknownThing",
        "className": "UnknownThing",
        "classType": "class",
        "annotations": [],
        "imports": [],
        "methods": [],
        "fields": [],
    }
    assert identifier.classify(file_info) is None
