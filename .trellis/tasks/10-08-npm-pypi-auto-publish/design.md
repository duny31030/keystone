# Design — npm 与 PyPI 自动发布流水线

## 边界与不变量

- 只改「发布基础设施」:`/.github/workflows/release.yml`、`scripts/release.sh` 尾部提示、`README.md` 安装段、`CHANGELOG.md`、三个版本号文件。**不触碰** `src/keystone/**` 运行时逻辑与 CLI 行为。
- 仓库保持 private,因此不使用 PyPI trusted publishing(OIDC),一律 API token。这是硬约束,不是偏好。
- 外部写入(npm publish / PyPI upload)只在 tag 推送时发生,普通 push 到 main 绝不发布。

## 触发与 job 图

```
push tag v* ──► build ──┬──► publish-pypi
                        └──► publish-npm
```

- **单一 workflow** `release.yml`。触发条件保持 `on.push.tags: ['v*']`。
- `build` 承担全部门禁与产物构建;两个 publish job 只 `needs: build` 后下载产物并发布,互相独立可并行。
- **不在 publish job 里重新构建**。发布物必须是被测试过的同一份 artifact,否则「测了什么就发什么」这条不变量失效。

### 为什么不加 workflow_dispatch(R11 的选择)

首次发布要在 secrets 配置好之后才能成功。若首次失败,tag 对应的 workflow run 会红;GitHub 提供 "Re-run failed jobs",在 secrets 补上后重跑即可,不需要第二个触发入口。idempotency 探针保证重跑安全。多加一个入口只增加需要维护的面,与 R11 一致。

## 门禁设计

`build` job 内按顺序:

1. **tag↔版本一致性(R5)**:`GITHUB_REF_NAME` 去掉 `v` 前缀,与 `pyproject.toml` 的 `project.version` 比对,不等则 `::error::` + `exit 1`。用标准库 `tomllib`(CI 跑 3.11),不引第三方解析器。放在最前,让错 tag 立刻失败。
2. **测试(R4)**:`pip install -e '.[dev]'` + `pytest`。
3. **同步(R6)**:跑 `scripts/sync_npm.py`(它会把 `pyproject.toml` 版本写进 `npm/package.json`,并把 `src/keystone` 复制到 `npm/python/keystone`)。
4. **同步后零漂移校验**:再比对一次 pyproject 与 package.json 版本。挡住「sync 脚本自身坏掉」这一类失败,而不是假设它一定对。

## 产物布局

现有写法的 `release-artifacts` 把 `dist/` 和 `npm/*.tgz` 塞进同一个 artifact,多 path + 通配符下的目录结构不确定。改为两个命名明确的 artifact:

| artifact | 内容 | 消费者 |
|---|---|---|
| `python-dist` | `dist/*.whl`, `dist/*.tar.gz` | `publish-pypi` → `dist/` |
| `npm-tarball` | `npm/*.tgz` | `publish-npm` → `npm-dist/` |

`actions/download-artifact@v4` 用单个 `name:` 时直接解到 `path:`,不产生额外子目录,无需 `merge-multiple`。

## 幂等(R7)

两个 registry 机制不同,分别处理:

- **PyPI**:用 action 自带的 `skip-existing: true`。原生支持,版本已存在时逐文件跳过并以成功结束,无需自己写探针。
- **npm**:无等价开关,必须自探。已实测:`npm view keystone-hook@<v> version` 在版本存在时 **exit 0**(stdout 打印版本号),不存在时 **exit 1**(stderr `E404 No match found for version`)。用它作为判据:exit 0 → 打印 skip 并 `exit 0`;非 0 → `npm publish <tgz>`。这个探针**失败方向是安全的**:网络异常导致误判只会退化成一次 publish 尝试,而 npm 对重复版本是硬失败,不会写坏数据。

## 凭据

| secret | 用途 | 归属 |
|---|---|---|
| `NPM_TOKEN` | npm publish(`NODE_AUTH_TOKEN`) | 仓库所有者配置 |
| `PYPI_TOKEN` | PyPI upload(`password`) | 仓库所有者配置 |

- `pypa/gh-action-pypi-publish@release/v1` 的输入是 `password:`,**没有 `token:` 输入**;`user` 默认 `__token__`,`repository-url` 默认正式 PyPI,`packages-dir` 默认 `dist`。
- **不写 `permissions:` 块**。token 流程不需要 `id-token: write`(那是 OIDC 专用);沿用现有无 `permissions` 的写法,避免窄化 token 后影响 `download-artifact` 的取用路径。OIDC 迁移不在本任务范围。
- PyPI 侧首次发布的已知坑:`keystone-hook` 在 pypi.org 尚未注册,**现在无法创建 project-scoped token**,首次必须用 account-scoped(Entire account)token;发布成功后建议换成 project-scoped。

## 版本策略

HEAD 已积累大量 `[Unreleased]` 功能(platform adapter、Codex 支持等),但 `pyproject.toml` 停在 `0.2.1`。首次发布定为 **0.3.0**,并把 `[Unreleased]` 内容裁剪为 `[0.3.0] - 2026-10-08`,否则会出现「包里是新代码、CHANGELOG 却把 0.2.1 描述成只有 skills」的错位。

`release.sh` 与 CI 的职责重新划分:

- `release.sh`:改版本号 → 校验三处一致 → 测试 → sync → 构建 → 打 tag → 推 tag。**推 tag 即完成**,不再打印手敲的 `npm publish` / `uv publish`。
- CI:`tag` 到达后自动发布。

## 兼容与回滚

- **无用户空间破坏**:CLI 行为、hook 协议、`.keystone/` 布局全部不动;唯一用户可见变化是 README 安装命令从 TestPyPI 改为正式 PyPI(这是修正,不是破坏)。
- 发布不可逆,回滚手段有限:PyPI 可 yank(版本仍在,不再被默认解析);npm 可在发布后 72 小时内 unpublish,超期不可。因此 tag 一旦推送即视为已发布,重跑靠幂等而非回退。

## 未决/后续

- 首次真实发布需要 secrets 就位后的 tag 推送,该步骤由用户把守;本地只能验证到「构建产物、探针语义、YAML 结构、版本一致性」这一层。
- 可选硬化(本次不做):GitHub Environment + required reviewers 给发布加人工闸门。