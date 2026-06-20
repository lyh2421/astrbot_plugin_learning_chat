"""
核心学习逻辑 - 从 nonebot-plugin-learning-chat 移植
"""

import random
import time
from typing import List, Optional

from .models import ChatMessage, ChatContext, ChatAnswer, ChatBlackList, LearnResult
from .config import ChatConfig, ChatGroupConfig


class LearningChat:
    """群聊学习核心类"""

    def __init__(
        self,
        chat_msg: ChatMessage,
        group_config: ChatGroupConfig,
        config: ChatConfig,
        storage: dict,
        bot_id: str = "bot",
    ):
        self.chat_msg = chat_msg
        self.group_config = group_config
        self.config = config
        self.storage = storage
        self.bot_id = str(bot_id)

        # 合并屏蔽列表
        self.ban_users = set(config.ban_users + group_config.ban_users)
        self.ban_words = set(config.ban_words + group_config.ban_words)

    def learn(self) -> LearnResult:
        """核心学习与回复逻辑"""
        msg = self.chat_msg

        # 检查总开关和群开关
        if not self.config.total_enable or not self.group_config.enable:
            return LearnResult(action="pass")

        # 检查发言人是否在屏蔽列表
        if msg.user_id in self.ban_users:
            return LearnResult(action="pass")

        # 检查消息是否合法
        if not self._check_allow(msg):
            return LearnResult(action="pass")

        # 如果是纯文本且太短（1个字符），不回复
        if msg.is_plain_text and len(msg.plain_text) <= 1:
            return LearnResult(action="pass")

        # 检查是否有已知的上下文可以回复
        reply = self._find_reply()
        if reply:
            return LearnResult(action="reply", reply=reply)

        # 检查是否需要复读
        repeat = self._check_repeat()
        if repeat:
            return LearnResult(action="repeat", reply=repeat)

        # 学习新消息：尝试建立上下文关联
        self._learn_new_message()

        return LearnResult(action="pass")

    def _check_allow(self, msg: ChatMessage) -> bool:
        """检查消息是否允许处理"""
        raw = msg.message
        if not raw or len(raw) < 1:
            return False

        # 检查 CQ 码
        for cq_code in ["[CQ:xml", "[CQ:json", "[CQ:at", "[CQ:video", "[CQ:record", "[CQ:share"]:
            if cq_code in raw:
                return False

        # 检查屏蔽词
        if any(w in raw for w in self.ban_words):
            return False

        # 检查 HTML 实体开头（表情等）
        if raw.startswith("&#91;") and raw.endswith("&#93;"):
            return False

        # 检查黑名单
        if msg.keywords in self.storage["blacklist"]:
            bl = self.storage["blacklist"][msg.keywords]
            if bl.global_ban or msg.group_id in bl.ban_group_id:
                return False

        return True

    def _find_reply(self) -> Optional[str]:
        """查找适合的回复"""
        if not self.chat_msg.keywords:
            return None

        # 在本群的回答中查找匹配
        matching_answers = []
        for answer in self.storage["answers"]:
            if (
                answer.group_id == self.chat_msg.group_id
                and answer.count >= self.group_config.answer_threshold
            ):
                # 检查关键词是否匹配
                answer_kws = set(answer.keywords.split(","))
                msg_kws = set(self.chat_msg.keywords.split(","))
                if answer_kws & msg_kws:  # 有交集
                    matching_answers.append(answer)

        if not matching_answers:
            # 跨群查找
            for answer in self.storage["answers"]:
                if answer.count >= self.config.cross_group_threshold:
                    answer_kws = set(answer.keywords.split(","))
                    msg_kws = set(self.chat_msg.keywords.split(","))
                    if answer_kws & msg_kws:
                        matching_answers.append(answer)

        if not matching_answers:
            return None

        # 按权重随机选择
        weights = []
        for a in matching_answers:
            w = a.count
            # 增加时间权重
            hrs_ago = (int(time.time()) - a.time) / 3600
            if hrs_ago < 10:
                w += self.group_config.answer_threshold_weights[0]  # 10小时内
            elif hrs_ago < 30:
                w += self.group_config.answer_threshold_weights[1]  # 30小时内
            else:
                w += self.group_config.answer_threshold_weights[2]  # 更早
            weights.append(max(w, 1))

        chosen = random.choices(matching_answers, weights=weights, k=1)[0]
        return random.choice(chosen.messages)

    def _check_repeat(self) -> Optional[str]:
        """检查是否需要复读"""
        threshold = self.group_config.repeat_threshold

        # 获取最近的消息
        recent = self.storage["messages"][-threshold:]
        if len(recent) < threshold:
            return None

        # 检查最近 threshold 条是否是相同内容
        target_msg = self.chat_msg.message
        same_msgs = [m for m in recent[-threshold:] if m.message == target_msg]

        if len(same_msgs) < threshold:
            return None

        # 检查是否全部是同一人
        if all(m.user_id == self.chat_msg.user_id for m in same_msgs):
            return None

        # 检查 Bot 是否已经复读过
        if any(m.user_id == self.bot_id and m.message == target_msg for m in recent[-threshold-5:]):
            return None

        # 复读！
        return target_msg

    def _learn_new_message(self):
        """学习新消息：建立上下文关联"""
        msg = self.chat_msg
        if not msg.keywords:
            return

        # 查找最近的关联消息（作为 context）
        recent_msgs = [m for m in self.storage["messages"][-10:]
                       if m.user_id != self.bot_id
                       and m.keywords
                       and m.keywords != msg.keywords]

        if not recent_msgs:
            return

        # 找最匹配的上下文
        best_context_msg = None
        best_score = 0
        for recent in recent_msgs:
            recent_kws = set(recent.keywords.split(","))
            msg_kws = set(msg.keywords.split(","))
            overlap = recent_kws & msg_kws
            # 有关键词重叠但不是完全相同
            if overlap and recent.keywords != msg.keywords:
                score = len(overlap)
                if score > best_score:
                    best_score = score
                    best_context_msg = recent

        if not best_context_msg:
            return

        # 建立 context
        ctx_key = best_context_msg.keywords
        if ctx_key not in self.storage["contexts"]:
            ctx = ChatContext(keywords=ctx_key, count=1, time=int(time.time()))
            self.storage["contexts"][ctx_key] = ctx
        else:
            ctx = self.storage["contexts"][ctx_key]
            if ctx.count < self.config.learn_max_count:
                ctx.count += 1
            ctx.time = int(time.time())

        # 建立或更新 answer
        answer_exists = False
        for answer in self.storage["answers"]:
            if (answer.keywords == msg.keywords
                    and answer.group_id == msg.group_id
                    and answer.context_keyword == ctx_key):
                answer_exists = True
                if answer.count < self.config.learn_max_count:
                    answer.count += 1
                answer.time = int(time.time())
                if msg.message not in answer.messages:
                    answer.messages.append(msg.message)
                break

        if not answer_exists:
            answer = ChatAnswer(
                keywords=msg.keywords,
                group_id=msg.group_id,
                context_keyword=ctx_key,
                messages=[msg.message],
                count=1,
                time=int(time.time()),
            )
            self.storage["answers"].append(answer)