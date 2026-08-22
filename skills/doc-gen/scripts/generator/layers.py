"""DDD 分层识别器。

根据文件路径、类名后缀、注解将 Java 组件归类到 DDD 分层
（start / adapter / client / application / domain / infrastructure）。
COLA 与 GTSP 约定同时容纳: interfaces=COLA 别名, adapter=GTSP/COLA4, app=COLA 模块名。
"""

import re
from typing import Optional

from doctypes import (
    SUFFIX_TYPE_MAP_ORDERED,
    LAYER_PATTERNS,
    CONTROLLER_ANNOTATIONS,
    STARTUP_ANNOTATIONS,
    FileInfo,
)


class LayerIdentifier:
    """根据文件路径、类名后缀、注解识别 DDD 分层"""

    def classify(self, file_info: FileInfo) -> Optional[tuple[str, str]]:
        """
        返回 (layer, componentType) 或 None
        layer: start, adapter, client, application, domain, infrastructure
        """
        file_path = file_info.get("filePath", "")
        class_name = file_info.get("className", "")
        annotations = file_info.get("annotations", [])
        qualified_name = file_info.get("qualifiedName", "")
        parts = qualified_name.split(".")

        # 0. 包路径顶层 layer 段最权威(DDD 按层分包), 优先于类名后缀/子目录关键词
        #    避免 infrastructure/repository/x 被 domain 的 /repository/ 路径模式误判
        #    COLA+GTSP 约定同时容纳: interfaces(COLA别名)/adapter(GTSP·COLA4)/app(COLA模块名)
        PKG_LAYER = {
            "start": "start",
            "adapter": "adapter", "interfaces": "adapter",
            "client": "client",
            "application": "application", "app": "application",
            "domain": "domain",
            "infrastructure": "infrastructure", "infra": "infrastructure",
        }
        pkg_layer = next((PKG_LAYER[p] for p in parts if p in PKG_LAYER), None)
        if pkg_layer:
            # comp_type 按类名后缀细化(后缀只决定类型, 不覆盖 layer)；
            # 后缀不中时 @FeignClient 注解兜底（yp 实测: FileClient 裸 Client 后缀，
            # 若加 Client 后缀映射会与 FeignClient 重叠违反无重叠约束，故走注解）
            comp_type = next(
                (ct for sx, _, ct in SUFFIX_TYPE_MAP_ORDERED if class_name.endswith(sx)),
                "feignInterface" if "FeignClient" in annotations else pkg_layer,
            )
            return (pkg_layer, comp_type)

        # 1. 通过后缀识别（无明确 layer 包路径时, 多词后缀优先匹配）
        for suffix, layer, comp_type in SUFFIX_TYPE_MAP_ORDERED:
            if class_name.endswith(suffix):
                return (layer, comp_type)

        # 1b. @FeignClient 注解 → client 层 Feign 接口（先于路径识别，
        #     避免 /xxx/client/ 路径把类型兜底成类名小写）
        if "FeignClient" in annotations:
            return ("client", "feignInterface")

        # 2. 通过路径关键字识别
        path_lower = file_path.lower()
        for layer, patterns in LAYER_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, path_lower):
                    return (layer, class_name.lower())

        # 3. 通过注解推断
        if any(a in CONTROLLER_ANNOTATIONS for a in annotations):
            return ("adapter", "controller")

        # 3b. 启动类注解 → start 层(无后缀/无层段的启动类靠此识别)
        if any(a in STARTUP_ANNOTATIONS for a in annotations):
            return ("start", "application")

        # 4. 包含 repository 关键字但在 domain 路径
        if re.search(r'/domain/', path_lower) and 'Repository' in class_name:
            return ("domain", "repositoryInterface")

        return None

    def identify_domain_from_module(self, artifact_id: str, modules: dict) -> Optional[str]:
        """从 Maven 模块名提取业务域名"""
        # 移除已知的层后缀（含 GTSP 轻量档契约模块 -api 与实现模块 -core）
        suffixes = ["-adapter", "-client", "-start",
                    "-app", "-domain", "-infrastructure", "-infra",
                    "-common", "-shared", "-api", "-core"]
        name = artifact_id
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        return name if name else artifact_id
