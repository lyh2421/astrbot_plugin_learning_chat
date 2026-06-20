"""
数据模型 - 用于存储学习数据
"""

from typing import List
import re


class ChatMessage:
    """聊天消息"""

    def __init__(
        self,
        group_id: str,
        user_id: str,
        message: str,
        raw_message: str,
        plain_text: str,
        time: int,
        message_id: str = "",
    ):
        self.group_id = str(group_id)
        self.user_id = str(user_id)
        self.message = message
        self.raw_message = raw_message
        self.plain_text = plain_text
        self.time = time
        self.message_id = str(message_id) if message_id else ""
        self.keywords = ""
        self.keyword_list: List[str] = []
        self.is_plain_text = True

    def extract_keywords(self, keyword_size: int = 3, custom_dict: List[str] = None):
        """提取关键词"""
        text = self.plain_text.strip()
        if not text:
            self.keywords = ""
            self.keyword_list = []
            return

        # 移除 URL
        text = re.sub(r'https?://\S+', '', text)
        # 移除纯符号
        text = re.sub(r'[^\w\u4e00-\u9fff]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if not text:
            self.keywords = ""
            self.keyword_list = []
            return

        try:
            import jieba.analyse as jieba_analyse

            # 加载自定义词典
            if custom_dict:
                for word in custom_dict:
                    jieba_analyse.add_word(word)

            # TF-IDF 提取
            keywords_tfidf = jieba_analyse.extract_tags(
                text, topK=keyword_size, withWeight=False
            )
            # TextRank 提取
            keywords_textrank = jieba_analyse.textrank(
                text, topK=keyword_size, withWeight=False
            )

            # 合并去重
            all_keywords = list(dict.fromkeys(keywords_tfidf + keywords_textrank))
            self.keyword_list = all_keywords[:keyword_size * 2]

            # 排序后作为唯一标识
            self.keywords = ",".join(sorted(self.keyword_list))
        except Exception:
            self.keywords = text
            self.keyword_list = text.split()

    def to_dict(self) -> dict:
        return {
            "group_id": self.group_id,
            "user_id": self.user_id,
            "message": self.message,
            "raw_message": self.raw_message,
            "plain_text": self.plain_text,
            "time": self.time,
            "message_id": self.message_id,
            "keywords": self.keywords,
            "keyword_list": self.keyword_list,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        msg = cls(
            group_id=data.get("group_id", ""),
            user_id=data.get("user_id", ""),
            message=data.get("message", ""),
            raw_message=data.get("raw_message", ""),
            plain_text=data.get("plain_text", ""),
            time=data.get("time", 0),
            message_id=data.get("message_id", ""),
        )
        msg.keywords = data.get("keywords", "")
        msg.keyword_list = data.get("keyword_list", [])
        return msg


class ChatContext:
    """聊天上下文（某个关键词触发语境）"""

    def __init__(self, keywords: str, count: int = 1, time: int = 0):
        self.keywords = keywords
        self.count = count
        self.time = time or int(__import__("time").time())

    def to_dict(self) -> dict:
        return {
            "keywords": self.keywords,
            "count": self.count,
            "time": self.time,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatContext":
        return cls(
            keywords=data.get("keywords", ""),
            count=data.get("count", 1),
            time=data.get("time", 0),
        )


class ChatAnswer:
    """聊天回答（某个语境下的具体回答）"""

    def __init__(
        self,
        keywords: str,
        group_id: str,
        context_keyword: str,
        messages: List[str] = None,
        count: int = 1,
        time: int = 0,
    ):
        self.keywords = keywords
        self.group_id = str(group_id)
        self.context_keyword = context_keyword
        self.messages = messages or []
        self.count = count
        self.time = time or int(__import__("time").time())

    def to_dict(self) -> dict:
        return {
            "keywords": self.keywords,
            "group_id": self.group_id,
            "context_keyword": self.context_keyword,
            "messages": self.messages,
            "count": self.count,
            "time": self.time,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatAnswer":
        return cls(
            keywords=data.get("keywords", ""),
            group_id=data.get("group_id", ""),
            context_keyword=data.get("context_keyword", ""),
            messages=data.get("messages", []),
            count=data.get("count", 1),
            time=data.get("time", 0),
        )


class ChatBlackList:
    """黑名单词汇"""

    def __init__(
        self,
        keywords: str,
        global_ban: bool = False,
        ban_group_id: List[str] = None,
    ):
        self.keywords = keywords
        self.global_ban = global_ban
        self.ban_group_id = ban_group_id or []

    def to_dict(self) -> dict:
        return {
            "keywords": self.keywords,
            "global_ban": self.global_ban,
            "ban_group_id": self.ban_group_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatBlackList":
        return cls(
            keywords=data.get("keywords", ""),
            global_ban=data.get("global_ban", False),
            ban_group_id=data.get("ban_group_id", []),
        )


class LearnResult:
    """学习结果"""

    def __init__(self, action: str, reply: str = ""):
        self.action = action  # "pass", "reply", "repeat", "ban"
        self.reply = reply