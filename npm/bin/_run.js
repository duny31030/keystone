#!/usr/bin/env node
'use strict';
// Keystone npm 垫片：定位 python3 后以内嵌源码执行对应模块，
// stdin/stdout/stderr 与退出码全部透传（hook 协议依赖）。

const { spawnSync } = require('child_process');
const path = require('path');

const PYTHON_SRC = path.join(__dirname, '..', 'python');

function findPython() {
  const candidates = [process.env.KEYSTONE_PYTHON, 'python3', 'python'].filter(Boolean);
  for (const candidate of candidates) {
    const probe = spawnSync(candidate, ['-c', 'print(1)'], { encoding: 'utf8' });
    if (!probe.error && probe.status === 0) {
      return candidate;
    }
  }
  return null;
}

/**
 * 运行内嵌 Python 模块。
 * @param {string} moduleName  python -m 的模块名
 * @param {number} fallbackExit  进程被信号杀死时的退出码兜底
 */
function run(moduleName, fallbackExit) {
  const python = findPython();
  if (!python) {
    console.error(
      'keystone: 未找到可用的 python3（hook 与 CLI 均需要）。\n' +
        '可用环境变量 KEYSTONE_PYTHON 指定解释器路径，或安装 Python >= 3.9。'
    );
    return 1;
  }
  const result = spawnSync(python, ['-m', moduleName, ...process.argv.slice(2)], {
    stdio: 'inherit',
    env: { ...process.env, PYTHONPATH: PYTHON_SRC },
  });
  if (result.error) {
    console.error(`keystone: 启动 ${python} 失败：${result.error.message}`);
    return fallbackExit;
  }
  return result.status === null ? fallbackExit : result.status;
}

module.exports = { run };
