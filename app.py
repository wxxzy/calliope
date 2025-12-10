import streamlit as st
from config import load_environment
import config_manager

# 在应用的最开始加载环境变量
load_environment()

from chains import create_planner_chain, create_research_chain, create_outliner_chain, create_drafter_chain, create_reviser_chain
from tools import check_ollama_model_availability
import os
# 更多的链和工具将在这里被导入
# from chains import create_research_chain
# from tools import web_search

# --- 页面配置 ---
st.set_page_config(
    page_title="AI分步写作智能体",
    page_icon="🤖",
    layout="wide"
)

# --- 侧边栏 ---
with st.sidebar:
    st.title("📝 AI写作智能体")
    
    with st.expander("🤖 系统模型配置", expanded=True):
        # 加载当前配置
        try:
            config_data = st.session_state.get('config_data', config_manager.load_config())
            st.session_state['config_data'] = config_data
        except (FileNotFoundError, ValueError) as e:
            st.error(f"加载配置文件失败: {e}")
            st.stop()

        models_config = config_data.get("models", {})
        steps_config = config_data.get("steps", {})
        
        available_model_ids = list(models_config.keys())
        
        # 为每一步创建一个下拉菜单
        new_steps_config = {}
        for step, current_model_id in steps_config.items():
            try:
                # 获取当前模型在列表中的索引
                current_index = available_model_ids.index(current_model_id)
            except ValueError:
                # 如果当前配置的模型ID不在模型列表中，则默认为第一个
                current_index = 0
            
            # 使用st.selectbox让用户选择
            selected_model = st.selectbox(
                label=f"第 {list(steps_config.keys()).index(step) + 1} 步: {step.capitalize()}",
                options=available_model_ids,
                index=current_index,
                key=f"step_{step}" # 为每个selectbox提供唯一的key
            )
            new_steps_config[step] = selected_model

        if st.button("保存配置", type="primary"):
            # 更新配置数据
            st.session_state['config_data']['steps'] = new_steps_config
            
            # 保存到文件
            try:
                config_manager.save_config(st.session_state['config_data'])
                st.success("配置已成功保存！")
                st.balloons()
            except IOError as e:
                st.error(f"保存配置失败: {e}")

    st.info(
        """
        这是一个AI分步写作智能体的原型实现。
        您可以在上面的配置区域动态更改每一步使用的AI模型。
        """
    )


# --- 主界面 ---
st.title("🤖 AI 分步写作智能体")

# --- 初始化Session State ---
# st.session_state 用于在Streamlit应用的多次运行之间保持数据
if "plan" not in st.session_state:
    st.session_state.plan = None
if "research_results" not in st.session_state:
    st.session_state.research_results = None
if "outline" not in st.session_state:
    st.session_state.outline = None
if "final_manuscript" not in st.session_state:
    st.session_state.final_manuscript = None
# ... 后续步骤的状态

# --- 步骤 1: 规划 ---
with st.container(border=True):
    st.header("第一步：规划 (Planning)")
    user_prompt = st.text_area("请输入您的写作需求：", height=150, placeholder="例如：写一篇关于“人工智能对未来就业市场影响”的博客文章，风格要通俗易懂。")

    if st.button("生成写作计划", type="primary"):
        if not user_prompt:
            st.error("请输入您的写作需求！")
        else:
            # 预检Ollama模型
            current_config = st.session_state.get('config_data', {})
            planner_model_id = current_config.get("steps", {}).get("planner")
            planner_model_config = current_config.get("models", {}).get(planner_model_id, {})
            
            should_run = True
            if planner_model_config.get("provider") == "ollama":
                base_url_env = planner_model_config.get("base_url_env")
                ollama_base_url = os.getenv(base_url_env)
                model_name = planner_model_config.get("model_name")
                
                with st.spinner(f"正在检查本地Ollama模型 '{model_name}'..."):
                    check_result = check_ollama_model_availability(model_name, ollama_base_url)
                
                if not check_result["status"]:
                    st.error(check_result["message"])
                    should_run = False
            
            if should_run:
                with st.spinner(f"正在调用“规划师”模型 ({st.session_state.config_data['steps']['planner']})... 请稍候..."):
                    try:
                        # 创建并调用规划链
                        planner_chain = create_planner_chain()
                        st.session_state.plan = planner_chain.invoke({"user_prompt": user_prompt})
                        st.success("写作计划生成完毕！")
                    except Exception as e:
                        st.error(f"生成计划时发生错误: {e}")
                        # 打印更详细的错误信息到控制台，便于调试
                        print(f"详细错误: {e}")

# 如果规划已生成，则显示规划内容和下一步操作
if st.session_state.plan:
    with st.container(border=True):
        st.subheader("生成的写作计划")
        st.markdown(st.session_state.plan)

    # --- 步骤 2: 研究 ---
    with st.container(border=True):
        st.header("第二步：研究 (Research)")
        
        # 允许用户选择搜索引擎
        search_engine = st.radio("选择搜索引擎:", ("tavily", "google"), horizontal=True)

        if st.button("开始研究", type="primary"):
            # 预检Ollama模型
            current_config = st.session_state.get('config_data', {})
            should_run = True
            for step in ["researcher", "summarizer"]:
                model_id = current_config.get("steps", {}).get(step)
                model_config = current_config.get("models", {}).get(model_id, {})

                if model_config.get("provider") == "ollama":
                    base_url_env = model_config.get("base_url_env")
                    ollama_base_url = os.getenv(base_url_env)
                    model_name = model_config.get("model_name")
                    
                    with st.spinner(f"正在检查本地Ollama模型 '{model_name}'..."):
                        check_result = check_ollama_model_availability(model_name, ollama_base_url)
                    
                    if not check_result["status"]:
                        st.error(f"'{step}' 步骤配置的模型检查失败: {check_result['message']}")
                        should_run = False
                        break # 一个失败就停止检查
            
            if should_run:
                with st.spinner(f"正在执行研究（引擎: {search_engine}）... 这可能需要1-2分钟..."):
                    try:
                        # 准备研究链的输入
                        research_input = {
                            "plan": st.session_state.plan,
                            "user_prompt": user_prompt 
                        }
                        # 创建并调用研究链
                        research_chain = create_research_chain(search_engine=search_engine)
                        st.session_state.research_results = research_chain.invoke(research_input)
                        st.success("研究完成！")
                    except Exception as e:
                        st.error(f"研究过程中发生错误: {e}")
                        print(f"详细错误: {e}")

# 如果研究已完成，则显示研究结果和下一步操作
if st.session_state.research_results:
    with st.container(border=True):
        st.subheader("研究摘要")
        st.markdown(st.session_state.research_results)

    # --- 步骤 3: 大纲 ---
    with st.container(border=True):
        st.header("第三步：大纲 (Outlining)")
        if st.button("生成大纲", type="primary"):
            # 预检Ollama模型
            current_config = st.session_state.get('config_data', {})
            outliner_model_id = current_config.get("steps", {}).get("outliner")
            outliner_model_config = current_config.get("models", {}).get(outliner_model_id, {})
            
            should_run = True
            if outliner_model_config.get("provider") == "ollama":
                base_url_env = outliner_model_config.get("base_url_env")
                ollama_base_url = os.getenv(base_url_env)
                model_name = outliner_model_config.get("model_name")
                
                with st.spinner(f"正在检查本地Ollama模型 '{model_name}'..."):
                    check_result = check_ollama_model_availability(model_name, ollama_base_url)
                
                if not check_result["status"]:
                    st.error(check_result["message"])
                    should_run = False

            if should_run:
                with st.spinner(f"正在调用“大纲师”模型 ({st.session_state.config_data['steps']['outliner']}) 生成大纲..."):
                    try:
                        # 准备大纲链的输入
                        outliner_input = {
                            "plan": st.session_state.plan,
                            "user_prompt": user_prompt,
                            "research_results": st.session_state.research_results
                        }
                        # 创建并调用大纲链
                        outliner_chain = create_outliner_chain()
                        st.session_state.outline = outliner_chain.invoke(outliner_input)
                        st.success("大纲生成完毕！")
                    except Exception as e:
                        st.error(f"生成大纲时发生错误: {e}")
                        print(f"详细错误: {e}")

# 如果大纲已生成，则显示大纲内容和下一步操作
if st.session_state.outline:
    with st.container(border=True):
        st.subheader("生成的文章大纲")
        st.markdown(st.session_state.outline)

    # --- 步骤 4: 撰写 ---
    with st.container(border=True):
        st.header("第四步：撰写 (Drafting)")

        # 初始化草稿相关的 session_state
        if "outline_sections" not in st.session_state:
            st.session_state.outline_sections = []
        if "drafts" not in st.session_state:
            st.session_state.drafts = []
        if "drafting_index" not in st.session_state:
            st.session_state.drafting_index = 0

        # 1. 解析大纲
        if st.button("准备撰写 (解析大纲)"):
            with st.spinner("正在解析大纲..."):
                # 一个简单的大纲解析逻辑：按顶级项目符号分割
                # 注意：这个解析器假设大纲是规范的Markdown列表
                sections = [s.strip() for s in st.session_state.outline.split('\n- ') if s.strip()]
                st.session_state.outline_sections = sections
                # 重置之前的草稿
                st.session_state.drafts = []
                st.session_state.drafting_index = 0
                st.success(f"大纲解析完毕，共 {len(sections)} 个章节。")

        # 2. 迭代撰写
        if st.session_state.outline_sections:
            total_sections = len(st.session_state.outline_sections)
            current_index = st.session_state.drafting_index

            if current_index < total_sections:
                st.progress((current_index) / total_sections, text=f"撰写进度: {current_index}/{total_sections}")
                
                section_to_write = st.session_state.outline_sections[current_index]
                st.markdown("**下一章节待撰写:**")
                st.info(section_to_write)

                if st.button(f"撰写章节 {current_index + 1}/{total_sections}", type="primary"):
                    # 预检Ollama模型
                    current_config = st.session_state.get('config_data', {})
                    drafter_model_id = current_config.get("steps", {}).get("drafter")
                    drafter_model_config = current_config.get("models", {}).get(drafter_model_id, {})

                    should_run = True
                    if drafter_model_config.get("provider") == "ollama":
                        base_url_env = drafter_model_config.get("base_url_env")
                        ollama_base_url = os.getenv(base_url_env)
                        model_name = drafter_model_config.get("model_name")
                        
                        with st.spinner(f"正在检查本地Ollama模型 '{model_name}'..."):
                            check_result = check_ollama_model_availability(model_name, ollama_base_url)
                        
                        if not check_result["status"]:
                            st.error(check_result["message"])
                            should_run = False
                    
                    if should_run:
                        with st.spinner(f"正在调用“写手”模型 ({st.session_state.config_data['steps']['drafter']}) 撰写章节 {current_index + 1}..."):
                            try:
                                drafter_input = {
                                    "plan": st.session_state.plan,
                                    "user_prompt": user_prompt,
                                    "research_results": st.session_state.research_results,
                                    "outline": st.session_state.outline,
                                    "section_to_write": section_to_write
                                }
                                drafter_chain = create_drafter_chain()
                                draft_content = drafter_chain.invoke(drafter_input)
                                
                                # 将新生成的草稿内容存入列表
                                st.session_state.drafts.append(draft_content)
                                # 更新索引
                                st.session_state.drafting_index += 1
                                st.rerun() # 重新运行脚本以更新UI
                            except Exception as e:
                                st.error(f"撰写章节时发生错误: {e}")
                                print(f"详细错误: {e}")
            else:
                st.success("所有章节已撰写完毕！初稿完成。")

        # 3. 显示完整草稿
        if st.session_state.drafts:
            with st.container(border=True):
                st.subheader("完整初稿 (持续更新中)")
                full_draft = "\n\n".join(st.session_state.drafts)
                st.markdown(full_draft)

# 如果撰写已完成，显示下一步
if st.session_state.get("drafting_index", 0) > 0 and st.session_state.drafting_index == len(st.session_state.get("outline_sections", [])):
    with st.container(border=True):
        st.header("第五步：修订 (Revision)")
        st.info("这是最后一步。强大的“总编辑”模型将审阅全文，修正逻辑、润色语言，并输出最终稿件。")
        
        if st.button("开始修订全文", type="primary"):
            # 预检Ollama模型
            current_config = st.session_state.get('config_data', {})
            reviser_model_id = current_config.get("steps", {}).get("reviser")
            reviser_model_config = current_config.get("models", {}).get(reviser_model_id, {})

            should_run = True
            if reviser_model_config.get("provider") == "ollama":
                base_url_env = reviser_model_config.get("base_url_env")
                ollama_base_url = os.getenv(base_url_env)
                model_name = reviser_model_config.get("model_name")
                
                with st.spinner(f"正在检查本地Ollama模型 '{model_name}'..."):
                    check_result = check_ollama_model_availability(model_name, ollama_base_url)
                
                if not check_result["status"]:
                    st.error(check_result["message"])
                    should_run = False
            
            if should_run:
                with st.spinner(f"“总编辑” ({st.session_state.config_data['steps']['reviser']}) 正在审阅全文... 这可能需要较长时间，请耐心等待..."):
                    try:
                        # 准备修订链的输入
                        full_draft = "\n\n".join(st.session_state.drafts)
                        reviser_input = {
                            "plan": st.session_state.plan,
                            "outline": st.session_state.outline,
                            "full_draft": full_draft
                        }
                        # 创建并调用修订链
                        reviser_chain = create_reviser_chain()
                        st.session_state.final_manuscript = reviser_chain.invoke(reviser_input)
                        st.success("全文修订完成！")
                    except Exception as e:
                        st.error(f"修订过程中发生错误: {e}")
                        print(f"详细错误: {e}")

# 如果最终稿件已生成，则显示它
if st.session_state.final_manuscript:
    with st.container(border=True):
        st.header("🎉 最终成品")
        st.markdown(st.session_state.final_manuscript)
        
        st.download_button(
            label="下载最终稿件 (Markdown)",
            data=st.session_state.final_manuscript,
            file_name="final_manuscript.md",
            mime="text/markdown"
        )

# --- 如何运行 ---
st.info(
    """
    **如何运行本项目:**
    1. 确保已在 `requirements.txt` 中安装所有依赖 (`pip install -r requirements.txt`)。
    2. 在您的终端中设置API密钥 (例如 `export OPENAI_API_KEY='your_key'`)。
    3. 运行 `streamlit run app.py`。
    """,
    icon="💡"
)
