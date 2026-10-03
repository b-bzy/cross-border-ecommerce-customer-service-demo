# 安全与限制说明

## 模型边界

Claude 只用于二级候选意图精排。它：

- 只能从一级 Top-3 候选中选择；
- 输出必须通过 Pydantic structured-output schema 校验；
- 不获得 MCP 工具定义；
- 不获得订单详情、完整会话、写入 capability 或 API Key；
- 不决定订单归属、政策资格或写操作。

模型输出无效、超时、拒绝或选择候选集外意图时，服务会进入离线后备、澄清或人工接管，不会放宽策略执行写操作。

## 写操作边界

改地址和催发货遵循：

1. 聊天接口只读取当前订单并创建待确认预览；
2. 自然语言“确认 / yes”不会执行写入；
3. 独立确认接口验证客户、会话、TTL 和 action digest；
4. 服务确认订单版本和当前政策未改变；
5. 服务签发绑定 action、工具、参数、客户、版本和过期时间的 HMAC capability；
6. MCP / in-process 业务服务再次校验 capability、资源版本和订单归属；
7. 已执行的 action 以 idempotency key 返回原结果，不重复修改。

## 数据和日志

- 数据目录只保存标记为 `is_synthetic: true` 的虚构 fixture；
- `.env`、凭证、日志、运行产物和旧参考源码均不应进入 Git；
- 本项目不实现真实身份认证，`customer_id` 仅用于演示跨客户拒绝；
- 内存状态在重启后清空，不适合作为生产架构；
- Demo 不提供支付、真实退款、税务、账户安全或真实人工客服集成。

## 发布前检查

公开提交前只显式暂存新 Demo 路径，随后检查：

```bash
git status --short
git diff --cached --check
git check-ignore -v --no-index mcp_core/amp_server.py
```

不要使用 `git add .` 或 `git add -A`，以避免误提交被隔离的旧车载参考文件。
