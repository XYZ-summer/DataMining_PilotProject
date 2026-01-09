"""
搜索意图理解模块。
负责解析用户的自然语言查询，提取核心关键词、排序意图和类型意图。
"""

import re
from typing import Dict, Any

class IntentParser:
    def __init__(self):
        # 排序意图关键词
        self.time_keywords = ["recent", "latest", "new", "newest", "current", "latest research", "recent papers"]
        self.citation_keywords = ["popular", "cited", "best", "top", "famous", "impactful", "highly cited", "most cited"]
        
        # 类型意图关键词
        self.author_keywords = ["author", "researcher", "scientist", "who wrote", "written by", "people"]
        self.inst_keywords = ["institution", "university", "lab", "laboratory", "center", "college", "school"]
        
        # 停用词/短语 (用于清洗出核心关键词)
        self.stop_phrases = [
            "research on", "papers about", "results for", "show me", "find", "search for", 
            "articles on", "documents about", "information on", "tell me about", "papers on",
            "results of", "list of"
        ]

    def parse(self, query: str) -> Dict[str, Any]:
        """
        解析用户查询，提取意图。
        返回字典:
        {
            "original_query": str,
            "keyword": str,       # 清洗后的核心关键词
            "sort": str,          # 'relevance', 'date', 'citation'
            "type": str,          # 'work', 'author', 'institution' (None 表示未明确指定)
        }
        """
        if not query:
            return {"original_query": "", "keyword": "", "sort": None, "type": None}

        query_lower = query.lower()
        intent = {
            "original_query": query,
            "keyword": query,
            "sort": None, # None 表示保持默认 (relevance)
            "type": None, # None 表示保持默认
        }

        # 1. 识别排序意图
        # 优先匹配引用
        if any(k in query_lower for k in self.citation_keywords):
            intent["sort"] = "citation"
        # 其次匹配时间
        elif any(k in query_lower for k in self.time_keywords):
            intent["sort"] = "date"
            
        # 2. 识别类型意图
        if any(k in query_lower for k in self.author_keywords):
            intent["type"] = "author"
        elif any(k in query_lower for k in self.inst_keywords):
            intent["type"] = "institution"

        # 3. 提取核心关键词
        clean_query = query
        
        # 移除停用短语 (不区分大小写)
        for phrase in self.stop_phrases:
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            clean_query = pattern.sub("", clean_query)
            
        # 移除意图关键词 (避免它们干扰搜索)
        words_to_remove = []
        if intent["sort"] == "date":
            words_to_remove.extend(self.time_keywords)
        if intent["sort"] == "citation":
            words_to_remove.extend(self.citation_keywords)
        if intent["type"] == "author":
            words_to_remove.extend(self.author_keywords)
        if intent["type"] == "institution":
            words_to_remove.extend(self.inst_keywords)
            
        for word in words_to_remove:
            # 使用 \b 匹配单词边界
            # 注意：有些关键词包含空格，需要先处理
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
            clean_query = pattern.sub("", clean_query)

        # 清理多余空格和标点
        clean_query = re.sub(r'[^\w\s]', ' ', clean_query) # 简单去除标点
        intent["keyword"] = " ".join(clean_query.split())
        
        # 如果清理后为空（例如用户只搜了 "recent papers"），则回退到原始查询
        if not intent["keyword"]:
            intent["keyword"] = query

        return intent
