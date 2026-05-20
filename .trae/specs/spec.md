# 智能劝学系统 P0优化 - Product Requirement Document

## Overview
- **Summary**: 对智能劝学系统进行核心优化，包括数据持久化、多模态融合识别、Web界面现代化三大核心功能
- **Purpose**: 解决当前系统识别准确率低、界面简陋、数据易丢失的问题
- **Target Users**: 学生、家长、教师

## Goals
1. 实现数据持久化（SQLite），防止数据丢失
2. 提高活动识别准确率至85%以上
3. 提供现代化、功能完善的Web日志界面
4. 为后续P1/P2优化奠定基础

## Non-Goals (Out of Scope)
- 不实现用户认证和权限管理
- 不实现机器学习辅助识别
- 不重构GUI界面（留待P1阶段）
- 不实现多用户支持

## Background & Context
当前系统问题：
1. 数据存储在内存，重启后丢失
2. 识别方式单一，误判漏判严重
3. Web界面简陋，功能不完善

## Functional Requirements
- **FR-1**: SQLite数据库存储活动日志
- **FR-2**: 配置文件持久化（JSON）
- **FR-3**: 多模态融合识别（OCR+进程+窗口标题）
- **FR-4**: 时间窗口分析（连续3次确认）
- **FR-5**: 现代化Web界面（Bootstrap+ECharts）
- **FR-6**: Web端数据可视化和时间筛选

## Non-Functional Requirements
- **NFR-1**: 识别准确率 &gt;= 85%
- **NFR-2**: 数据库操作响应时间 &lt; 100ms
- **NFR-3**: Web界面加载时间 &lt; 2s
- **NFR-4**: 向后兼容现有配置

## Constraints
- **Technical**: 保持Python技术栈，使用SQLite
- **Business**: 优先完成P0任务，不扩展范围
- **Dependencies**: 需要安装pygetwindow库

## Assumptions
- 用户已安装项目基础依赖
- 用户环境支持Python 3.7+
- Tesseract-OCR可用性检测保持现有逻辑

## Acceptance Criteria

### AC-1: 数据持久化
- **Given**: 系统运行中
- **When**: 记录活动日志
- **Then**: 日志保存到SQLite数据库，服务重启后数据不丢失
- **Verification**: programmatic

### AC-2: 多模态融合识别
- **Given**: 系统正在监控
- **When**: 进行活动检测
- **Then**: 同时使用OCR、进程、窗口标题三种方式，加权融合结果
- **Verification**: programmatic

### AC-3: 时间窗口分析
- **Given**: 系统正在监控
- **When**: 检测到娱乐活动
- **Then**: 只有连续3次检测结果一致才触发提醒
- **Verification**: programmatic

### AC-4: Web界面现代化
- **Given**: 访问服务端Web界面
- **When**: 查看活动日志
- **Then**: 显示现代化界面，包含图表、时间戳、筛选功能
- **Verification**: human-judgment

## Open Questions
- 无
