# 跨境电商智能客服 Demo

> **Shopee 跨境电商场景化智能客服 Demo**：使用独立实现、合成数据与抽象规则构建的作品集项目。它不是 Shopee 官方系统，不连接 Shopee 生产环境，也不包含真实买家、订单、会话、业务规则或凭证。

## 展示什么

该 Demo 面向跨境电商买家常见的订单与售后问题，支持中文、英文及中英混合输入，并展示：

- 一级轻量意图召回（Top-3）与候选受限的二级 Claude 精排；
- 订单查询、物流追踪、物流异常、退货资格、退款进度和关税 FAQ；
- “查订单 → 改地址（预览）→ 显式确认 → 催发货（预览）→ 显式确认”的多轮链路；
- 会话中的当前订单继承与跨客户订单拒绝；
- MCP 统一暴露合成订单、物流、政策和工单工具；
- 后端确定性策略控制：LLM 不拥有 MCP 工具，也不能直接执行写操作；
- 冻结的合成评测集与离线回归测试。

## 核心架构

```text
HTTP Chat API
  → 会话状态与订单 ID 解析
  → 一级轻量 Top-3 意图召回
  → Claude 结构化精排（可选；仅候选集）
  → 确定性策略层
       ├─ 只读：调用合成订单 / 物流 / 政策工具
       └─ 写入：只创建待确认操作
  → 显式确认接口校验 digest、订单版本与时效
  → MCP / in-process 合成业务服务
```

所有业务事实来自 `data/synthetic/` 中的版本化虚构 fixture。服务重启会重置模拟写操作，这是刻意保留的 Demo 行为。

## 快速开始：离线模式

离线模式不需要模型 Key、不会发起网络模型调用，适合本地演示和测试。

```bash
git clone https://github.com/b-bzy/cross-border-ecommerce-customer-service-demo.git
cd cross-border-ecommerce-customer-service-demo
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

DEMO_ROUTER_MODE=offline \
DEMO_COMMERCE_TRANSPORT=in_process \
python -m uvicorn commerce_support_demo.main:app --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000/docs> 查看交互式 API 文档。

健康检查：

```bash
curl --fail http://127.0.0.1:8000/healthz
curl --fail http://127.0.0.1:8000/readyz
```

## 核心会话示例

### 1. 查询订单

```bash
curl --fail -X POST \
  http://127.0.0.1:8000/v1/conversations/demo-001/messages \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_id": "CUST-DEMO-001",
    "locale": "en-SG",
    "message": "Where is order ORD-DEMO-1001?"
  }'
```

响应会带有：路由阶段、候选意图、受控工具事件和合成 `source_id`。

### 2. 改地址：仅创建预览

```bash
curl --fail -X POST \
  http://127.0.0.1:8000/v1/conversations/demo-002/messages \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_id": "CUST-DEMO-001",
    "locale": "en-SG",
    "message": "Change delivery address for ORD-DEMO-1002",
    "slots": {"new_address": "99 Demo Crescent, Singapore"}
  }'
```

该请求**不会**修改订单。响应中的 `pending_action` 包含 `action_id` 与 `action_digest`。必须用独立确认接口执行写操作：

```bash
curl --fail -X POST \
  "http://127.0.0.1:8000/v1/actions/<action_id>/confirm" \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_id": "CUST-DEMO-001",
    "conversation_id": "demo-002",
    "decision": "confirm",
    "action_digest": "<action_digest>"
  }'
```

自然语言中的“确认 / yes”不会触发写入。确认接口会校验客户、会话、冻结参数、digest、操作时效和订单版本；重复确认只返回已保存的结果，不重复写入。

## Claude 二级精排

用户可选择 `hybrid` 或 `live_always` 模式接入 Claude。二级模型使用官方 Anthropic Python SDK 和 `claude-opus-5`，以 Pydantic structured output 返回意图选择、置信度、缺失槽位和澄清 / 转人工决定。

模型输入只包含：

- 当前未受信任的买家消息；
- locale；
- 已验证的安全槽位；
- 一级 Top-3 候选意图与得分。

模型**不接收**订单详情、完整会话、MCP 工具或写权限。业务策略、订单归属、退货资格、地址修改和催发货均由确定性后端处理。

配置本地环境变量或已登录的 Anthropic profile 后再运行：

```bash
DEMO_ROUTER_MODE=hybrid \
DEMO_COMMERCE_TRANSPORT=in_process \
DEMO_CLAUDE_MODEL=claude-opus-5 \
python -m uvicorn commerce_support_demo.main:app --host 127.0.0.1 --port 8000
```

> Live 模式会调用外部 API 并产生费用。默认测试、CI 和离线评测不会调用 Claude。

## MCP 模式

默认 `in_process` 模式便于无网络测试。要展示 MCP 协议边界，切换为：

```bash
DEMO_ROUTER_MODE=offline \
DEMO_COMMERCE_TRANSPORT=mcp \
python -m uvicorn commerce_support_demo.main:app --host 127.0.0.1 --port 8000
```

服务会启动本地 stdio MCP 子进程，提供以下受控工具：

- `orders_get`、`shipments_track`、`refunds_get`；
- `policies_get`、`returns_check_eligibility`；
- `orders_update_address`、`tickets_create_delivery_urge`；
- `handoffs_create`。

写工具必须收到由确认接口签发、绑定到固定参数与订单版本的短时 capability，不能由用户或模型自由拼装。

## 测试与评测

```bash
pytest
python -m commerce_support_demo.evals
```

评测产物写入被 Git 忽略的 `output/offline-evaluation.json`。它仅统计合成数据上的离线路由结果；在未实际执行、冻结测试集和记录口径之前，本仓库不会声称任何生产或绝对性能指标。

## 公开与隐私边界

- 所有 `CUST-DEMO-*`、`ORD-DEMO-*`、物流、地址、姓名、政策和工单均为虚构数据；
- 不提交 API Key、Token、`.env`、真实订单、客户会话、内部网址、企业源码或生产配置；
- 根目录已隔离旧的车载参考材料，公开提交时请只显式暂存本 Demo 的新文件，**不要使用** `git add .`；
- 该项目展示产品设计、受控 Agent 编排、MCP 工具边界、多轮状态和评测方法，不构成真实平台客服能力或合规建议。

详细说明见：

- [`docs/跨境电商智能客服系统改造方案.md`](docs/跨境电商智能客服系统改造方案.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/safety.md`](docs/safety.md)
- [`docs/synthetic-data.md`](docs/synthetic-data.md)
- [`docs/evaluation.md`](docs/evaluation.md)
