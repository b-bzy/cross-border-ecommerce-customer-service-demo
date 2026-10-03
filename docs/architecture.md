# 架构说明

## 信任边界

```text
未受信任买家消息
  → Top-3 轻量召回
  → Claude（仅候选精排，可选）
  → 确定性路由与策略层
  → 固定工具 allowlist
  → 合成业务服务 / MCP
```

Claude 不获得 MCP 工具，也不获得直接写入权限。模型输出必须符合 `RerankDecision` schema，且 `selected_intent` 必须属于一级候选集；否则进入离线后备、澄清或人工接管。

## 写操作状态机

```text
chat request → pending action → explicit confirm endpoint → executing → executed
                    │                    │
                    └─ cancelled/expired └─ failed
```

聊天接口永远不执行写操作。确认时校验：客户与会话归属、digest、固定工具和参数、TTL、当前订单版本与业务状态。写入 capability 使用 HMAC 绑定这些字段，MCP 工具会再次验证。

## 运行模式

| 模式 | 路由 | 业务传输 | 使用场景 |
|---|---|---|---|
| `offline` | 确定性精排 | in-process 或 MCP | 默认本地运行、CI、评测 |
| `hybrid` | 高置信度直路由；歧义时 Claude | in-process 或 MCP | 有凭证的交互演示 |
| `live_always` | Claude 精排 | in-process 或 MCP | 受控人工验证，不用于默认 CI |

## 组件

- `routing/retriever.py`：多语言轻量 Top-3 候选召回；
- `routing/rerankers.py`：Claude 与离线 Reranker；
- `service/orchestrator.py`：会话、策略、工具编排与响应；
- `service/actions.py`：确认、过期、幂等与 capability；
- `service/commerce.py`：传输无关的合成业务规则；
- `mcp/server.py`：同一业务规则的 stdio MCP 暴露；
- `mcp/gateway.py`：in-process / MCP 适配器。

进程内状态仅适合 Demo；真实生产环境需替换为持久化会话、经过认证的身份体系、审计存储、幂等事务和经审核的业务服务。
