# 发布检查清单

社区版 **0.5.1-community.2** 基于 origin652/cpa-plugin-key-policy v0.5.1，保留 MIT LICENSE 与上游署名。

1. 仅从已审查的源码目录建立独立 Git 仓库，使用 GitHub noreply 邮箱。不要上传父级维护目录或私人 Git 历史。
2. 源码允许包含虚构数据的示例与截图；禁止凭据、真实账本、缓存、日志、生产地址和私人安装脚本。测试生成的空账本也必须排除。
3. 执行 `python3 scripts/check-public-source.py`、`python3 -m unittest discover -s scripts -p 'test_*.py' -v` 和 Gitleaks；核对 FILES.sha256。新增文件及提交作者信息也要检查。
4. 按 VALIDATION.md 运行对应测试。GitHub 工作流只验证；手动触发时生成二进制，不自动发布或部署。
5. 若改变构建输入，重新编译插件并检查二进制；更新校验值后再上传 Release 附件。安装文件名必须是 `cpa-key-policy-v0.5.1-community.2.so`。
6. 插件元数据保留上游项目链接作为来源，README 中明确社区分支身份。它不是上游插件商店的官方更新。

本发布包的检查结果不表示生产实例已部署这些变更。详见 PRIVACY.md、SECURITY.md 和 VALIDATION.md。
