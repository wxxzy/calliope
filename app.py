import streamlit as st
import os
from config import load_environment
import config_manager
import tool_provider # 导入工具提供者模块
from config_manager import load_provider_templates # 导入 provider_templates 加载函数
from chains import create_planner_chain, create_research_chain, create_outliner_chain, create_drafter_chain, create_reviser_chain
from tools import check_ollama_model_availability

# --- 在应用的最开始加载环境变量 ---
load_environment()

# --- 页面配置 ---
st.set_page_config(
    page_title="AI分步写作智能体",
    page_icon="🤖",
    layout="wide"
)

# --- 侧边栏 ---
with st.sidebar:
    st.title("📝 AI写作智能体")
    
    # --- 动态配置UI ---
    st.header("⚙️ 系统配置")

    # 加载配置和模板 (优化加载逻辑，避免重复读取)
    if 'config_data' not in st.session_state:
        try:
            st.session_state['config_data'] = config_manager.load_config()
        except (FileNotFoundError, ValueError) as e:
            st.error(f"加载模型配置文件失败: {e}")
            st.stop()
    if 'model_templates' not in st.session_state:
        st.session_state['model_templates'] = config_manager.load_provider_templates()
    if 'tool_templates' not in st.session_state:
        st.session_state['tool_templates'] = tool_provider.get_tool_templates() # 从tool_provider获取工具模板
        
    config_data = st.session_state['config_data']
    model_templates = st.session_state['model_templates']
    tool_templates = st.session_state['tool_templates'] # 获取工具模板

    # --- 1. 步骤模型分配 ---
    with st.expander("步骤模型分配", expanded=True):
        steps_config = config_data.get("steps", {})
        available_model_ids = list(config_data.get("models", {}).keys())
        
        new_steps_config = {}
        for step, current_model_id in steps_config.items():
            try:
                current_index = available_model_ids.index(current_model_id) if available_model_ids else 0
            except ValueError:
                current_index = 0 # 如果当前配置的模型ID不在列表中，则默认为第一个
            
            selected_model = st.selectbox(
                label=f"步骤: {step.capitalize()}",
                options=available_model_ids,
                index=current_index,
                key=f"step_{step}" # 为每个selectbox提供唯一的key
            )
            new_steps_config[step] = selected_model

        if st.button("保存步骤分配", key="save_steps"):
            st.session_state['config_data']['steps'] = new_steps_config
            try:
                config_manager.save_config(st.session_state['config_data'])
                st.success("步骤分配已保存！")
                st.balloons()
            except IOError as e:
                st.error(f"保存配置失败: {e}")

    # --- 2. 模型实例管理 ---
    with st.expander("模型实例管理", expanded=False):
        st.subheader("当前模型列表")
        st.json(config_data.get("models", {}))

        with st.form("add_new_model_form"):
            st.subheader("添加新模型")
            
            available_model_templates = list(model_templates.keys())
            
            new_model_id = st.text_input("新模型ID (自定义, e.g., 'my_groq_model')", key="new_model_id_input")
            selected_template_id = st.selectbox("选择提供商模板", options=available_model_templates, key="model_template_select")
            
            param_values = {}
            if selected_template_id:
                template_params = model_templates[selected_template_id].get("params", {})
                for param, param_type in template_params.items():
                    param_values[param] = st.text_input(f"{param} ({param_type})", key=f"model_param_{param}")

            submitted = st.form_submit_button("添加并保存新模型")
            
            if submitted:
                if not new_model_id:
                    st.error("“新模型ID”不能为空！")
                elif new_model_id in config_data.get("models", {}):
                    st.error(f"模型ID '{new_model_id}' 已存在！")
                else:
                    new_model_config = {"template": selected_template_id}
                    new_model_config.update({k: v for k, v in param_values.items() if v})
                    
                    st.session_state['config_data']['models'][new_model_id] = new_model_config
                    try:
                        config_manager.save_config(st.session_state['config_data'])
                        st.session_state['model_templates'] = config_manager.load_provider_templates() # 刷新模板
                        st.success(f"新模型 '{new_model_id}' 已添加！请重新分配步骤模型或刷新页面。")
                    except IOError as e:
                        st.error(f"保存新模型失败: {e}")

    # --- 3. 工具实例管理 ---
    with st.expander("工具实例管理", expanded=False):
        st.subheader("当前工具列表")
        user_tools_config = tool_provider.get_user_tools_config()
        st.json(user_tools_config)

        with st.form("add_new_tool_form"):
            st.subheader("添加新工具")
            
            available_tool_templates = list(tool_templates.keys())

            new_tool_id = st.text_input("新工具ID (e.g., 'my_search')", key="new_tool_id_input")
            selected_tool_template_id = st.selectbox("选择工具模板", options=available_tool_templates, key="tool_template_select")

            tool_params = {}
            if selected_tool_template_id:
                template_params_schema = tool_templates[selected_tool_template_id].get("params", {})
                for param, param_type in template_params_schema.items():
                    tool_params[param] = st.text_input(f"{param} ({param_type})", key=f"tool_param_{param}")
                # 额外添加一个description字段 (所有工具实例都应该有描述)
                tool_params['description'] = st.text_area("工具描述 (可选)", key="tool_description_input")

            tool_submitted = st.form_submit_button("添加并保存新工具")

            if tool_submitted:
                if not new_tool_id:
                    st.error("“新工具ID”不能为空！")
                elif new_tool_id in user_tools_config:
                    st.error(f"工具ID '{new_tool_id}' 已存在！")
                else:
                    new_tool_config = {"template": selected_tool_template_id}
                    new_tool_config.update({k: v for k, v in tool_params.items() if v})

                    user_tools_config[new_tool_id] = new_tool_config
                    try:
                        tool_provider.save_user_tools_config(user_tools_config)
                        st.success(f"新工具 '{new_tool_id}' 已添加！请刷新页面以在研究步骤中选择。")
                    except IOError as e:
                        st.error(f"保存新工具失败: {e}")
    
    st.info(
        """
        您可以在此动态配置系统的行为。
        - **步骤模型分配:** 为每个写作步骤选择使用哪个模型。
        - **模型/工具实例管理:** 添加对新模型或新工具的支持。
        """,
        icon="💡"
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
    user_prompt = st.text_area("请输入您的写作需求：", height=150, placeholder="例如：写一篇关于“人工智能对未来就业市场影响”的博客文章，风格要通俗易懂。", key="user_prompt_input")

    if st.button("生成写作计划", type="primary"):
        if not user_prompt:
            st.error("请输入您的写作需求！")
        else:
            # 预检Ollama模型
            current_config = st.session_state.get('config_data', {})
            planner_model_id = current_config.get("steps", {}).get("planner")
            planner_model_config = current_config.get("models", {}).get(planner_model_id, {})
            
            should_run = True
            if planner_model_config.get("template") == "ollama":
                base_url_env = planner_model_config.get("base_url_env")
                ollama_base_url = os.getenv(base_url_env) if base_url_env else None
                model_name = planner_model_config.get("model") # ollama模板使用'model'

                if not ollama_base_url:
                    st.error(f"错误: 模型 '{planner_model_id}' 需要环境变量 '{base_url_env}'，但它未被设置。")
                    should_run = False
                else:
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
        
        # 允许用户从 user_tools.yaml 中选择搜索工具
        user_tools = tool_provider.get_user_tools_config()
        available_tool_ids = list(user_tools.keys())
        
        selected_tool_id = st.selectbox(
            "选择搜索工具:", 
            options=available_tool_ids,
            help="您可以在侧边栏的“工具实例管理”中添加和配置更多工具。",
            key="research_tool_select"
        )

        if st.button("开始研究", type="primary"):
            # 预检Ollama模型 (研究步骤中的模型也需要检查)
            current_config = st.session_state.get('config_data', {})
            should_run = True
            for step in ["researcher", "summarizer"]:
                model_id = current_config.get("steps", {}).get(step)
                if not model_id: continue # 如果步骤没有分配模型，则跳过

                model_config = current_config.get("models", {}).get(model_id, {})

                if model_config.get("template") == "ollama":
                    base_url_env = model_config.get("base_url_env")
                    ollama_base_url = os.getenv(base_url_env) if base_url_env else None
                    model_name_key = "model" # ollama模板使用'model'
                    model_name = model_config.get(model_name_key)
                    
                    if not ollama_base_url:
                        st.error(f"错误: 模型 '{model_id}' 需要环境变量 '{base_url_env}'，但它未被设置。")
                        should_run = False
                        break

                    with st.spinner(f"正在检查本地Ollama模型 '{model_name}'..."):
                        check_result = check_ollama_model_availability(model_name, ollama_base_url)
                    
                    if not check_result["status"]:
                        st.error(f"'{step}' 步骤配置的模型检查失败: {check_result['message']}")
                        should_run = False
                        break
            
            if should_run:
                with st.spinner(f"正在使用工具 '{selected_tool_id}' 进行研究..."):
                    try:
                        # 1. 从选择的ID动态获取工具实例
                        search_tool = tool_provider.get_tool(selected_tool_id)
                        
                        # 2. 创建研究链，并传入工具实例
                        research_chain = create_research_chain(search_tool=search_tool)

                        # 3. 准备输入并调用链
                        research_input = {
                            "plan": st.session_state.plan,
                            "user_prompt": user_prompt 
                        }
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
            if outliner_model_config.get("template") == "ollama":
                base_url_env = outliner_model_config.get("base_url_env")
                ollama_base_url = os.getenv(base_url_env) if base_url_env else None
                model_name = outliner_model_config.get("model")

                if not ollama_base_url:
                    st.error(f"错误: 模型 '{outliner_model_id}' 需要环境变量 '{base_url_env}'，但它未被设置。")
                    should_run = False
                else:
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
                    if drafter_model_config.get("template") == "ollama":
                        base_url_env = drafter_model_config.get("base_url_env")
                        ollama_base_url = os.getenv(base_url_env) if base_url_env else None
                        model_name = drafter_model_config.get("model")

                        if not ollama_base_url:
                            st.error(f"错误: 模型 '{drafter_model_id}' 需要环境变量 '{base_url_env}'，但它未被设置。")
                            should_run = False
                        else:
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
            if reviser_model_config.get("template") == "ollama":
                base_url_env = reviser_model_config.get("base_url_env")
                ollama_base_url = os.getenv(base_url_env) if base_url_env else None
                model_name = reviser_model_config.get("model")

                if not ollama_base_url:
                    st.error(f"错误: 模型 '{reviser_model_id}' 需要环境变量 '{base_url_env}'，但它未被设置。")
                    should_run = False
                else:
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