"""规范文件：init 时生成模板，内容由人工维护（规范即文件，随 git 共享评审）。"""

from __future__ import annotations

from keystone.store.layout import KeystoneLayout

# 顺序即注入顺序
SPEC_CATEGORIES = ("architecture", "coding", "general-ban")

_TEMPLATES = {
    "architecture": """\
# 架构规范

（keystone init 生成的模板，请按项目实际填写；本文件随 git 共享给全团队）

- 模块/分层划分：
- 依赖方向约束：
- 关键设计约定：
""",
    "coding": """\
# 编码规范

- 命名约定：
- 异常与日志：
- 测试要求：
- 其他团队约定：
""",
    "general-ban": """\
# 通用禁止事项

- 禁止直接修改 `.keystone/` 内的任务状态文件，任务状态一律用 `keystone task` 命令推进
- 禁止提交密钥、token 等敏感信息
- 禁止绕过验证直接宣称任务完成
""",
}


def write_templates(layout: KeystoneLayout) -> list:
    """生成规范模板文件，返回创建的路径列表（已存在的不覆盖）。"""
    created = []
    layout.specs_dir.mkdir(parents=True, exist_ok=True)
    for category in SPEC_CATEGORIES:
        target = layout.specs_dir / f"{category}.md"
        if not target.exists():
            target.write_text(_TEMPLATES[category], encoding="utf-8")
            created.append(target)
    return created


def load_specs(layout: KeystoneLayout) -> list[tuple[str, str]]:
    """按固定类别顺序读取规范内容，跳过缺失或空文件。"""
    result = []
    for category in SPEC_CATEGORIES:
        path = layout.specs_dir / f"{category}.md"
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            if content.strip():
                result.append((category, content))
    return result
