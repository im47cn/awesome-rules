"""doc-gen 共享类型与常量定义"""

from dataclasses import dataclass, field
from typing import Optional, TypedDict

# ── 常量 ──────────────────────────────────────────────────────────────────────

MAVEN_NS = "http://maven.apache.org/POM/4.0.0"
SKIP_DIRS = {"target", "build", ".git", "node_modules", ".idea", ".vscode",
             ".gradle", ".mvn", "dist", "out", ".next", ".nuxt", "test", "tests"}

# DDD 层识别关键字
LAYER_PATTERNS = {
    "adapter":        [r"/adapter/", r"/controller/", r"/consumer/", r"/scheduler/",
                       r"/interfaces/", r"/web/", r"/rest/", r"/api/"],
    "client":         [r"/client/"],
    "application":    [r"/application/", r"/app/", r"/executor/", r"/assembler/",
                       r"/validator/", r"/interceptor/"],
    "domain":         [r"/domain/", r"/entity/", r"/valueobject/", r"/repository/",
                       r"/service/", r"/event/", r"/extensionpoint/"],
    "infrastructure": [r"/infrastructure/", r"/infra/", r"/persistence/",
                       r"/external/", r"/extension/", r"/config/"],
    # start 层：启动模块路径(辅助识别; 主识别靠 @SpringBootApplication 注解)
    "start":          [r"/start/", r"/bootstrap/", r"/launcher/"],
}

# 后缀到组件类型的映射
# 注意：多词后缀必须放在单词后缀前面（按长度降序匹配），
# 否则 "OrderRepositoryImpl" 会被 "Impl" 误匹配而不是 "RepositoryImpl"
# 该顺序有单元测试保护，请勿随意调整
SUFFIX_TYPE_MAP_ORDERED = [
    # ── Adapter 层 ──
    ("Controller",      "adapter",      "controller"),
    ("Consumer",        "adapter",      "consumer"),
    ("Scheduler",       "adapter",      "scheduler"),
    ("Job",             "adapter",      "scheduler"),  # xxl-job handler 类
    # ── Client 层 ──（COLA: ServiceI/CO/Cmd + GTSP: Inter/DTO/Command）
    ("ServiceI",        "client",       "serviceInterface"),
    ("Inter",           "client",       "feignInterface"),
    ("CO",              "client",       "clientObject"),
    ("DTO",             "client",       "dataTransferObject"),
    ("Cmd",             "client",       "command"),
    ("Command",         "client",       "command"),
    ("Query",           "client",       "query"),
    # ── Application 层 ──（GTSP 补充 AppService/Handler/Manager）
    ("CmdExe",          "application",  "executor"),
    ("QryExe",          "application",  "executor"),
    ("AppService",      "application",  "appService"),
    ("Assembler",       "application",  "assembler"),
    ("Handler",         "application",  "handler"),
    ("Manager",         "application",  "manager"),
    ("Validator",       "application",  "validator"),
    # ── Domain 层 ──
    ("DomainService",   "domain",       "domainService"),
    ("Repository",      "domain",       "repositoryInterface"),
    ("ExtPt",           "domain",       "extensionPoint"),
    ("Event",           "domain",       "domainEvent"),
    # 完整后缀优先（业界主流命名 XxxEntity / XxxVO / XxxValueObject），
    # 单字母 E/V 仅匹配末字符恰为 E/V 的类（如 OrderE/OrderV）。
    # 二者不互为后缀（"Entity"末尾为 y，"VO"末尾为 O），故无顺序冲突。
    ("ValueObject",     "domain",       "valueObject"),
    ("Entity",          "domain",       "entity"),
    ("VO",              "domain",       "valueObject"),
    ("V",               "domain",       "valueObject"),
    ("E",               "domain",       "entity"),
    ("BO",              "domain",       "entity"),  # GTSP: 领域实体(Business Object)
    # ── Infrastructure 层 ──（COLA: DO + GTSP: PO/Converter/Constant/Enum/Exception）
    ("RepositoryImpl",  "infrastructure", "repositoryImpl"),
    ("GatewayImpl",     "infrastructure", "gatewayImpl"),
    ("Gateway",         "infrastructure", "gateway"),
    ("DO",              "infrastructure", "dataObject"),
    ("PO",              "infrastructure", "persistentObject"),
    ("Mapper",          "infrastructure", "mapper"),
    ("Converter",       "infrastructure", "converter"),
    ("Constant",        "infrastructure", "constant"),
    ("Exception",       "infrastructure", "exception"),
    ("Enum",            "infrastructure", "enum"),  # 技术分类枚举兜底；状态枚举由包路径归 domain
    ("Ext",             "infrastructure", "extension"),
]

# Controller 相关注解
CONTROLLER_ANNOTATIONS = [
    "RestController", "Controller",
]

# 启动类注解(COLA/GTSP start 模块启动类，识别为 start 层)
STARTUP_ANNOTATIONS = [
    "SpringBootApplication", "EnableAutoConfiguration",
]

# HTTP 方法注解
HTTP_MAPPING_ANNOTATIONS = {
    "PostMapping":    "POST",
    "GetMapping":     "GET",
    "PutMapping":     "PUT",
    "DeleteMapping":  "DELETE",
    "PatchMapping":   "PATCH",
    "RequestMapping": "REQUEST",
}

# Java 类型 → SQL 类型映射（InfrastructureDBExtractor / POScanner 共享）
JPA_TYPE_MAP = {
    "String": "varchar(255)",
    "Long": "bigint", "long": "bigint",
    "Integer": "int", "int": "int",
    "BigDecimal": "decimal(18,2)",
    "LocalDateTime": "datetime", "Date": "datetime",
    "Boolean": "tinyint(1)", "boolean": "tinyint(1)",
    "Double": "double", "double": "double",
    "Float": "float", "float": "float",
    "byte[]": "blob",
}


# ── 数据结构 ──────────────────────────────────────────────────────────────────


class JavaMethodInfo(TypedDict):
    """Java 方法信息（JavaScanner 提取）"""
    returnType: str
    name: str
    params: str
    deprecated: bool


class JavaFieldInfo(TypedDict):
    """Java 字段信息（JavaScanner 提取）"""
    type: str
    name: str
    deprecated: bool


class FileInfo(TypedDict):
    """Java 文件扫描结果（JavaScanner._parse_java_file 返回）"""
    filePath: str
    package: str
    qualifiedName: str
    className: str
    classType: str
    annotations: list
    imports: list
    methods: list  # list[JavaMethodInfo]
    fields: list   # list[JavaFieldInfo]
    enumValues: list  # 枚举常量（仅 enum，JavaScanner._parse_java_file 已填充）
    deprecated: bool  # 类级 @Deprecated（注解或 @deprecated Javadoc，仅看类声明前）
    nestedEnums: list  # 嵌套枚举（仅 class，[{"name","qualifiedName","values","deprecated"}]）


@dataclass
class EndpointDoc:
    method: str
    path: str
    summary: str = ""
    requestBody: str = ""
    responseBody: str = ""
    openapiSpecRef: str = ""
    deprecated: bool = False


@dataclass
class MqChannelDoc:
    """MQ 通道声明（producer 发布 / consumer 订阅），供鹰眼跨项目 MQ 边对齐"""
    role: str          # producer / consumer
    channel: str       # topic/queue 名（全局命名空间，跨项目精确匹配）
    framework: str     # rocketmq / kafka / rabbit
    via: str           # 触发注解或调用（RocketMQMessageListener / syncSend / ...）


@dataclass
class CacheKeyDoc:
    """缓存 key 声明（读写共享），供鹰眼跨项目共享缓存耦合边对齐"""
    key: str           # key 字面量/前缀模式（运行时拼接的静态证据本就是模式）
    via: str           # redisTemplate.get / @Cacheable / ...


@dataclass
class ScheduleDoc:
    """定时任务资产（xxl-job handler / Spring @Scheduled）。

    注：定时任务无强跨项目边语义（跨项目任务链配置在调度中心，代码不可见），
    仅作资产清单供全景观测（C02 站点）与项目内影响链（deps BFS 已覆盖）。
    """
    handler: str       # handler 名或方法名
    cron: str = ""     # @Scheduled cron（@XxlJob 的 cron 在调度中心配置，为空）
    via: str = ""      # XxlJob / Scheduled


@dataclass
class ComponentDoc:
    type: str                        # controller, executor, entity, repository, etc.
    className: str
    qualifiedName: str = ""
    sourcePath: str = ""
    sourceLine: int = 0              # 类声明起始行（L2 行级 evidence 锚点，0=未知）
    description: str = ""
    annotations: list = field(default_factory=list)
    endpoints: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    methods: list = field(default_factory=list)
    fields: list = field(default_factory=list)
    interfaces: list = field(default_factory=list)
    classType: str = ""                # class, interface, enum, @interface
    enumValues: list = field(default_factory=list)  # 枚举常量（仅 enum）
    deprecated: bool = False            # 类级 @Deprecated（整个组件废弃）
    deps: list = field(default_factory=list)  # 项目内依赖边（import 的本项目 qn），供 /impact/ 前端 BFS
    mqChannels: list = field(default_factory=list)  # list[MqChannelDoc]，MQ producer/consumer 声明
    cacheKeys: list = field(default_factory=list)   # list[CacheKeyDoc]，Redis key 声明
    schedules: list = field(default_factory=list)   # list[ScheduleDoc]，定时任务资产



@dataclass
class FieldDoc:
    name: str
    type: str
    kind: str = ""                   # identifier, valueObject, enum, entityCollection
    comment: str = ""
    deprecated: bool = False          # 字段级 @Deprecated


@dataclass
class AggregateDoc:
    name: str
    rootEntity: Optional[ComponentDoc] = None
    entities: list = field(default_factory=list)
    valueObjects: list = field(default_factory=list)
    domainServices: list = field(default_factory=list)
    repositoryInterface: Optional[ComponentDoc] = None
    domainEvents: list = field(default_factory=list)
    # "aggregate"=有聚合根实体的标准聚合; "behavior"=行为域/能力域(领域层仅含
    # 服务/网关/值对象, 无聚合根), 前端据此渲染「行为域」标识而非伪聚合根。
    kind: str = "aggregate"


@dataclass
class LayerDoc:
    javaPackage: str = ""
    mavenModule: str = ""
    components: list = field(default_factory=list)
    aggregates: list = field(default_factory=list)


@dataclass
class DomainDoc:
    name: str
    displayName: str = ""
    description: str = ""
    modulePrefix: str = ""
    layers: dict = field(default_factory=lambda: {
        "start": LayerDoc(),
        "adapter": LayerDoc(),
        "client": LayerDoc(),
        "application": LayerDoc(),
        "domain": LayerDoc(),
        "infrastructure": LayerDoc(),
    })


@dataclass
class TableColumnDoc:
    name: str
    type: str
    comment: str = ""
    primaryKey: bool = False
    nullable: bool = True
    unique: bool = False
    defaultValue: str = ""


@dataclass
class TableIndexDoc:
    name: str
    columns: list = field(default_factory=list)
    unique: bool = False


@dataclass
class TableDoc:
    name: str
    comment: str = ""
    columns: list = field(default_factory=list)
    indexes: list = field(default_factory=list)


@dataclass
class StateTransitionDoc:
    """状态机的一条转换（用 source/target 避开 Python 关键字 from）"""
    source: str = ""
    target: str = ""
    event: str = ""
    guard: str = ""


@dataclass
class StateMachineIssueDoc:
    """状态机质量审查问题"""
    type: str = ""        # dead_state / unreachable / missing_transition / no_initial / no_end / multi_initial
    severity: str = ""    # critical / warning / info
    message: str = ""


@dataclass
class StateMachineDoc:
    """一个状态机的完整文档（含质量审查）。

    framework: spring(Spring StateMachine) / cola(Cola Statemachine) / raw(裸 enum+switch)
    """
    name: str
    framework: str = "raw"
    detection: str = "explicit"  # explicit=Spring/Cola 框架; heuristic=裸 enum 启发式(隐式状态字段+分支)
    sourceClass: str = ""
    sourcePath: str = ""
    managedEnum: str = ""    # 被 spring/cola 状态机管理的状态枚举类名（去重关联 + 展示语义）
    states: list = field(default_factory=list)           # list[str]
    initialState: str = ""
    endStates: list = field(default_factory=list)        # list[str]
    transitions: list = field(default_factory=list)      # list[StateTransitionDoc]
    issues: list = field(default_factory=list)           # list[StateMachineIssueDoc]


@dataclass
class DiagramSet:
    architectureOverview: str = ""
    layeredDependency: str = ""
    layerDependencyReal: str = ""   # 层间真实依赖(基于 IMPORTS), 违规跨层边标红
    domainAggregates: dict = field(default_factory=dict)
    erDiagram: str = ""
    eventFlow: str = ""
    externalTopology: str = ""
    stateMachines: dict = field(default_factory=dict)    # {状态机名: stateDiagram-v2 文本}


@dataclass
class CrossDomainDep:
    fromDomain: str
    toDomain: str
    type: str                        # client-api, domain-event, shared-valueobject
    description: str = ""
    evidence: str = ""


# ── 业务上下文（business-context.json 可选扩展分片，AH-MANIFEST §5）─────────


@dataclass
class BusinessItemDoc:
    """客户/角色/业务场景条目（人工 md 叙事为主 + 代码弱信号锚定为辅）"""
    name: str
    description: str = ""
    source: str = "manual"           # manual / code / hybrid
    domain: str = ""                 # 场景归属域（仅 scenarios）
    anchors: list = field(default_factory=list)  # 锚定 qn / METHOD /path / 表名


@dataclass
class BusinessFlowStepDoc:
    """流程步骤：步骤名 → 锚点表达式（锚定 qualifiedName / METHOD /path / 表名）"""
    name: str
    description: str = ""
    anchors: list = field(default_factory=list)


@dataclass
class BusinessFlowDoc:
    """业务流程：人工 md（### 流程名 + 有序步骤）或状态机弱信号"""
    name: str
    description: str = ""
    steps: list = field(default_factory=list)   # list[BusinessFlowStepDoc]
    source: str = "manual"
    anchors: list = field(default_factory=list)


@dataclass
class BusinessContextDoc:
    """业务维度扩展块（business-context.json 可选分片，全空时不产出）"""
    customers: list = field(default_factory=list)  # list[BusinessItemDoc]
    roles: list = field(default_factory=list)
    scenarios: list = field(default_factory=list)
    flows: list = field(default_factory=list)      # list[BusinessFlowDoc]


@dataclass
class DocManifest:
    meta: dict = field(default_factory=dict)
    domains: list = field(default_factory=list)
    diagrams: DiagramSet = field(default_factory=DiagramSet)
    openapiSpecs: dict = field(default_factory=dict)
    database: dict = field(default_factory=lambda: {"tables": []})
    businessContext: BusinessContextDoc = None  # 可选扩展分片；None 则不写出
    crossDomainDependencies: list = field(default_factory=list)
    stateMachines: list = field(default_factory=list)    # list[StateMachineDoc]
