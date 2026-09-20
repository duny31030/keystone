# Keystone 发布工程化

## Goal

实现最小可行的发布工程化：release.sh 发布脚本、CHANGELOG.md、GitHub Actions workflow 骨架（tag 触发，测试通过后可手动或自动发布）。

## Requirements

- `scripts/release.sh <version>`：一条命令完成版本校验、测试、同步、构建、打 tag、推送
- 版本号一致性校验：pyproject.toml、src/keystone/__init__.py、npm/package.json 必须一致
- 发布前自动跑 pytest，失败则拒绝发布
- 自动同步 npm 内嵌源码和 README
- 自动构建 Python wheel/sdist 和 npm tarball
- 自动打 Git tag 并推送（`v<version>`）
- 发布 registry 部分先注释掉，等用户决定后再启用
- `CHANGELOG.md`：从 0.2.0 开始补，记录用户可见变化
- GitHub Actions workflow：tag 触发，自动跑测试、构建产物；发布步骤先注释
- 不引入 OIDC/Trusted Publishing（后续优化）

## Acceptance Criteria

- [ ] `scripts/release.sh` 可执行，版本不一致时拒绝
- [ ] `scripts/release.sh` 测试失败时拒绝
- [ ] `scripts/release.sh` 自动同步 npm、构建产物、打 tag、推送
- [ ] `CHANGELOG.md` 包含 0.2.0 的完整变更记录
- [ ] `.github/workflows/release.yml` 存在，tag 触发时跑测试和构建
- [ ] workflow 的发布步骤已注释，不会误发
- [ ] 测试全绿，脚本在干净工作区可执行
- [ ] 版本 0.2.1，不发布
