# 合成数据说明

本项目的 `data/synthetic/` 是可公开提交的虚构 fixture，不包含 Shopee 或任何企业生产数据。

## 保证

- 每个实体带有 `is_synthetic: true`；
- `manifest.json` 声明 fixture 版本、支持语言和合成属性；
- 订单、客户、地址、商品、物流单、退款、政策和工单 ID 均使用明显的 `*-DEMO-*` 前缀；
- 所有姓名、地址、时间、物流事件和政策文本均为演示构造，不能用于真实业务判断；
- 服务重启会恢复 fixture 原状，所有写入仅存在于进程内内存。

## 数据集

| 文件 | 内容 |
|---|---|
| `customers.json` | 两个虚构 Demo 客户 |
| `orders.json` | 处理、运输、签收以及跨客户拒绝场景 |
| `shipments.json` | 正常等待发货和清关延误轨迹 |
| `refunds.json` | 退款处理中场景 |
| `policies.json` | 演示用退货和关税规则 |
| `intent_catalog.json` | 多语言意图、槽位和操作映射 |

新增 fixture 必须保留 schema version、`is_synthetic`、显式 source ID，且不能加入真实姓名、联系方式、地址、订单号、会话、凭证或内部规则。
