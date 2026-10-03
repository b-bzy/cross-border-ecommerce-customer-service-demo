# 评测方法

## 默认离线评测

运行：

```bash
python -m commerce_support_demo.evals
```

评测使用 `evals/cases_test.jsonl` 中的冻结合成案例，并通过 FastAPI 与 `offline + in_process` 链路执行。输出写入忽略目录 `output/offline-evaluation.json`。

## 当前指标

- Intent Accuracy：最终路由意图是否与冻结标签一致；
- Recall@3：一级候选集是否包含目标意图（由单元测试与扩展评测覆盖）；
- Tool Selection Accuracy：意图是否映射到固定的正确工具；
- Multi-turn Success：预览、确认和幂等重放是否正确；
- Wrong-action Rate：聊天接口是否错误执行写工具；
- Handoff Accuracy：人工请求与不确定输入是否安全升级。

## 结果口径

所有结果仅描述**合成 Demo**。它们不是 Shopee、任何企业、真实买家或生产环境的结果。README 和作品集在没有冻结数据、可复现命令和原始输出之前，不应写入 98%、87%、QPS 等数字。

## Live Claude 评测

Live 模式涉及外部 API 调用与费用，应另行确认：

1. 使用独立、少量的合成歧义案例；
2. 记录模型 ID、时间、输入 case ID、结构化决策和 token 使用；
3. 不把 API Key、完整消息或敏感日志写入评测文件；
4. 不在默认 CI、批处理或未明确同意的情况下运行。
