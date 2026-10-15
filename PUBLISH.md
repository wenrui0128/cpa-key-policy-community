# 发布维护

此文档供维护者发布版本时使用。安装和使用说明见 [README.zh-CN.md](README.zh-CN.md)。

## 发布前检查

1. 更新版本号、更新日志和安装说明，确认文档中的动态库文件名与版本一致。
2. 按 [VALIDATION.md](VALIDATION.md) 运行与改动相关的测试。修改前端后运行 `make web-build`，更新嵌入插件的 HTML。
3. 检查待提交文件，排除运行数据、凭据、日志和备份；示例和截图使用演示数据。
4. 运行源码检查与凭据扫描：

```bash
python3 scripts/check-public-source.py
python3 -m unittest discover -s scripts -p 'test_*.py' -v
gitleaks detect --source . --config .gitleaks.toml --no-banner
```

5. 更新 `FILES.sha256`，使其覆盖所有源码文件（不含清单本身），并核对清单。
6. 保留 [LICENSE](LICENSE) 和上游署名。

## 构建和发布

在对应架构的 Linux 环境中构建动态库。当前已验证 Linux amd64 / glibc；其他环境需要补充验证。

安装文件名为 `cpa-key-policy-v<版本>.so`。CPA 根据文件名识别插件，打包时应将构建产物的架构后缀改为版本后缀。

- 源码包包含源码、文档、示例配置和文件校验清单。
- 二进制包包含动态库、安装说明和许可证。
- 为下载文件生成 `SHA256SUMS`，上传至对应版本的 GitHub Release。
- 发布说明列出功能变化、安装或升级步骤、兼容版本及已知限制。
- 发布后核对下载文件的校验值和文档链接。

GitHub 工作流会在推送和 Pull Request 时执行验证；手动触发时构建二进制，不自动创建 Release。已发布的标签和附件保持不变；后续修复使用新版本号。
