package com.example.order.domain;

/**
 * badcase 004：状态枚举但未引入状态机框架。
 * 期望规则：STATE_MACHINE（推荐，治理提醒）。
 */
enum OrderStatus { INIT, PAID, SHIPPED, CANCELLED }
