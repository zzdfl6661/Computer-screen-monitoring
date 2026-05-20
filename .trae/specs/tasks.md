# 智能劝学系统 P0优化 - Implementation Plan

## [x] Task 1: 数据持久化（SQLite）
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 创建SQLite数据库和activity_logs表
  - 重构server.py使用数据库存储
  - 重构client.py添加本地数据库支持
  - 实现配置文件持久化（config.json）
  - 为所有日志添加时间戳
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - programmatic: 验证数据保存到数据库
  - programmatic: 验证服务重启后数据不丢失
  - programmatic: 验证配置文件读写正常
- **Notes**: 表结构包含id, timestamp, activity, message, source字段

## [x] Task 2: 多模态融合识别 + 时间窗口分析
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 添加窗口标题获取功能（使用pygetwindow）
  - 实现三种识别方式的加权融合（进程0.6, OCR0.3, 窗口0.1）
  - 实现时间窗口队列，保存最近N次检测结果
  - 只有连续3次结果一致才触发提醒
  - 添加pygetwindow到依赖
- **Acceptance Criteria Addressed**: AC-2, AC-3
- **Test Requirements**:
  - programmatic: 验证三种识别方式都被调用
  - programmatic: 验证加权计算逻辑正确
  - programmatic: 验证时间窗口连续确认机制
- **Notes**: 保持向后兼容，OCR不可用时降级到进程+窗口

## [x] Task 3: Web界面现代化（Bootstrap + ECharts）
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 重构templates/index.html使用Bootstrap 5
  - 集成ECharts图表库
  - 添加仪表盘界面（关键指标卡片）
  - 添加饼图（学习/娱乐时间分布）
  - 添加折线图（时间趋势）
  - 添加时间筛选和搜索功能
  - 优化服务端API提供统计数据
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - human-judgment: 界面美观度检查
  - programmatic: 验证数据可视化功能
  - programmatic: 验证时间筛选功能正常
- **Notes**: 使用CDN引入Bootstrap和ECharts，无需本地安装

## Task 依赖关系图
Task1 → Task2
Task1 → Task3
