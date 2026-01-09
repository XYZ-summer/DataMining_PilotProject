import streamlit as st
from search import search_all
from recall import search_with_recall, KGManager
from intent import IntentParser

st.set_page_config(page_title="Acemap 搜索增强", page_icon="🔍", layout="wide")

# 初始化 KGManager (使用 st.cache_resource 避免重复加载)
@st.cache_resource
def get_kg_manager():
    return KGManager()

kg_manager = get_kg_manager()
parser = IntentParser()

# 初始化 Session State
if "selected_sort" not in st.session_state:
    st.session_state.selected_sort = "最佳匹配"
if "last_keyword" not in st.session_state:
    st.session_state.last_keyword = ""

st.title("🔍 Acemap 搜索增强")

# 简化的搜索界面：只有一个输入框和按钮
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    keyword = st.text_input("请输入关键词...", placeholder="例如: rock, plate tectonics")
    
    # 监听关键词变化，自动更新排序选项
    if keyword != st.session_state.last_keyword:
        parsed = parser.parse(keyword)
        intent_sort = parsed.get('sort')
        if intent_sort == 'date':
            st.session_state.selected_sort = "最新发表"
        elif intent_sort == 'citation':
            st.session_state.selected_sort = "引用最多"
        st.session_state.last_keyword = keyword

with col2:
    sort_option = st.selectbox(
        "排序方式",
        ("最佳匹配", "引用最多", "引用最少", "最新发表", "最早发表"),
        key="selected_sort"
    )
with col3:
    st.write("") # 占位符，为了对齐
    st.write("") 
    search_btn = st.button("搜索", type="primary", use_container_width=True)

def render_work_item(item):
    """渲染单个论文结果"""
    title = item.get("display_name") or item.get("title")
    primary_loc = item.get("primary_location") or {}
    url = primary_loc.get("landing_page_url")
    year = item.get("publication_year")
    cited_by_count = item.get("cited_by_count", 0)
    
    # 提取专业类型 (Topics/Concepts)
    topics = []
    # 优先使用 topics
    if item.get("topics"):
        for t in item.get("topics")[:3]: # 取前3个
            if t.get("display_name"):
                topics.append(t.get("display_name"))
    # 如果没有 topics，尝试 concepts
    elif item.get("concepts"):
        for c in item.get("concepts")[:3]:
            if c.get("display_name"):
                topics.append(c.get("display_name"))
    
    topic_str = ", ".join(topics) if topics else "未知领域"

    # 处理作者
    authors_list = item.get("authorships", [])
    author_names = []
    for a in authors_list:
        auth_info = a.get("author", {})
        if auth_info and auth_info.get("display_name"):
            author_names.append(auth_info.get("display_name"))
    authors = ", ".join(author_names)
    
    if url:
        st.markdown(f"#### 📄 [{title}]({url})")
    else:
        st.markdown(f"#### 📄 {title}")
    
    # 显示来源概念（如果是增强搜索结果）
    source_concept = item.get("_source_concept")
    if source_concept:
        st.info(f"💡 推荐理由：与概念 **{source_concept}** 相关")
        
    st.markdown(f"**年份:** {year} | **引用数:** {cited_by_count} | **领域:** {topic_str}")
    st.markdown(f"**作者:** {authors}")
    
    if item.get("abstract"):
        st.caption(item.get("abstract")[:200] + "...")
    st.divider()

def render_author_item(item):
    """渲染单个作者结果"""
    name = item.get("display_name")
    affiliations = item.get("affiliations", [])
    orgs = []
    for aff in affiliations:
        inst = aff.get("institution")
        if inst and inst.get("display_name"):
            orgs.append(inst.get("display_name"))
            
    org_str = ", ".join(orgs) if orgs else "未知机构"
    stats = item.get("summary_stats", {}) or {}
    h_index = stats.get("h_index", "N/A")
    works_count = item.get("works_count", 0)
    
    st.markdown(f"#### 👤 {name}")
    st.text(f"机构: {org_str}")
    st.caption(f"论文数: {works_count} | H-Index: {h_index}")
    st.divider()

def render_institution_item(item):
    """渲染单个机构结果"""
    name = item.get("display_name")
    country = item.get("country_code", "")
    geo = item.get("geo") or {}
    city = geo.get("city", "")
    homepage = item.get("homepage_url")
    
    if homepage:
        st.markdown(f"#### 🏛️ [{name}]({homepage})")
    else:
        st.markdown(f"#### 🏛️ {name}")
        
    location_parts = []
    if city: location_parts.append(city)
    if country: location_parts.append(country)
    location = ", ".join(location_parts)
    
    st.text(f"位置: {location}")
    st.caption(f"论文数: {item.get('works_count', 0)}")
    st.divider()

# 只要关键词存在（回车或点击按钮或切换排序），就执行搜索
if keyword:
    # 意图识别 (仅用于提取关键词)
    parsed_intent = parser.parse(keyword)
    search_keyword = parsed_intent.get('keyword', keyword)
    
    # 映射排序选项到 API 参数
    sort_map = {
        "最佳匹配": (None, "desc"),
        "引用最多": ("cited_by_count", "desc"),
        "引用最少": ("cited_by_count", "asc"),
        "最新发表": ("publication_date", "desc"),
        "最早发表": ("publication_date", "asc")
    }
    
    # 直接使用 UI 选择的排序 (因为它已经根据意图自动更新了)
    sort_param, order_param = sort_map.get(sort_option, (None, "desc"))
    
    if search_keyword != keyword:
        st.toast(f"🎯 已优化搜索关键词: {search_keyword}")

    with st.spinner(f"正在全网搜索 '{search_keyword}'..."):
        # 1. 先执行标准聚合搜索 (作者、机构等)
        all_results = search_all(search_keyword, sort=sort_param, order=order_param)
        
        # 2. 单独处理论文搜索：使用知识图谱增强
        # 注意：如果用户选择了排序，增强搜索可能会比较慢，且排序逻辑会变得复杂
        # 这里我们简化处理：增强搜索主要用于召回更多相关内容，暂时忽略排序参数对增强部分的影响
        # 或者我们可以将增强搜索的结果也纳入排序逻辑（需要修改 recall.py）
        
        # 调用增强搜索
        recall_data = search_with_recall(search_keyword, kg_manager, sort=sort_param, order=order_param)
        
        # 将增强搜索得到的论文结果覆盖到 all_results['work'] 中
        # 注意：search_with_recall 返回的是一个字典，包含 'results' 列表
        # 我们需要构造一个符合 search_all 返回格式的结构
        
        # 简单的合并策略：
        # 如果用户没有选择特殊排序，直接使用增强结果
        # 如果用户选择了排序，我们可能需要对增强结果进行重排序
        
        enhanced_work_items = recall_data.get("results", [])
        
        # 如果有排序需求，对增强后的结果进行内存排序
        if sort_param:
             reverse = (order_param == 'desc')
             if sort_param == 'cited_by_count':
                enhanced_work_items.sort(key=lambda x: x.get('cited_by_count', 0) or 0, reverse=reverse)
             elif sort_param == 'publication_date':
                def date_key(x):
                    d = x.get('publication_date')
                    if d: return d
                    y = x.get('publication_year')
                    return "9999" if reverse else "0000"
                enhanced_work_items.sort(key=date_key, reverse=reverse)
        
        # 更新 all_results 中的 work 部分
        all_results['work'] = {
            "results": enhanced_work_items,
            "meta": {"count": len(enhanced_work_items)} # 这里 count 只是当前召回的数量，不是全库数量
        }
        
        # 获取相关概念用于展示
        related_concepts = recall_data.get("related_concepts", [])

    # 使用 Tabs 分类展示，或者直接分栏展示
    # 这里为了直观，使用 Tabs
    tab_work, tab_author, tab_inst = st.tabs(["📄 论文", "👤 作者", "🏛️ 机构"])
    
    # --- 论文展示 ---
    with tab_work:
        if related_concepts:
            st.success(f"🧠 知识图谱联想：已为您扩展搜索相关概念：**{', '.join(related_concepts)}**")
            
        res_work = all_results.get('work', {})
        if "error" in res_work:
            st.error(f"搜索论文时出错: {res_work['error']}")
        else:
            items = res_work.get("results", [])
            count = res_work.get("meta", {}).get("count", 0)
            
            if sort_param:
                st.warning(f"⚠️ 注意：当前使用的是客户端排序（基于前 200-500 条相关结果），可能无法显示全库中绝对{sort_option}的论文。")
                
            st.info(f"找到约 {count} 篇相关论文 (含知识图谱扩展结果)")
            if not items:
                st.warning("未找到相关论文")
            for item in items:
                render_work_item(item)

    # --- 作者展示 ---
    with tab_author:
        res_author = all_results.get('author', {})
        if "error" in res_author:
            st.error(f"搜索作者时出错: {res_author['error']}")
        else:
            items = res_author.get("results", [])
            count = res_author.get("meta", {}).get("count", 0)
            st.info(f"找到约 {count} 位相关作者")
            if not items:
                st.warning("未找到相关作者")
            for item in items:
                render_author_item(item)

    # --- 机构展示 ---
    with tab_inst:
        res_inst = all_results.get('institution', {})
        if "error" in res_inst:
            st.error(f"搜索机构时出错: {res_inst['error']}")
        else:
            items = res_inst.get("results", [])
            count = res_inst.get("meta", {}).get("count", 0)
            st.info(f"找到约 {count} 个相关机构")
            if not items:
                st.warning("未找到相关机构")
            for item in items:
                render_institution_item(item)

elif search_btn and not keyword:
    st.warning("请输入关键词")
