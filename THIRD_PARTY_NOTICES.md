# 复用来源

## dashi-taskboard

- 仓库：https://github.com/chuspeeism/dashi-taskboard
- 检查及引用版本：`da4704da494af2364a7556373f2490aeb3092554`
- 许可证：Apache-2.0，全文位于 `vendor/dashi-taskboard/LICENSE`。
- `vendor/dashi-taskboard/taskboard-supervisor.mjs` 直接复制上游同名模块，未修改。
- `tests/supervisor.test.mjs` 来自上游测试，仅调整导入路径。
- `web/native.js` 的主内容区定位参考上游 `inject/codex-taskboard.user.js` 的 `findPageHost`；本项目改用 Shadow DOM 与 CDP 消息桥，并实现项目旁的入口。

资料索引、搜索、展示及本机启动管理在本仓库实现。

## markdown-it

Markdown 文档预览采用 npm `markdown-it` 14.3.0（MIT），版本及传递依赖固定在 `package-lock.json`。禁用原始 HTML 和外部图片、链接渲染；许可证随依赖包安装。
