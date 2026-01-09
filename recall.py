"""
基于 GAKG 知识图谱的搜索召回增强模块。
功能：
1. 加载 GAKG 子图数据。
2. 根据用户输入的关键词，在知识图谱中查找相关联的概念（1跳邻居）。
3. 利用相关概念扩展搜索，召回更多相关文献。
"""

import pandas as pd
import os
from typing import List, Dict, Any
from search import search_acemap

# 数据路径
GAKG_PATH = os.path.join("data", "gakg_subset.parquet")

class KGManager:
    def __init__(self, data_path: str = GAKG_PATH):
        self.data_path = data_path
        self.df = None
        self._load_data()

    def _load_data(self):
        """加载 Parquet 数据"""
        if os.path.exists(self.data_path):
            try:
                self.df = pd.read_parquet(self.data_path)
                print(f"[KG] 已加载知识图谱数据，共 {len(self.df)} 条三元组。")
            except Exception as e:
                print(f"[KG] 加载数据失败: {e}")
                self.df = pd.DataFrame(columns=['subject', 'relation', 'object', 'paperid'])
        else:
            print(f"[KG] 数据文件不存在: {self.data_path}")
            self.df = pd.DataFrame(columns=['subject', 'relation', 'object', 'paperid'])

    def find_related_concepts(self, keyword: str, top_k: int = 5) -> List[str]:
        """
        查找与关键词相关的概念。
        策略：
        1. 查找 subject == keyword 的记录，取 object。
        2. 查找 object == keyword 的记录，取 subject。
        3. 按出现频率排序返回。
        """
        if self.df is None or self.df.empty:
            return []

        keyword = keyword.lower().strip()
        
        # 简单的全匹配，实际应用中可能需要模糊匹配或包含匹配
        # 这里为了演示，使用包含匹配，但要注意性能
        # 也可以先尝试精确匹配
        
        # 精确匹配
        mask_sub = self.df['subject'].str.lower() == keyword
        mask_obj = self.df['object'].str.lower() == keyword
        
        related_from_sub = self.df[mask_sub]['object'].tolist()
        related_from_obj = self.df[mask_obj]['subject'].tolist()
        
        all_related = related_from_sub + related_from_obj
        
        # 如果精确匹配太少，尝试包含匹配 (可选，视数据量而定)
        if len(all_related) < top_k:
             mask_sub_contains = self.df['subject'].str.lower().str.contains(keyword, regex=False)
             mask_obj_contains = self.df['object'].str.lower().str.contains(keyword, regex=False)
             
             # 排除掉已经是精确匹配的，避免重复计算（虽然最后会去重）
             # 这里简单处理，直接把包含匹配的结果加进来
             related_from_sub_c = self.df[mask_sub_contains]['object'].tolist()
             related_from_obj_c = self.df[mask_obj_contains]['subject'].tolist()
             all_related.extend(related_from_sub_c + related_from_obj_c)

        # 统计频率并排序
        from collections import Counter
        counter = Counter(all_related)
        
        # 移除关键词本身
        if keyword in counter:
            del counter[keyword]
            
        # 获取前 K 个高频概念
        top_concepts = [item for item, count in counter.most_common(top_k)]
        
        return top_concepts

def search_with_recall(keyword: str, kg_manager: KGManager = None, sort: str = None, order: str = "desc") -> Dict[str, Any]:
    """
    增强搜索：
    1. 搜索原始关键词。
    2. 从 KG 获取相关概念。
    3. 搜索相关概念。
    4. 合并结果。
    """
    if kg_manager is None:
        kg_manager = KGManager()
        
    print(f"正在搜索原始关键词: {keyword} (sort={sort}, order={order})")
    # 1. 原始搜索
    try:
        original_results = search_acemap("work", keyword, size=5, sort=sort, order=order)
    except Exception as e:
        print(f"原始搜索失败: {e}")
        original_results = {"results": []}

    # 2. 获取相关概念
    related_concepts = kg_manager.find_related_concepts(keyword, top_k=3)
    print(f"发现相关概念: {related_concepts}")
    
    expanded_results = []
    
    # 3. 搜索相关概念
    for concept in related_concepts:
        print(f"正在搜索相关概念: {concept}")
        try:
            # 限制每个相关概念只取前 2-3 条，避免喧宾夺主
            # 同样应用排序规则，保证相关概念召回的也是最新的/引用最高的
            res = search_acemap("work", concept, size=2, sort=sort, order=order)
            items = res.get("results", [])
            # 标记来源
            for item in items:
                item["_source_concept"] = concept
            expanded_results.extend(items)
        except Exception as e:
            print(f"搜索概念 '{concept}' 失败: {e}")

    # 4. 合并结果
    # 原始结果排在前面
    final_list = original_results.get("results", [])
    
    # 去重 (根据 ID)
    seen_ids = {item.get("id") for item in final_list}
    
    for item in expanded_results:
        if item.get("id") not in seen_ids:
            final_list.append(item)
            seen_ids.add(item.get("id"))
            
    return {
        "original_keyword": keyword,
        "related_concepts": related_concepts,
        "results": final_list,
        "total_count": len(final_list)
    }

if __name__ == "__main__":
    # 测试代码
    import sys
    if len(sys.argv) > 1:
        kw = sys.argv[1]
    else:
        kw = "rock"
        
    kg = KGManager()
    result = search_with_recall(kw, kg)
    
    print(f"\n=== '{kw}' 的增强搜索结果 ===")
    print(f"相关概念: {result['related_concepts']}")
    print(f"总共找到: {result['total_count']} 条文献")
    
    for i, item in enumerate(result['results']):
        source = f"(来自概念: {item.get('_source_concept')})" if item.get('_source_concept') else "(原始搜索)"
        print(f"{i+1}. {item.get('display_name')} {source}")
