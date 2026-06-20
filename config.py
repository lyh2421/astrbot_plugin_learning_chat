"""
配置模块
"""

from typing import List, Dict


class ChatGroupConfig:
    """群聊配置"""

    def __init__(self):
        self.enable: bool = True
        self.ban_words: List[str] = []
        self.ban_users: List[str] = []
        self.answer_threshold: int = 4
        self.answer_threshold_weights: List[int] = [10, 30, 60]
        self.repeat_threshold: int = 3
        self.break_probability: float = 0.25
        self.speak_enable: bool = True
        self.speak_threshold: int = 5
        self.speak_min_interval: int = 300
        self.speak_continuously_probability: float = 0.5
        self.speak_continuously_max_len: int = 3
        self.speak_poke_probability: float = 0.5

    def to_dict(self) -> dict:
        return {
            "enable": self.enable,
            "ban_words": self.ban_words,
            "ban_users": self.ban_users,
            "answer_threshold": self.answer_threshold,
            "answer_threshold_weights": self.answer_threshold_weights,
            "repeat_threshold": self.repeat_threshold,
            "break_probability": self.break_probability,
            "speak_enable": self.speak_enable,
            "speak_threshold": self.speak_threshold,
            "speak_min_interval": self.speak_min_interval,
            "speak_continuously_probability": self.speak_continuously_probability,
            "speak_continuously_max_len": self.speak_continuously_max_len,
            "speak_poke_probability": self.speak_poke_probability,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatGroupConfig":
        config = cls()
        config.enable = data.get("enable", True)
        config.ban_words = data.get("ban_words", [])
        config.ban_users = data.get("ban_users", [])
        config.answer_threshold = data.get("answer_threshold", 4)
        config.answer_threshold_weights = data.get("answer_threshold_weights", [10, 30, 60])
        config.repeat_threshold = data.get("repeat_threshold", 3)
        config.break_probability = data.get("break_probability", 0.25)
        config.speak_enable = data.get("speak_enable", True)
        config.speak_threshold = data.get("speak_threshold", 5)
        config.speak_min_interval = data.get("speak_min_interval", 300)
        config.speak_continuously_probability = data.get("speak_continuously_probability", 0.5)
        config.speak_continuously_max_len = data.get("speak_continuously_max_len", 3)
        config.speak_poke_probability = data.get("speak_poke_probability", 0.5)
        return config


class ChatConfig:
    """全局配置"""

    def __init__(self):
        self.total_enable: bool = True
        self.ban_words: List[str] = []
        self.ban_users: List[str] = []
        self.KEYWORDS_SIZE: int = 3
        self.cross_group_threshold: int = 3
        self.learn_max_count: int = 6
        self.dictionary: List[str] = []
        self.group_configs: Dict[str, ChatGroupConfig] = {}

    def to_dict(self) -> dict:
        return {
            "total_enable": self.total_enable,
            "ban_words": self.ban_words,
            "ban_users": self.ban_users,
            "KEYWORDS_SIZE": self.KEYWORDS_SIZE,
            "cross_group_threshold": self.cross_group_threshold,
            "learn_max_count": self.learn_max_count,
            "dictionary": self.dictionary,
            "group_configs": {
                k: v.to_dict() for k, v in self.group_configs.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatConfig":
        config = cls()
        config.total_enable = data.get("total_enable", True)
        config.ban_words = data.get("ban_words", [])
        config.ban_users = data.get("ban_users", [])
        config.KEYWORDS_SIZE = data.get("KEYWORDS_SIZE", 3)
        config.cross_group_threshold = data.get("cross_group_threshold", 3)
        config.learn_max_count = data.get("learn_max_count", 6)
        config.dictionary = data.get("dictionary", [])
        config.group_configs = {
            k: ChatGroupConfig.from_dict(v)
            for k, v in data.get("group_configs", {}).items()
        }
        return config