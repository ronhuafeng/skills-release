---
name: prune-legacy
description: 仅限用户显式调用 $prune-legacy。基于当前代码、实际调用关系和可重复运行证据，审查或删除旧类型、旧 schema、adapter、deprecated API、兼容路径、fallback、双执行路径、死代码以及失效测试和文档。
user-invocable: true
disable-model-invocation: true
---

# Prune Legacy Paths

仅在用户显式调用 `$prune-legacy` 时执行本 skill。

根据用户请求选择一个动作，读取对应文档，然后严格按该文档执行：

- 检查、审计、识别或报告 legacy 候选，但不修改代码：读取
  `commands/review.md`。
- 修复或删除用户已确认且可精确识别的 findings：读取
  `commands/apply.md`。

示例请求：

- `使用 $prune-legacy review 审查 <范围> 中的 legacy 实现。`
- `使用 $prune-legacy apply 修复已确认的 LP-01 和 LP-02。`

只有名称、注释、年代或历史印象不能证明实现已经失效。必须以当前实现、
实际调用关系、现行契约或可重复运行结果为依据。

如果用户要求修改，但没有提供或确认 findings，先执行只读 review，不直接删除。
如果用户已经明确要求应用已确认 findings，不重新进行全仓审查，也不扩大范围。

除非用户另行明确授权，不 commit、push、创建 PR、部署或执行生产环境 mutation。
