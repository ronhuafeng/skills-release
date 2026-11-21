# Stitch 工具限制

这些限制来自 2026-11-20 的一次页面画面制作。工具签名变化时，以当前工具为准。

## 上传与主题

- `upload_design_md` 只接收 `projectId` 和 `designMdBase64`。它不接收本地文件路径。
- 工具参数里的 `$(...)` 不会展开。Base64 必须是已经算好的字符串。
- 创建设计系统后，主题主色可能与 token 文件不同。画面合同仍使用来源色值，不改 token 文件。
- 生成器可能留下 `text-primary`、`bg-primary`、`text-info`、`border-info`、`bg-accent`。精确画面改用本地 HTML 中的字面色值。

## 画面

- `generate_screen_from_text` 只负责建立一张桌面画面。精确修改用 `update_screen`：`updateMask` 为 `html_code`，HTML 放在 `htmlCodeBase64`。
- `edit_screens` 可以返回成功，但 HTML 文件 ID 不变。文件 ID 不变就是没有改到画面。
- `list_screens` 可能漏掉新画面。screen ID 以生成结果和 `get_project` 为准。
- 一次读取很长的 Base64 可能被截断。按约 1200 字符分段读取，再原样拼接。

## 读取与验收

- 下载地址直接请求会返回 401。用 `download_file`。
- `download_file` 可能截断大约 20KB 以上的 HTML。截断结果不能做哈希。
- `update_screen` 返回的 contribution 地址可以取回全文。用这篇全文做 sha256。
- `get_screen` 返回的宽高是截图尺寸，不是画布实例尺寸。
- 缩略图分辨率不足以判断颜色、字号和圆角。

## 画布

- 修改画布前先 `get_project`。
- `update_project` 的 `updateMask` 使用 `screen_instances` 时，提交的是完整实例表。漏掉旧实例会从画布移除它们。
- 失败的重复画面改为隐藏。不要为了清理而整表替换成部分列表。
- 并行 Stitch 调用可能返回 `runtime_capacity_exceeded`。写操作一次只发一个。
