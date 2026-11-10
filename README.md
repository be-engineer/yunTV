# 云TV (yunTV)

基于 TVBox 的开源影视盒子，适配电视盒子与手机横屏。

本仓库为 **yunTV 的发布仓库**：存放正式版 APK 资产与更新清单（`version.json`），源码仓库见 [be-engineer/Box](https://github.com/be-engineer/Box)。

## ✨ 核心特性

### 🔍 自动搜索数据源
内置数据源自动发现：种子页抽取候选配置地址，自动校验结构（点播 `sites` / 直播 `#EXTM3U`），搜索结果带复选框、勾选后一键批量添加，不用再到处找配置地址。结果随机化，每次搜索持续发现新源（每日 3 次）。

### ✅ 一键验证源
批量测试数据源连通性：逐条显示 HTTP 状态、耗时、站点数/频道数，坏源一目了然，添加前先验货。

### 其他
- 数据源管理：添加 / 扫码添加 / 编辑 / 历史记录
- 直播源 + EPG 支持
- WebDAV 备份同步
- XWalk 内核网页嗅探

## 📦 下载

到 [Releases](https://github.com/be-engineer/yunTV/releases) 页面下载最新版：

| 文件 | 适用 |
|------|------|
| `yunTV-release-<日期>.apk` | arm64-v8a（主流手机/盒子） |
| `yunTV-release-<日期>-armeabi.apk` | armeabi-v7a（老盒子） |

## ⚠️ 免责声明

本项目不提供任何影视内容，所有内容均来自用户自行配置的第三方数据源。请遵守当地法律法规，仅用于技术学习交流。
