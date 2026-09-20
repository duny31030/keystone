# Keystone 本地诊断与生命周期命令

## Goal

实现 `keystone doctor`、`keystone status`、`keystone uninstall` 与 `keystone init --dry-run`，使用户能确认本地配置状态、定位问题、预览初始化和无损注销 Keystone，而不引入服务端或自动执行工程动作。

## Requirements

- `keystone init --dry-run` 与实际 init 共用变更计算，绝不写入项目文件、目录或运行时状态；
- `keystone status [--dir DIR]` 提供项目、任务、注册 hook、会话绑定和 SessionEnd 记录的只读摘要；
- `keystone doctor [--dir DIR]` 输出 PASS/WARN/FAIL，仅检查本地文件和 settings 注册，不声称 CodeBuddy 已实际加载或触发 hook；
- `keystone uninstall` 仅移除 `.codebuddy/settings.json` 中 Keystone command，保留 `.keystone/`、第三方 hooks 和 `.gitignore`；
- `keystone uninstall --purge --yes` 才删除 `.keystone/`，并只移除精确 Keystone managed gitignore block；
- 混合 hook rule 内的第三方 command/matcher 必须保留；
- `--dry-run` 不写入，`--purge` 在非 TTY 下必须显式 `--yes`；
- 版本升级到 0.2.0，本轮不发布 npm/TestPyPI。

## Acceptance Criteria

- [x] init dry-run 空项目/旧配置/非法 settings 均按预期预览且零写入
- [x] status 正确汇总正常项目，错误项目返回非零
- [x] doctor 能发现缺失、损坏、退役/缺失 hook 和 enforce 未实机验证提示，且不改文件
- [x] uninstall 默认无损、混合 rule 安全、幂等；purge 只在明确确认后删除项目资料
- [x] pytest、Python 构建、npm tarball fresh install 冒烟通过
- [x] 0.2.0 代码和 npm 同步内容提交并推送 GitHub
