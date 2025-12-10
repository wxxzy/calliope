import streamlit as st
import os
import re
from config import load_environment
import config_manager
import tool_provider
import text_splitter_provider
import vector_store_manager
from chains import create_planner_chain, create_research_chain, create_outliner_chain, create_drafter_chain, create_reviser_chain
from tools import check_ollama_model_availability

# --- 在应用的最开始加载环境变量 ---
load_environment()

# --- 页面配置 ---
st.set_page_config(
    page_title="AI 长篇写作智能体 (带记忆)",
    page_icon="📚",
    layout="wide"
)

# --- Helper Functions ---
def sanitize_project_name(name: str) -> str:
    """将项目名称转换为安全的ChromaDB集合名称。"""
    name = re.sub(r'[^\w-]', '_', name)
    name = re.sub(r'__+', '_', name)
    name = name.strip('_')
    if len(name) < 3:
        name = f"proj_{name}"
    return name.lower()

# --- 初始化和侧边栏 ---
def setup_sidebar():
    st.sidebar.title("📚 AI 长篇写作智能体")
    
    # --- 项目管理 ---
    st.sidebar.header("📝 写作项目管理")
    project_name_input = st.sidebar.text_input("输入新项目名称", key="project_name_input")
    if st.sidebar.button("创建新项目", key="create_project"):
        if project_name_input:
            collection_name = sanitize_project_name(project_name_input)
            st.session_state.project_name = project_name_input
            st.session_state.collection_name = collection_name
            # 重置项目相关的所有状态
            keys_to_reset = ['world_bible', 'plan', 'research_results', 'outline', 'drafts', 'drafting_index', 'final_manuscript']
            for key in keys_to_reset:
                if key in st.session_state:
                    del st.session_state[key]
            # 重置向量数据库集合
            with st.spinner(f"正在为新项目 '{project_name_input}' 创建记忆库..."):
                vector_store_manager.reset_collection(collection_name)
            st.sidebar.success(f"项目 '{project_name_input}' 已创建！")
        else:
            st.sidebar.error("请输入项目名称！")

    st.sidebar.markdown("---")
    
    # --- 动态配置UI ---
    st.sidebar.header("⚙️ 系统配置")
    
    # 加载配置和模板
    try:
        if 'config_data' not in st.session_state:
            st.session_state['config_data'] = config_manager.load_config()
        if 'provider_templates' not in st.session_state:
            st.session_state['provider_templates'] = config_manager.load_provider_templates()
        if 'tool_templates' not in st.session_state:
            st.session_state['tool_templates'] = tool_provider.get_tool_templates()
    except (FileNotFoundError, ValueError) as e:
        st.error(f"加载配置文件失败: {e}")
        st.stop()

    config_data = st.session_state['config_data']
    provider_templates = st.session_state['provider_templates']
    tool_templates = st.session_state['tool_templates']

    # Embedding模型选择
    with st.expander("记忆模型配置", expanded=False):
        embedding_models_config = config_data.get("embeddings", {})
        available_embedding_ids = list(embedding_models_config.keys())
        active_embedding_id = config_data.get("active_embedding_model")
        
        # 确保当前激活的模型ID在可用列表中，否则默认选择第一个
        try:
            current_emb_index = available_embedding_ids.index(active_embedding_id) if active_embedding_id in available_embedding_ids else 0
        except ValueError: # 如果 active_embedding_id 不在列表中 (例如配置错误)，则选择第一个
            current_emb_index = 0
            
        new_active_embedding_id = st.selectbox(
            "当前记忆/向量化模型", 
            options=available_embedding_ids, 
            index=current_emb_index, 
            key="active_embedding_model_select"
        )
        
        if st.button("保存记忆模型配置", key="save_embedding_config"):
            st.session_state['config_data']['active_embedding_model'] = new_active_embedding_id
            try:
                config_manager.save_config(st.session_state['config_data'])
                st.success("记忆模型配置已更新！")
            except IOError as e:
                st.error(f"保存配置失败: {e}")

    # 步骤模型分配
    with st.expander("步骤模型分配", expanded=False):
        steps_config = config_data.get("steps", {})
        available_model_ids = list(config_data.get("models", {}).keys())
        
        new_steps_config = {}
        for step, current_model_id in steps_config.items():
            try:
                current_index = available_model_ids.index(current_model_id) if current_model_id in available_model_ids else 0
            except ValueError:
                current_index = 0
            selected_model = st.selectbox(f"步骤: {step.capitalize()}", options=available_model_ids, index=current_index, key=f"step_{step}")
            new_steps_config[step] = selected_model

        if st.button("保存步骤分配", key="save_steps"):
            st.session_state['config_data']['steps'] = new_steps_config
            config_manager.save_config(st.session_state['config_data'])
            st.success("步骤分配已保存！")
    
    # 省略模型和工具实例管理的UI代码以保持简洁，逻辑不变

setup_sidebar()

# --- 主界面 ---
if 'project_name' not in st.session_state:
    st.info("👈 请在左侧边栏创建或选择一个写作项目以开始。")
    st.stop()

st.title(f"项目: {st.session_state.project_name}")
collection_name = st.session_state.collection_name

# --- 核心记忆：世界观圣经 ---
with st.container(border=True):
    st.header("🧠 核心记忆 (世界观)")
    world_bible = st.text_area(
        "在此输入项目的核心设定、人物小传、情节大纲等关键信息。",
        key="world_bible",
        height=200,
        placeholder="例如：主角：艾拉，一位记忆侦探...\n反派：Morpheus，一个数据幽灵..."
    )
    if st.button("更新核心记忆", key="update_memory"):
        with st.spinner("正在将核心记忆存入向量数据库..."):
            active_splitter_id = st.session_state.get('active_text_splitter', 'default_recursive') # 获取当前激活的切分器
            text_splitter = text_splitter_provider.get_text_splitter(active_splitter_id)
            vector_store_manager.index_text(collection_name, world_bible, text_splitter, metadata={"source": "world_bible"})
        st.success("核心记忆已更新！")

# --- 步骤 1: 规划 ---
with st.container(border=True):
    st.header("第一步：规划 (Planning)")
    user_prompt = st.text_area("请输入您的整体写作需求：", key="user_prompt", height=100)

    if st.button("生成写作计划", type="primary"):
        # ... (Ollama预检逻辑保持不变)
        with st.spinner(f"正在调用“规划师”..."):
            planner_chain = create_planner_chain()
            st.session_state.plan = planner_chain.invoke({"user_prompt": user_prompt})
            st.success("写作计划生成完毕！")

if 'plan' in st.session_state and st.session_state.plan:
    with st.container(border=True):
        st.subheader("生成的写作计划")
        st.markdown(st.session_state.plan)

    # --- 步骤 2: 研究 ---
    with st.container(border=True):
        st.header("第二步：研究 (Research)")
        # ... (UI和逻辑保持不变, 选择工具并执行)
        user_tools = tool_provider.get_user_tools_config()
        available_tool_ids = list(user_tools.keys())
        selected_tool_id = st.selectbox("选择搜索工具:", options=available_tool_ids)
        if st.button("开始研究", type="primary"):
            with st.spinner(f"正在使用工具 '{selected_tool_id}' 进行研究..."):
                search_tool = tool_provider.get_tool(selected_tool_id)
                research_chain = create_research_chain(search_tool=search_tool)
                research_input = {"plan": st.session_state.plan, "user_prompt": user_prompt}
                st.session_state.research_results = research_chain.invoke(research_input)
                st.success("研究完成！")


if 'research_results' in st.session_state and st.session_state.research_results:
    with st.container(border=True):
        st.subheader("研究摘要")
        st.markdown(st.session_state.research_results)

    # --- 步骤 3: 大纲 ---
    with st.container(border=True):
        st.header("第三步：大纲 (Outlining)")
        if st.button("生成大纲", type="primary"):
            # ... (Ollama预检逻辑保持不变)
            with st.spinner(f"正在调用“大纲师”..."):
                outliner_chain = create_outliner_chain()
                outliner_input = {"plan": st.session_state.plan, "user_prompt": user_prompt, "research_results": st.session_state.research_results}
                st.session_state.outline = outliner_chain.invoke(outliner_input)
                st.success("大纲生成完毕！")

if 'outline' in st.session_state and st.session_state.outline:
    with st.container(border=True):
        st.subheader("生成的文章大纲")
        st.markdown(st.session_state.outline)

    # --- 步骤 4: 撰写 (RAG增强) ---
    with st.container(border=True):
        st.header("第四步：撰写 (RAG增强)")
        if "drafting_index" not in st.session_state: st.session_state.drafting_index = 0
        if "drafts" not in st.session_state: st.session_state.drafts = []
            
        if st.button("准备撰写 (解析大纲)", key="parse_outline"):
            sections = [s.strip() for s in st.session_state.outline.split('\n- ') if s.strip()]
            st.session_state.outline_sections = sections
            st.session_state.drafts = []
            st.session_state.drafting_index = 0
            st.success(f"大纲解析完毕，共 {len(sections)} 个章节。")

        if 'outline_sections' in st.session_state and st.session_state.outline_sections:
            total_sections = len(st.session_state.outline_sections)
            current_index = st.session_state.drafting_index

            if current_index < total_sections:
                section_to_write = st.session_state.outline_sections[current_index]
                st.info(f"下一章节待撰写: {section_to_write.splitlines()[0]}")
                if st.button(f"撰写章节 {current_index + 1}/{total_sections}", type="primary"):
                    with st.spinner("正在检索记忆并调用“写手”..."):
                        drafter_chain = create_drafter_chain(collection_name)
                        drafter_input = {
                            "user_prompt": user_prompt, "research_results": st.session_state.research_results,
                            "outline": st.session_state.outline, "section_to_write": section_to_write
                        }
                        draft_content = drafter_chain.invoke(drafter_input)
                        st.session_state.drafts.append(draft_content)
                        st.session_state.drafting_index += 1
                        # 将新写好的章节也加入记忆库
                        with st.spinner("正在将新章节存入记忆库..."):
                            active_splitter_id = st.session_state.get('active_text_splitter', 'default_recursive')
                            text_splitter = text_splitter_provider.get_text_splitter(active_splitter_id)
                            vector_store_manager.index_text(collection_name, draft_content, text_splitter, metadata={"source": f"chapter_{current_index + 1}"})
                        st.rerun()
            else:
                st.success("所有章节已撰写完毕！初稿完成。")

        if st.session_state.drafts:
            with st.expander("完整初稿 (持续更新中)", expanded=False):
                full_draft = "\n\n".join(st.session_state.drafts)
                st.markdown(full_draft)


if st.session_state.get("drafting_index", 0) > 0 and st.session_state.drafting_index == len(st.session_state.get("outline_sections", [])):
    # --- 步骤 5: 修订 (RAG增强) ---
    with st.container(border=True):
        st.header("第五步：修订 (RAG增强)")
        if st.button("开始修订全文", type="primary"):
            with st.spinner("“总编辑”正在检索记忆并审阅全文..."):
                reviser_chain = create_reviser_chain(collection_name)
                full_draft = "\n\n".join(st.session_state.drafts)
                reviser_input = {"plan": st.session_state.plan, "outline": st.session_state.outline, "full_draft": full_draft}
                st.session_state.final_manuscript = reviser_chain.invoke(reviser_input)
                st.success("全文修订完成！")

if 'final_manuscript' in st.session_state and st.session_state.final_manuscript:
    with st.container(border=True):
        st.header("🎉 最终成品")
        st.markdown(st.session_state.final_manuscript)
        st.download_button("下载最终稿件 (Markdown)", st.session_state.final_manuscript, file_name=f"{collection_name}_final.md")
