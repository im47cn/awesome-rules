"""Java 源码扫描器，提取类、方法、注解信息。"""

import re
from pathlib import Path
from typing import Optional

from doctypes import SKIP_DIRS, FileInfo


class JavaScanner:
    """Java 源码扫描，提取类、方法、注解信息"""

    # 注解提取正则
    ANNOTATION_RE = re.compile(r'@(\w+)(?:\(([^)]*)\))?')
    # 包声明
    PACKAGE_RE = re.compile(r'package\s+([\w.]+)\s*;')
    # import 语句
    IMPORT_RE = re.compile(r'import\s+([\w.*]+)\s*;')
    # 类/接口声明
    CLASS_RE = re.compile(
        r'(?:public\s+)?(?:abstract\s+)?(?:final\s+)?'
        r'(class|interface|enum|@interface)\s+(\w+)'
        r'(?:\s+extends\s+(\w+))?'
        r'(?:\s+implements\s+([\w,\s]+))?'
    )
    # 方法声明（简化版）
    METHOD_RE = re.compile(
        r'(?:public|protected|private)\s+'
        r'(?:static\s+)?(?:final\s+)?(?:abstract\s+)?'
        r'(?:<[\w\s,?]+>\s+)?'
        r'(\w+(?:<[\w\s,?]+>)?)\s+'
        r'(\w+)\s*\(([^)]*)\)'
    )
    # 字段声明（简化版）
    FIELD_RE = re.compile(
        r'(?:public|protected|private)\s+'
        r'(?:static\s+)?(?:final\s+)?'
        r'(\w+(?:<[\w\s,?]+>)?)\s+'
        r'(\w+)\s*[=;]'
    )
    # 已知局限：正则解析无法覆盖的 Java 语法（AST 解析才能处理）。
    # 文档生成时通过此标志位提示用户。
    KNOWN_LIMITATIONS = [
        "泛型嵌套 > 2 层（如 Map<String, List<Map<Integer, String>>>）",
        "Lambda 表达式、匿名内部类",
        "字符串字面量内出现 class/@ 关键字（已处理注释但不处理字符串内容）",
        "多注解合并（如 @A @B class Foo）",
        "文本块（text block）含换行和缩进",
    ]

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()

    def scan_java_files(self) -> list[FileInfo]:
        """扫描所有 Java 文件，返回解析结果列表"""
        results = []
        java_files = list(self.root_path.rglob("*.java"))

        for java_file in java_files:
            if not self._should_scan(java_file):
                continue

            result = self._parse_java_file(java_file)
            if result:
                results.append(result)

        return results

    def _should_scan(self, file_path: Path) -> bool:
        """判断是否应该扫描该文件"""
        parts = file_path.parts
        for skip in SKIP_DIRS:
            if skip in parts:
                return False
        return True

    def _parse_java_file(self, file_path: Path) -> Optional[FileInfo]:
        """解析单个 Java 文件"""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return None

        # 使用简单正则（比正则健壮，但不处理注释内的假匹配）
        content_clean = self._strip_comments(content)

        package = self._extract_first(self.PACKAGE_RE, content_clean)
        class_match = self.CLASS_RE.search(content_clean)
        if not class_match:
            return None

        class_type = class_match.group(1)
        class_name = class_match.group(2)
        # 类声明起始行（等长保证下 offset 直接映射原文行号；L2 行级 evidence 锚点）
        class_line = content_clean[:class_match.start()].count('\n') + 1

        # 类级废弃：仅看类声明前的注解段（含 _strip_comments 转写的 @deprecated Javadoc），
        # 避免全文件 annotations 误把字段/方法上的 @Deprecated 算作类级废弃
        class_deprecated = self._deprecated_above(content_clean, class_match.start())

        # 提取注解
        annotations = [m.group(1) for m in self.ANNOTATION_RE.finditer(content_clean)]

        # 提取 import
        imports = [m.group(1) for m in self.IMPORT_RE.finditer(content_clean)]

        # 提取方法（仅 public/protected；line 为原文行号——_strip_comments
        # 等长替换保证 content_clean 的 offset 可直接换算行号）
        methods = []
        for m in self.METHOD_RE.finditer(content_clean):
            methods.append({
                "returnType": m.group(1),
                "name": m.group(2),
                "params": m.group(3),
                "line": content_clean[:m.start()].count('\n') + 1,
                "deprecated": self._deprecated_above(content_clean, m.start()),
            })

        # 提取字段（仅 private/protected）
        fields = []
        for m in self.FIELD_RE.finditer(content_clean):
            fields.append({
                "type": m.group(1),
                "name": m.group(2),
                "deprecated": self._deprecated_above(content_clean, m.start()),
            })

        # 提取枚举常量（仅 enum 类型；常量列表位于 { 与首个 ; / } 之间）
        enum_values = []
        if class_type == "enum":
            enum_body = re.search(
                r'enum\s+' + re.escape(class_name) + r'\s*(?:implements\s+[\w, ]+\s*)?\{([^;}]*)(?:;|\})',
                content_clean,
            )
            if enum_body:
                # 枚举常量为纯大写标识符（最后一个常量后可能无逗号，直接 } ）
                enum_values = re.findall(r'\b([A-Z][A-Z0-9_]*)\b', enum_body.group(1))

        # 计算相对路径
        try:
            rel_path = str(file_path.relative_to(self.root_path))
        except ValueError:
            rel_path = str(file_path)

        qualified_name = f"{package}.{class_name}" if package else class_name

        # 提取嵌套枚举（仅 class；Java 枚举不能再嵌套枚举）。
        # 嵌套枚举对多数扫描器不可见，仅在 FileInfo.nestedEnums 携带，供 StateMachineScanner 消费。
        nested_enums = []
        if class_type == "class":
            for m in self.CLASS_RE.finditer(content_clean):
                nt, nn = m.group(1), m.group(2)
                if nt == "enum" and nn != class_name:
                    body = re.search(
                        r'enum\s+' + re.escape(nn) +
                        r'\s*(?:implements\s+[\w, ]+\s*)?\{([^;}]*)(?:;|\})',
                        content_clean,
                    )
                    vals = re.findall(r'\b([A-Z][A-Z0-9_]*)\b', body.group(1)) if body else []
                    nested_enums.append({
                        "name": nn,
                        "qualifiedName": f"{qualified_name}.{nn}",
                        "values": vals,
                        "deprecated": self._deprecated_above(content_clean, m.start()),
                    })

        return {
            "filePath": rel_path,
            "package": package or "",
            "qualifiedName": qualified_name,
            "className": class_name,
            "classType": class_type,
            "classLine": class_line,
            "annotations": annotations,
            "imports": imports,
            "methods": methods,
            "fields": fields,
            "enumValues": enum_values,
            "nestedEnums": nested_enums,
            "deprecated": class_deprecated,
        }

    @staticmethod
    def _strip_comments(content: str) -> str:
        """移除 Java 注释语义，保留字符串字面量内的注释标记。

        **等长替换**：注释字符原地替换为空格（换行保留），保证
        len(result) == len(content) 且换行位置不变——正则匹配的 offset
        可直接映射回原文行号（v2 方法级 diff / 行级 evidence 的基石）。
        同时保留废弃语义：块注释内的 @deprecated（11 字符）原地等长
        转写为 @Deprecated（恰好 11 字符），使注解提取与回看检测能统一
        识别 @Deprecated 注解与 @deprecated Javadoc 标签两种写法。
        """
        result: list[str] = []
        i = 0
        n = len(content)
        while i < n:
            # 块注释 /* ... */ → 空格（保留 \n；@deprecated 等长转写）
            if i + 1 < n and content[i] == '/' and content[i + 1] == '*':
                end = content.find('*/', i + 2)
                if end >= 0:
                    block = content[i + 2:end]
                    replaced = re.sub(r'@deprecated\b', '@Deprecated',
                                      block, flags=re.IGNORECASE)
                    # 等长：边界 /* 与 */ → 2 空格；块内 \n 保留、其余→空格，
                    # 唯独转写出的 @Deprecated 标记（与 @deprecated 等长）原样保留
                    result.append('  ')
                    for part in re.split(r'(@Deprecated)', replaced):
                        if part == '@Deprecated':
                            result.append(part)
                        else:
                            result.append(''.join('\n' if c == '\n' else ' '
                                                   for c in part))
                    result.append('  ')
                    i = end + 2
                else:
                    # 未闭合：剩余全部视为注释（等长空格化）
                    while i < n:
                        result.append('\n' if content[i] == '\n' else ' ')
                        i += 1
            # 行注释 // ... 到行尾 → 空格（不含 \n）
            elif i + 1 < n and content[i] == '/' and content[i + 1] == '/':
                result.append('  ')
                i += 2
                while i < n and content[i] != '\n':
                    result.append(' ')
                    i += 1
            # 字符串字面量：保留内容（不处理内部注释标记）
            elif content[i] == '"':
                result.append('"')
                i += 1
                while i < n and content[i] != '"':
                    if content[i] == '\\' and i + 1 < n:
                        result.append(content[i])
                        result.append(content[i + 1])
                        i += 2
                    else:
                        result.append(content[i])
                        i += 1
                if i < n:
                    result.append('"')
                    i += 1
            # 字符字面量：保留内容
            elif content[i] == "'":
                result.append("'")
                i += 1
                while i < n and content[i] != "'":
                    if content[i] == '\\' and i + 1 < n:
                        result.append(content[i])
                        result.append(content[i + 1])
                        i += 2
                    else:
                        result.append(content[i])
                        i += 1
                if i < n:
                    result.append("'")
                    i += 1
            else:
                result.append(content[i])
                i += 1
        return ''.join(result)

    @staticmethod
    def _deprecated_above(content: str, pos: int) -> bool:
        """pos 处声明是否被 @Deprecated 标记。

        以声明为锚点回看到上一个成员边界(;}/{)，在「本声明注解段」内查找，
        覆盖 @Deprecated 夹在其他注解之间的情况（如 @TableField @Deprecated private x）。
        content 须为 _strip_comments 后的结果——@deprecated Javadoc 已转写为 @Deprecated。
        """
        pre_region = content[max(0, pos - 300):pos]
        last_sep = max(pre_region.rfind(';'), pre_region.rfind('}'), pre_region.rfind('{'))
        anno_region = pre_region[last_sep + 1:] if last_sep >= 0 else pre_region
        return bool(re.search(r'@Deprecated(?:\([^)]*\))?', anno_region))

    @staticmethod
    def _extract_first(pattern: re.Pattern, content: str) -> Optional[str]:
        m = pattern.search(content)
        return m.group(1) if m else None
