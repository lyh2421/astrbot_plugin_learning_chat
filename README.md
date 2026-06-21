# 群聊学习 (astrbot_plugin_learning_chat)

AstrBot 插件 - 让 Bot 学习群友的发言、复读以及主动发言。

基于 [nonebot-plugin-learning-chat](https://github.com/CMHopeSunshine/nonebot-plugin-learning-chat) 移植。

## ✨ 功能

- 📚 **学习群友发言**：使用 jieba 分词提取关键词，建立上下文关联，越聊越像群友
- 🔁 **智能复读**：检测多人队形复读，达到阈值自动跟上
- ✋ **随机打断复读**：有概率在复读达到阈值时打断
- 💬 **主动发言**：群聊沉默时，从已学会的回复中挑选合适的主动发言
- 🚫 **屏蔽管理**：支持屏蔽特定用户或特定词汇
- ⚙️ **分群配置**：每个群独立开关和参数调节

## 📦 安装

### 从 AstrBot 插件市场安装

在 AstrBot WebUI → 插件市场 搜索 `群聊学习` 一键安装。

### 手动安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/yourname/astrbot_plugin_learning_chat.git
```

## 🎮 使用方法

插件安装后默认开启，Bot 会自动学习群聊中的发言。

### 指令列表

| 指令 | 说明 |
|------|------|
| `/学说话` | 开启本群学习功能 |
| `/闭嘴` | 关闭本群学习功能 |
| `/学习状态` | 查看当前学习统计 |

## ⚙️ 配置说明

### 全局配置

配置文件位于插件目录 `data/config.json`

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `total_enable` | `true` | 总开关 |
| `KEYWORDS_SIZE` | `3` | 关键词提取数量 |
| `learn_max_count` | `6` | 单句最高学习次数 |
| `cross_group_threshold` | `3` | 跨群回复阈值 |
| `ban_words` | `[]` | 全局屏蔽词 |
| `ban_users` | `[]` | 全局屏蔽用户 |
| `dictionary` | `[]` | 自定义词典 |

### 分群配置

每个群的配置会自动生成，可通过 WebUI 或直接编辑 `config.json` 中的 `group_configs`。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `enable` | `true` | 本群开关 |
| `answer_threshold` | `4` | 回复阈值（学会多少次后才开始回复） |
| `repeat_threshold` | `3` | 复读阈值（连续N条相同消息触发复读） |
| `break_probability` | `0.25` | 打断复读概率 |
| `speak_enable` | `true` | 主动发言开关 |
| `speak_threshold` | `5` | 主动发言阈值（沉默倍率） |
| `speak_min_interval` | `300` | 主动发言最小区间（秒） |
| `speak_continuously_probability` | `0.5` | 连续发言概率 |
| `speak_continuously_max_len` | `3` | 最大连续发言句数 |

## 📂 插件结构

```
astrbot_plugin_learning_chat/
├── main.py              # 插件入口（Star 类）
├── handler.py           # 核心学习逻辑
├── models.py            # 数据模型
├── config.py            # 配置类
├── metadata.yaml        # 插件元数据
├── requirements.txt     # 依赖
├── .astrbot-plugin      # 标记文件
├── README.md            # 说明文档
└── data/                # 运行时数据（自动生成）
    ├── config.json      # 配置文件
    └── storage.json     # 学习数据
```

## 📄 许可证

AGPL v3.0

## 🔗 致谢

- [nonebot-plugin-learning-chat](https://github.com/CMHopeSunshine/nonebot-plugin-learning-chat) - 原始插件
- [AstrBot](https://github.com/AstrBotDevs/AstrBot) - Bot 框架