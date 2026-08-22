package com.example.order.domain.entity;

// 静态导入框架成员（宿主类 TransactionSynchronizationManager 非注解白名单）
// 期望规则：DOMAIN_PURITY（强制）—— 修复前 ^import\s+([\w.]+) 捕获到 "static"，漏报
import static org.springframework.transaction.support.TransactionSynchronizationManager.getCurrentTransactionName;

// 内部包通配 import：无法定位目标类，不猜层
// 期望规则：结构性债务（"通配 import 无法定位目标类，待 ArchUnit 复核"），不计入 mandatory_count
import com.example.other.adapter.web.*;

/*
import org.springframework.web.client.RestTemplate;
*/

public class OrderE {
    // class FooDTO —— 注释里的命名不应触发 NAMING
    /**
     * class XxxPO —— javadoc 内命名不应触发 NAMING
     */
    private String note;
}
