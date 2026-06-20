"""
群聊学习插件 - AstrBot 版本
基于 nonebot-plugin-learning-chat 移植
让 Bot 学习群友的发言、复读以及主动发言
"""

import asyncio
import json
import os
import random
import re
import time
from pathlib import Path
from typing import Optional

import jieba.analyse as jieba_analyse

from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api.message_components import Plain, At
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

from .handler import LearningChat, ChatAnswer, ChatContext, ChatMessage, ChatBlackList
from .config import ChatConfig, ChatGroupConfig

PLUGIN_DIR = Path(__file__).parent
DATA_DIR = PLUGIN_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

STORAGE_PATH = DATA_DIR / "storage.json"


class LearningChatPlugin(Star):
    """群聊学习插件主类"""

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)

        # 从 AstrBot WebUI 配置加载
        self.config = ChatConfig()
        if config:
            self._from_astrbot_config(config)
        else:
            # fallback: 从文件加载
            self.config_path = DATA_DIR / "config.json"
            self._load_config()

        # 加载持久化数据
        self.storage = {
            "contexts": {},       # keyword -> ChatContext
            "answers": [],        # list of ChatAnswer
            "messages": [],       # list of ChatMessage (recent)
            "blacklist": {},      # keyword -> ChatBlackList
        }
        self._load_storage()

        # 消息缓冲区（用于复读检测等）
        self.message_buffer: list[ChatMessage] = []

        # 上次主动发言时间 {group_id: timestamp}
        self.last_speak_time: dict[str, float] = {}

        # 启动定时任务 - 主动发言
        self._speak_task = asyncio.create_task(self._speak_loop())

    def _from_astrbot_config(self, cfg: AstrBotConfig):
        """从 AstrBot WebUI 配置同步到内部 ChatConfig"""
        self.config.total_enable = cfg.get("total_enable", True)
        self.config.KEYWORDS_SIZE = cfg.get("KEYWORDS_SIZE", 3)
        self.config.learn_max_count = cfg.get("learn_max_count", 6)
        self.config.cross_group_threshold = cfg.get("cross_group_threshold", 3)
        self.config.ban_words = self._parse_json_field(cfg.get("ban_words", "[]"))
        self.config.ban_users = self._parse_json_field(cfg.get("ban_users", "[]"))
        self.config.dictionary = self._parse_json_field(cfg.get("dictionary", "[]"))

        # 全局默认值用于新建群
        default_group = ChatGroupConfig()
        default_group.answer_threshold = cfg.get("answer_threshold", 4)
        default_group.repeat_threshold = cfg.get("repeat_threshold", 3)
        default_group.break_probability = cfg.get("break_probability", 0.25)
        default_group.speak_enable = cfg.get("speak_enable", True)
        default_group.speak_threshold = cfg.get("speak_threshold", 5)
        default_group.speak_min_interval = cfg.get("speak_min_interval", 300)
        default_group.speak_continuously_probability = cfg.get("speak_continuously_probability", 0.5)
        default_group.speak_continuously_max_len = cfg.get("speak_continuously_max_len", 3)
        default_group.speak_poke_probability = cfg.get("speak_poke_probability", 0.5)
        self.config.default_group_config = default_group

        # 分群配置
        group_configs_raw = self._parse_json_field(cfg.get("group_configs", "{}"))
        for gid, gc_data in group_configs_raw.items():
            self.config.group_configs[str(gid)] = ChatGroupConfig.from_dict(gc_data)

    def _parse_json_field(self, value):
        """解析 WebUI 中的 JSON 文本字段"""
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return json.loads(value)
            except Exception:
                logger.warning(f"[群聊学习] JSON 解析失败: {value[:50]}...")
                return [] if value.startswith("[") else {}
        return [] if isinstance(value, str) and value.startswith("[") else {}

    def _load_config(self):
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text("utf-8"))
                self.config = ChatConfig.from_dict(data)
            except Exception:
                logger.warning("[群聊学习] 配置文件加载失败，使用默认配置")
                self._save_config()
        else:
            self._save_config()

    def _save_config(self):
        self.config_path.write_text(
            json.dumps(self.config.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_storage(self):
        if STORAGE_PATH.exists():
            try:
                data = json.loads(STORAGE_PATH.read_text("utf-8"))
                self.storage["contexts"] = {
                    k: ChatContext.from_dict(v) for k, v in data.get("contexts", {}).items()
                }
                self.storage["answers"] = [
                    ChatAnswer.from_dict(a) for a in data.get("answers", [])
                ]
                self.storage["messages"] = [
                    ChatMessage.from_dict(m) for m in data.get("messages", [])
                ]
                self.storage["blacklist"] = {
                    k: ChatBlackList.from_dict(b) for k, b in data.get("blacklist", {}).items()
                }
            except Exception as e:
                logger.warning(f"[群聊学习] 存储数据加载失败: {e}")

    def _save_storage(self):
        self._cleanup_storage()
        data = {
            "contexts": {k: v.to_dict() for k, v in self.storage["contexts"].items()},
            "answers": [a.to_dict() for a in self.storage["answers"]],
            "messages": [m.to_dict() for m in self.storage["messages"][-1000:]],  # 限制1000条
            "blacklist": {k: b.to_dict() for k, b in self.storage["blacklist"].items()},
        }
        STORAGE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _cleanup_storage(self):
        """自动清理陈旧数据，防止 storage.json 无限膨胀"""
        cur_time = int(time.time())

        # 1. 只保留近 7 天的消息（每次保存时裁剪到1000条，这里再按时间过滤）
        cutoff_7d = cur_time - 7 * 86400
        self.storage["messages"] = [
            m for m in self.storage["messages"] if m.time >= cutoff_7d
        ]

        # 2. 清理超过 30 天未更新的 context
        cutoff_30d = cur_time - 30 * 86400
        stale_contexts = [
            k for k, v in self.storage["contexts"].items()
            if v.time < cutoff_30d and v.count <= 2  # 低使用率 + 长时间未更新
        ]
        for k in stale_contexts:
            del self.storage["contexts"][k]

        # 3. 限制 context 总数（最多保留 5000 个高频使用的）
        max_contexts = 5000
        if len(self.storage["contexts"]) > max_contexts:
            sorted_ctx = sorted(
                self.storage["contexts"].items(),
                key=lambda x: x[1].count,
                reverse=True,
            )
            self.storage["contexts"] = dict(sorted_ctx[:max_contexts])

        # 4. 清理无关联 context 的孤立 answer
        valid_context_keys = set(self.storage["contexts"].keys())
        self.storage["answers"] = [
            a for a in self.storage["answers"]
            if a.context_keyword in valid_context_keys
        ]

        # 5. 限制 answer 总数（最多保留 10000 条）
        max_answers = 10000
        if len(self.storage["answers"]) > max_answers:
            self.storage["answers"].sort(
                key=lambda a: a.count + a.time / 1e9,  # count 优先，time 次之
                reverse=True,
            )
            self.storage["answers"] = self.storage["answers"][:max_answers]

        # 6. 单个 answer 的 messages 去重 + 限制条数
        for answer in self.storage["answers"]:
            answer.messages = list(dict.fromkeys(answer.messages))  # 去重保留顺序
            if len(answer.messages) > 20:
                answer.messages = answer.messages[-20:]  # 最多保留20条

    def _get_group_config(self, group_id: str) -> ChatGroupConfig:
        if group_id not in self.config.group_configs:
            self.config.group_configs[group_id] = ChatGroupConfig()
            self._save_config()
        return self.config.group_configs[group_id]

    # ========== 消息处理 ==========

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """处理群消息，执行学习+回复逻辑"""
        group_id = event.get_group_id()
        if not group_id:
            return

        sender_id = event.get_sender_id()
        message_str = event.message_str
        raw_message = message_str

        # 获取群配置
        group_config = self._get_group_config(group_id)

        # 检查总开关和群开关
        if not self.config.total_enable or not group_config.enable:
            return

        # 构造 ChatMessage
        chat_msg = ChatMessage(
            group_id=group_id,
            user_id=sender_id,
            message=raw_message,
            raw_message=raw_message,
            plain_text=message_str,
            time=int(time.time()),
        )

        # 提取关键词
        chat_msg.extract_keywords(self.config.KEYWORDS_SIZE, self.config.dictionary)

        # 保存消息到 buffer
        self.storage["messages"].append(chat_msg)
        self.message_buffer.append(chat_msg)

        # 清理旧消息（保留2小时内）
        cutoff = int(time.time()) - 7200
        self.storage["messages"] = [m for m in self.storage["messages"] if m.time >= cutoff]
        self.message_buffer = [m for m in self.message_buffer if m.time >= cutoff]

        # 构建 LearningChat 实例
        lc = LearningChat(
            chat_msg=chat_msg,
            group_config=group_config,
            config=self.config,
            storage=self.storage,
            bot_id=event.get_self_id() or "bot",
        )

        # 检查是否有回复
        result = lc.learn()

        if result.action == "pass":
            return

        if result.action == "repeat":
            # 检查是否已经复读过
            recent_bot_msgs = [
                m for m in self.storage["messages"][-20:]
                if m.user_id == lc.bot_id and m.message == result.reply
            ]
            if recent_bot_msgs:
                logger.debug(f"[群聊学习] 已经复读过，跳过")
                return
            # 检查复读阈值
            recent_msgs = [m for m in self.message_buffer[-10:] if m.message == chat_msg.message]
            if len(recent_msgs) < group_config.repeat_threshold:
                return
            # 是否全部为同一人
            if all(m.user_id == chat_msg.user_id for m in recent_msgs):
                return
            if random.random() < group_config.break_probability:
                reply_text = random.choice(["打断复读！", "打断！"])
            else:
                reply_text = result.reply
            try:
                yield event.plain_result(reply_text)
                logger.info(f"[群聊学习] 向群<{group_id}>复读: {reply_text}")
                self._record_bot_message(group_id, lc.bot_id, reply_text)
            except Exception as e:
                logger.warning(f"[群聊学习] 发送复读失败: {e}")
            return

        if result.action == "reply" and result.reply:
            reply_text = result.reply
            try:
                yield event.plain_result(reply_text)
                logger.info(f"[群聊学习] 向群<{group_id}>回复: {reply_text}")
                self._record_bot_message(group_id, lc.bot_id, reply_text)
            except Exception as e:
                logger.warning(f"[群聊学习] 发送回复失败: {e}")

            # 保存学习数据
            self._save_storage()

    def _record_bot_message(self, group_id: str, bot_id: str, message: str):
        """记录 Bot 发送的消息"""
        bot_msg = ChatMessage(
            group_id=group_id,
            user_id=bot_id,
            message=message,
            raw_message=message,
            plain_text=message,
            time=int(time.time()),
        )
        self.storage["messages"].append(bot_msg)

    # ========== 主动发言定时任务 ==========

    async def _speak_loop(self):
        """主动发言循环（每 3 分钟检查一次）"""
        while True:
            try:
                await asyncio.sleep(180)  # 3分钟
                if not self.config.total_enable:
                    continue
                await self._do_speak()
            except Exception as e:
                logger.error(f"[群聊学习] 主动发言异常: {e}")

    async def _do_speak(self):
        """执行主动发言逻辑"""
        cur_time = int(time.time())
        today_start = int(time.mktime(time.localtime(cur_time - cur_time % 86400)))

        # 统计各群消息量
        group_messages: dict[str, list[ChatMessage]] = {}
        for msg in self.storage["messages"]:
            if msg.time < today_start:
                continue
            if msg.group_id not in group_messages:
                group_messages[msg.group_id] = []
            group_messages[msg.group_id].append(msg)

        if not group_messages:
            return

        # 按活跃度排序（消息越多越活跃）
        def popularity_key(item):
            msgs = item[1]
            if len(msgs) < 2:
                return 0
            return len(msgs) / max(msgs[0].time - msgs[-1].time, 1)

        sorted_groups = sorted(group_messages.items(), key=popularity_key, reverse=True)
        logger.debug(f"[群聊学习] 主动发言：群活跃度 {[(g[0], len(g[1])) for g in sorted_groups[:5]]}")

        for group_id, messages in sorted_groups:
            if len(messages) < 30:
                continue

            group_config = self._get_group_config(group_id)

            # 检查开关
            if not group_config.speak_enable or not group_config.enable:
                continue

            # 检查最后一条是否是自己发的
            bot_msgs = [
                m for m in messages if m.user_id == self._get_bot_id()
            ]
            if bot_msgs and bot_msgs[-1].time >= messages[0].time:
                logger.debug(f"[群聊学习] 主动发言：群<{group_id}>最后一条是Bot消息，跳过")
                continue

            # 检查上次发言间隔
            last_time = self.last_speak_time.get(group_id, 0)
            if cur_time - last_time < group_config.speak_min_interval:
                continue

            # 检查沉默时间
            avg_interval = (messages[0].time - messages[-1].time) / max(len(messages), 1)
            silent_time = cur_time - messages[0].time
            threshold = avg_interval * group_config.speak_threshold
            if silent_time < threshold:
                logger.debug(
                    f"[群聊学习] 主动发言：群<{group_id}>沉默时间({silent_time:.0f}s) < 阈值({threshold:.0f}s)"
                )
                continue

            # 寻找合适的发言
            speak_list = self._find_speak_messages(group_id, group_config)
            if not speak_list:
                logger.debug(f"[群聊学习] 主动发言：群<{group_id}>未找到合适的发言")
                continue

            # 发送消息
            for msg_text in speak_list:
                try:
                    # 使用统一的 API 发送群消息
                    await self._send_group_message(group_id, msg_text)
                    logger.info(f"[群聊学习] 向群<{group_id}>主动发言: {msg_text}")
                    self._record_bot_message(group_id, self._get_bot_id(), msg_text)
                    await asyncio.sleep(random.randint(2, 4))
                except Exception as e:
                    logger.warning(f"[群聊学习] 主动发言发送失败: {e}")

            self.last_speak_time[group_id] = cur_time
            break  # 一次只对一个群发言

    def _find_speak_messages(self, group_id: str, group_config: ChatGroupConfig) -> list[str]:
        """寻找合适的主动发言内容"""
        speak_list = []
        contexts = list(self.storage["contexts"].values())
        if not contexts:
            return []

        # 按计数排序，随机选择
        contexts.sort(key=lambda x: x.count, reverse=True)
        random.shuffle(contexts[:20])  # 在 top 20 中随机

        for ctx in contexts:
            if len(speak_list) >= group_config.speak_continuously_max_len:
                break
            if random.random() > group_config.speak_continuously_probability and speak_list:
                break

            # 找该 context 在本群的回答
            answers = [
                a for a in self.storage["answers"]
                if a.context_keyword == ctx.keywords and a.group_id == group_id
                and a.count >= group_config.answer_threshold
            ]
            if not answers:
                continue

            answer = random.choices(
                answers,
                weights=[a.count for a in answers],
                k=1,
            )[0]

            msg = random.choice(answer.messages)
            if len(msg) < 2:
                continue
            if msg.startswith("&#91;") and msg.endswith("&#93;"):
                continue

            # 检查屏蔽词
            ban_words = set(self.config.ban_words + group_config.ban_words)
            if any(w in msg for w in ban_words):
                continue

            speak_list.append(msg)

            # 链式查找下一个 context
            follow_ctx = self.storage["contexts"].get(answer.keywords)
            if not follow_ctx:
                break

        return speak_list

    def _get_bot_id(self) -> str:
        """获取 Bot 的 ID"""
        try:
            return self.context.get_astrbot_config().get("qq", "bot")
        except Exception:
            return "bot"

    async def _send_group_message(self, group_id: str, message: str):
        """发送群消息（尝试使用平台 API）"""
        try:
            platforms = self.context.platform_manager.get_insts()
            for plat in platforms:
                try:
                    client = plat.get_client()
                    if hasattr(client, 'api') and hasattr(client.api, 'send_group_msg'):
                        await client.api.send_group_msg(group_id=int(group_id), message=message)
                        return
                except Exception:
                    pass
        except Exception:
            pass

        logger.warning(f"[群聊学习] 无法通过平台 API 发送消息到群<{group_id}>")

    # ========== 指令处理 ==========

    @filter.command("学说话")
    async def enable_learning(self, event: AstrMessageEvent):
        """开启学习"""
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令")
            return

        group_config = self._get_group_config(group_id)
        group_config.enable = True
        self._save_config()
        yield event.plain_result("好的呢，我开始学说话啦~")

    @filter.command("闭嘴")
    async def disable_learning(self, event: AstrMessageEvent):
        """关闭学习"""
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令")
            return

        group_config = self._get_group_config(group_id)
        group_config.enable = False
        self._save_config()
        yield event.plain_result("好好好，我不学说话了...")

    @filter.command("学习状态")
    async def learning_status(self, event: AstrMessageEvent):
        """查看学习状态"""
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令")
            return

        group_config = self._get_group_config(group_id)
        status = "开启" if group_config.enable else "关闭"
        total_contexts = len(self.storage["contexts"])
        total_answers = sum(len(a.messages) for a in self.storage["answers"])

        yield event.plain_result(
            f"群聊学习状态:\n"
            f"总开关: {'开启' if self.config.total_enable else '关闭'}\n"
            f"本群学习: {status}\n"
            f"已学习语境: {total_contexts} 个\n"
            f"已学习回复: {total_answers} 句\n"
        )

    async def terminate(self):
        """插件卸载时调用"""
        self._save_storage()
        self._save_config()
        if self._speak_task:
            self._speak_task.cancel()