"""
Acemap 搜索接口客户端。

使用示例：
    python search_acemap.py rock

该脚本调用 Acemap 的公开 API，并以直观的文本格式打印结果。
默认同时搜索论文、作者和机构。
"""

from __future__ import annotations

import argparse
import sys
from typing import Dict, Any, List

import requests

API_BASE = "https://acemap.info/api/v1"
ENDPOINTS = {
    "work": f"{API_BASE}/work/search",
    "author": f"{API_BASE}/author/search",
    "institution": f"{API_BASE}/institution/search",
}


def build_params(search_type: str, keyword: str, page: int, size: int, order: str, sort: str = None) -> Dict[str, Any]:
    """构建请求参数"""
    params: Dict[str, Any] = {"keyword": keyword, "page": page, "size": size}
    if search_type == "work":
        params["order"] = order
        if sort:
            params["sort"] = sort
    return params


def search_acemap(search_type: str, keyword: str, page: int = 1, size: int = 10, order: str = "desc", sort: str = None) -> Dict[str, Any]:
    """
    执行单个类型的搜索。
    如果指定了 sort (且为 work 类型)，则执行客户端重排序：
    1. 获取更多结果 (默认 50 条或更多)
    2. 在内存中排序
    3. 返回指定页的结果
    """
    if search_type not in ENDPOINTS:
        raise ValueError(f"无效的类型 '{search_type}'。请使用以下之一: {', '.join(ENDPOINTS)}")

    # 如果需要排序 (仅支持 work)，则启用重排序逻辑
    if search_type == "work" and sort:
        # 策略：获取足够多的数据进行排序
        # 为了演示效果，我们获取前 200 条 (或者如果请求的页码靠后，则获取更多)
        # 注意：由于 API 不支持服务端排序，这里只能在有限的结果集中进行排序，
        # 因此结果可能与网页版（全量排序）不一致。
        target_count = max(page * size, 200)
        if target_count > 500: target_count = 500 # 限制最大获取数量以防超时

        all_results = []
        current_page = 1
        max_page_size = 100 # API 限制最大 100
        
        try:
            # 分页获取数据直到满足 target_count
            while len(all_results) < target_count:
                # 计算本次需要获取的数量，虽然 API 允许 size=100，但我们只需要够用就行
                # 不过为了减少请求次数，直接用 max_page_size 比较好
                params = build_params(search_type, keyword, current_page, max_page_size, "desc")
                
                response = requests.get(
                    ENDPOINTS[search_type],
                    params=params,
                    headers={"User-Agent": "acemap-search-demo/0.1"},
                    timeout=20,
                )
                response.raise_for_status()
                data = response.json()
                
                page_results = data.get("results", [])
                if not page_results:
                    break # 没有更多数据了
                
                all_results.extend(page_results)
                
                # 如果获取到的数据少于请求的数量，说明已经是最后一页了
                if len(page_results) < max_page_size:
                    break
                    
                current_page += 1
            
            # 构造返回数据结构，复用最后一次请求的 meta 信息（虽然 count 可能不准，但够用了）
            final_data = data 
            final_data['results'] = all_results # 暂存所有结果
            
            # 内存中排序
            reverse = (order == 'desc')
            
            if sort == 'cited_by_count':
                all_results.sort(key=lambda x: x.get('cited_by_count', 0) or 0, reverse=reverse)
            elif sort == 'publication_date':
                # 使用 publication_date 字符串排序，如果为空则用 publication_year
                def date_key(x):
                    d = x.get('publication_date')
                    if d: return d
                    y = x.get('publication_year')
                    # 如果没有日期，根据排序顺序放到最后或最前
                    return "9999" if reverse else "0000"
                all_results.sort(key=date_key, reverse=reverse)
            
            # 分页切片
            start_idx = (page - 1) * size
            end_idx = start_idx + size
            
            # 更新 results 为切片后的结果
            final_data['results'] = all_results[start_idx:end_idx]
            
            return final_data
            
        except Exception as e:
            raise e

    # 默认逻辑 (无排序或非 work 类型)
    params = build_params(search_type, keyword, page, size, order, sort)
    try:
        response = requests.get(
            ENDPOINTS[search_type],
            params=params,
            headers={"User-Agent": "acemap-search-demo/0.1"},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise e


def search_all(keyword: str, sort: str = None, order: str = "desc") -> Dict[str, Any]:
    """
    聚合搜索：同时搜索论文、作者和机构。
    """
    results = {}
    
    # 搜索论文
    try:
        results['work'] = search_acemap('work', keyword, size=5, sort=sort, order=order)
    except Exception as e:
        results['work'] = {"error": str(e), "results": []}

    # 搜索作者
    try:
        results['author'] = search_acemap('author', keyword, size=3)
    except Exception as e:
        results['author'] = {"error": str(e), "results": []}

    # 搜索机构
    try:
        results['institution'] = search_acemap('institution', keyword, size=3)
    except Exception as e:
        results['institution'] = {"error": str(e), "results": []}
        
    return results


# --- 结果展示函数 ---

def display_work(item: Dict[str, Any]):
    """打印单个论文条目"""
    title = item.get("display_name") or item.get("title") or "无标题"
    year = item.get("publication_year", "未知年份")
    
    # 提取作者
    authors = []
    for a in item.get("authorships", []):
        if a.get("author") and a.get("author").get("display_name"):
            authors.append(a["author"]["display_name"])
    author_str = ", ".join(authors[:5]) # 最多显示5位作者
    if len(authors) > 5: author_str += " 等"
    
    print(f"📄 [论文] {title}")
    print(f"    年份: {year} | 作者: {author_str}")
    print("-" * 60)


def display_author(item: Dict[str, Any]):
    """打印单个作者条目"""
    name = item.get("display_name", "未知姓名")
    
    # 提取机构
    orgs = []
    for aff in item.get("affiliations", []):
        if aff.get("institution") and aff.get("institution").get("display_name"):
            orgs.append(aff["institution"]["display_name"])
    org_str = ", ".join(orgs) or "未知机构"
    
    stats = item.get("summary_stats", {}) or {}
    h_index = stats.get("h_index", "N/A")
    
    print(f"👤 [作者] {name}")
    print(f"    机构: {org_str}")
    print(f"    H-Index: {h_index} | 论文数: {item.get('works_count', 0)}")
    print("-" * 60)


def display_institution(item: Dict[str, Any]):
    """打印单个机构条目"""
    name = item.get("display_name", "未知机构")
    country = item.get("country_code", "")
    city = item.get("geo", {}).get("city", "")
    
    loc_parts = [p for p in [city, country] if p]
    loc = ", ".join(loc_parts) if loc_parts else "未知位置"
    
    print(f"🏛️ [机构] {name}")
    print(f"    位置: {loc}")
    print(f"    论文数: {item.get('works_count', 0)}")
    print("-" * 60)


def display_list(items: List[Dict[str, Any]], item_type: str):
    """打印列表"""
    if not items:
        print("    (无结果)")
        return

    for item in items:
        if item_type == 'work':
            display_work(item)
        elif item_type == 'author':
            display_author(item)
        elif item_type == 'institution':
            display_institution(item)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="调用 Acemap 搜索 API")
    parser.add_argument("keyword", help="搜索关键词")
    parser.add_argument("--type", choices=ENDPOINTS.keys(), help="指定搜索类型 (可选，默认搜索全部)")
    parser.add_argument("--page", type=int, default=1, help="页码 (默认 1)")
    parser.add_argument("--size", type=int, default=10, help="每页数量 (默认 10)")

    args = parser.parse_args(argv)
    
    print(f"\n🔍 正在搜索: '{args.keyword}' ...\n")
    print("=" * 60)

    try:
        if args.type:
            # 单一类型搜索
            result = search_acemap(args.type, args.keyword, args.page, args.size)
            items = result.get("results", [])
            count = result.get("meta", {}).get("count", 0)
            print(f"找到约 {count} 条结果 (显示前 {len(items)} 条):")
            print("-" * 60)
            display_list(items, args.type)
        else:
            # 聚合搜索
            results = search_all(args.keyword)
            
            # 1. 论文
            work_res = results.get('work', {})
            if "error" not in work_res:
                count = work_res.get("meta", {}).get("count", 0)
                print(f"\n=== 📄 相关论文 (约 {count} 篇) ===")
                display_list(work_res.get("results", []), 'work')
            
            # 2. 作者
            auth_res = results.get('author', {})
            if "error" not in auth_res:
                count = auth_res.get("meta", {}).get("count", 0)
                print(f"\n=== 👤 相关作者 (约 {count} 位) ===")
                display_list(auth_res.get("results", []), 'author')

            # 3. 机构
            inst_res = results.get('institution', {})
            if "error" not in inst_res:
                count = inst_res.get("meta", {}).get("count", 0)
                print(f"\n=== 🏛️ 相关机构 (约 {count} 个) ===")
                display_list(inst_res.get("results", []), 'institution')

    except requests.HTTPError as exc:
        sys.stderr.write(f"HTTP 错误: {exc}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"错误: {exc}\n")
        return 1

    print("\n搜索完成。\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
