import streamlit as st
import os
import re
from config import load_environment
import config_manager
import tool_provider
import text_splitter_provider
import vector_store_manager
import workflow_manager
from tools import check_ollama_model_availability

# --- 在应用的最开始加载环境变量 ---
load_environment()

# --- 页面配置 ---
st.set_page_config(page_title="AI 长篇写作智能体", page_icon="📚", layout="wide")

# --- Helper Functions ---
def sanitize_project_name(name: str) -> str:
    """将项目名称转换为安全的ChromaDB集合名称。"""
    name = re.sub(r'[^\w-]', '_', name)
    name = re.sub(r'__+', '_', name)
    name = name.strip('_')
    if len(name) < 3: name = f"proj_{name}"
    return name.lower()

def reset_project_state():
    """重置与特定项目内容相关的会话状态。"""
    keys_to_reset = [
        'world_bible', 'plan', 'research_results', 'outline', 'drafts', 
        'drafting_index', 'final_manuscript', 'outline_sections',
        'project_writing_style_id', 'project_writing_style_description' # 添加写作风格相关的key
    ]
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]

def run_step_with_spinner(step_name: str, spinner_text: str, full_config: dict):
    """带spinner的运行步骤的通用函数，返回结果。"""
    # 从 st.session_state 获取项目专属的写作风格描述
    project_writing_style_description = st.session_state.get('project_writing_style_description', '')

    with st.spinner(spinner_text):
        try:
            result = workflow_manager.run_step(step_name, st.session_state, full_config, project_writing_style_description)
            st.success(f"步骤 '{step_name}' 已完成！")
            return result
        except Exception as e:
            st.error(f"执行步骤 '{step_name}' 时发生错误: {e}")
            print(f"详细错误: {e}")
            return None

# ==================================================================
# --- App 启动入口 ---
# ==================================================================
if __name__ == "__main__":
    
    # 加载合并后的配置，使其在整个脚本范围内可用
    full_config = config_manager.load_config()

    # --- 侧边栏 UI ---
    with st.sidebar:
        st.title("📚 AI 长篇写作智能体")
        
        # --- 项目管理 ---
        st.header("📝 写作项目管理")
        existing_projects = vector_store_manager.list_all_collections()
        project_selection_options = ["--- 选择一个项目 ---"] + existing_projects + ["--- 创建新项目 ---"]
        
        selected_project_index = 0
        if 'collection_name' in st.session_state and st.session_state['collection_name'] in existing_projects:
            selected_project_index = existing_projects.index(st.session_state['collection_name']) + 1

        selected_option = st.selectbox("项目列表", options=project_selection_options, index=selected_project_index, key="project_selector")

        if selected_option == "--- 创建新项目 ---":
            project_name_input = st.text_input("输入新项目名称", key="project_name_input_new")
            if st.button("创建并加载", key="create_and_load_project"):
                if project_name_input:
                    collection_name = sanitize_project_name(project_name_input)
                    if collection_name in existing_projects:
                        st.error(f"项目 '{project_name_input}' 已存在！")
                    else:
                        st.session_state.project_name = project_name_input
                        st.session_state.collection_name = collection_name
                        reset_project_state()
                        with st.spinner(f"正在为新项目 '{project_name_input}' 创建记忆库..."):
                            vector_store_manager.get_or_create_collection(collection_name)
                        st.success(f"项目 '{project_name_input}' 已创建并加载！")
                        st.rerun()
                else:
                    st.error("请输入项目名称！")
        elif selected_option != "--- 选择一个项目 ---" and st.session_state.get('collection_name') != selected_option:
            st.session_state.collection_name = selected_option
            st.session_state.project_name = selected_option
            reset_project_state()
            st.rerun()
        
        st.markdown("---")
        # ... (其他配置UI保持不变，此处省略以保持简洁) ...

    # --- 主界面 UI ---
    if 'project_name' not in st.session_state:
        st.info("👈 请在左侧边栏创建或加载一个写作项目以开始。" )
        st.stop()

    st.title(f"项目: {st.session_state.project_name}")
    
    tab1, tab2, tab3 = st.tabs(["主写作流程", "记忆库浏览器", "系统配置"])

    with tab1:
        # --- RENDER MAIN WRITER VIEW ---
        collection_name = st.session_state.collection_name
        vector_store_manager.get_or_create_collection(collection_name) # 确保集合存在

        # 获取所有写作风格（作为全局库）
        global_writing_styles_library = full_config.get("writing_styles", {})
        style_options = ["无 (默认)"] + list(global_writing_styles_library.keys())

        # 初始化项目写作风格（如果不存在）
        if 'project_writing_style_id' not in st.session_state:
            st.session_state.project_writing_style_id = "无 (默认)"
            st.session_state.project_writing_style_description = ""

        with st.expander("📝 项目写作风格", expanded=True):
            selected_project_style_id = st.selectbox(
                "为当前项目选择写作风格:",
                options=style_options,
                index=style_options.index(st.session_state.project_writing_style_id) if st.session_state.project_writing_style_id in style_options else 0,
                key="project_writing_style_selector"
            )
            
            if selected_project_style_id != st.session_state.project_writing_style_id:
                st.session_state.project_writing_style_id = selected_project_style_id
                if selected_project_style_id == "无 (默认)":
                    st.session_state.project_writing_style_description = ""
                else:
                    st.session_state.project_writing_style_description = global_writing_styles_library.get(selected_project_style_id, "")
                st.info(f"项目写作风格已设置为: {st.session_state.project_writing_style_id}")
                st.rerun() # 重新运行以更新依赖风格的组件

            if st.session_state.project_writing_style_description:
                st.markdown(f"**风格描述:** *{st.session_state.project_writing_style_description}*")
            else:
                st.info("当前未选择特定写作风格，LLM将采用其默认风格。")


        with st.container(border=True):
            st.subheader("🧠 核心记忆 (世界观)")
            st.text_area("在此输入项目的核心设定...", key="world_bible", height=200)
            if st.button("更新核心记忆"):
                with st.spinner("正在将核心记忆存入向量数据库..."):
                    # active_splitter_id 应该在项目级别配置，暂时硬编码
                    text_splitter = text_splitter_provider.get_text_splitter('default_recursive')
                    vector_store_manager.index_text(collection_name, st.session_state.world_bible, text_splitter, metadata={"source": "world_bible"})
                st.success("核心记忆已更新！")

        with st.container(border=True):
            st.subheader("第一步：规划")
            st.text_area("请输入您的整体写作需求：", key="user_prompt", height=100)
            if st.button("生成写作计划", type="primary"):
                result = run_step_with_spinner("plan", "正在调用“规划师”...", full_config)
                if result: st.session_state.update(result)

        if 'plan' in st.session_state:
            st.expander("写作计划").markdown(st.session_state.plan)
            with st.container(border=True):
                st.subheader("第二步：研究")
                user_tools = tool_provider.get_user_tools_config()
                st.selectbox("选择搜索工具:", options=list(user_tools.keys()), key="selected_tool_id")
                if st.button("开始研究", type="primary"):
                    result = run_step_with_spinner("research", f"正在使用工具 '{st.session_state.selected_tool_id}' 进行研究...", full_config)
                    if result: st.session_state.update(result)

        if 'research_results' in st.session_state:
            st.expander("研究摘要").markdown(st.session_state.research_results)
            with st.container(border=True):
                st.subheader("第三步：大纲")
                if st.button("生成大纲", type="primary"):
                    result = run_step_with_spinner("outline", "正在调用“大纲师”...", full_config)
                    if result: st.session_state.update(result)

        if 'outline' in st.session_state:
            st.expander("文章大纲").markdown(st.session_state.outline)
            with st.container(border=True):
                st.subheader("第四步：撰写 (RAG增强)")
                if st.button("准备撰写 (解析大纲)"):
                    st.session_state.outline_sections = [s.strip() for s in st.session_state.outline.split('\n- ') if s.strip()]
                    st.session_state.drafts = []
                    st.session_state.drafting_index = 0
                
                if 'outline_sections' in st.session_state:
                    total = len(st.session_state.outline_sections)
                    current = st.session_state.get('drafting_index', 0)
                    if current < total:
                        st.info(f"下一章节待撰写: {st.session_state.outline_sections[current].splitlines()[0]}")
                        if st.button(f"撰写章节 {current + 1}/{total}", type="primary"):
                            st.session_state.section_to_write = st.session_state.outline_sections[current]
                            result = run_step_with_spinner("draft", "正在检索记忆并调用“写手”...", full_config)
                            if result and "new_draft_content" in result:
                                drafts = st.session_state.get('drafts', [])
                                drafts.append(result["new_draft_content"])
                                st.session_state.drafts = drafts
                                st.session_state.drafting_index += 1
                                st.rerun()
                    else:
                        st.success("所有章节已撰写完毕！")

                if st.session_state.get('drafts'):
                    st.expander("完整初稿").markdown("\n\n".join(st.session_state.drafts))

        if st.session_state.get("drafting_index", 0) > 0 and st.session_state.get("drafting_index") == len(st.session_state.get("outline_sections", [])):
            with st.container(border=True):
                st.subheader("第五步：修订 (RAG增强)")
                if st.button("开始修订全文", type="primary"):
                    st.session_state.full_draft = "\n\n".join(st.session_state.drafts)
                    result = run_step_with_spinner("revise", "“总编辑”正在检索记忆并审阅全文...", full_config)
                    if result: st.session_state.update(result)

        if 'final_manuscript' in st.session_state:
            with st.container(border=True):
                st.header("🎉 最终成品")
                st.markdown(st.session_state.final_manuscript)
                st.download_button("下载最终稿件", st.session_state.final_manuscript, file_name=f"{st.session_state.collection_name}_final.md")


    with tab2:
        # --- RENDER VECTOR STORE EXPLORER ---
        st.header("记忆库浏览器")
        collection_name_for_explorer = st.session_state.collection_name
        st.info(f"当前查看的项目记忆库: **{collection_name_for_explorer}**")
        
        with st.spinner("正在从向量数据库加载记忆..."):
            data = vector_store_manager.get_collection_data(collection_name_for_explorer)
        
        if not data or not data['ids']:
            st.warning("当前记忆库为空。")
        else:
            import pandas as pd
            df = pd.DataFrame({
                "ID": data["ids"],
                "内容": [doc[:100] + '...' if len(doc) > 100 else doc for doc in data["documents"]],
                "元数据": data["metadatas"]
            })
            
            st.info("通过勾选行来选择要删除的记忆条目。")
            edited_df = st.data_editor(df, key=f"df_editor_{collection_name_for_explorer}", num_rows="dynamic", column_config={"ID": st.column_config.Column(disabled=True)})
            
            deleted_ids = list(set(df["ID"]) - set(edited_df["ID"]))
            if deleted_ids:
                if st.button("确认删除选中的记忆", type="primary"):
                    with st.spinner(f"正在删除 {len(deleted_ids)} 条记忆..."):
                        vector_store_manager.delete_documents(collection_name_for_explorer, deleted_ids)
                    st.success("删除成功！")
                    st.rerun()

    with tab3:
        st.header("系统配置")
        
        # 加载所有模型模板
        all_model_templates = config_manager.get_all_model_templates()
        template_names = list(all_model_templates.keys())

        # 获取当前模型配置
        current_models_config = full_config.get("models", {})

        st.subheader("现有模型配置")
        if current_models_config:
            # 识别哪些是用户自定义模型
            user_config_models = config_manager.load_user_config().get("models", {})
            user_defined_model_ids = list(user_config_models.keys())

            st.write("以下是所有可用模型 (包括默认和您自定义的)。您可以删除自定义模型。")
            
            # 使用 st.columns 来显示每个模型及其删除按钮
            # 增加一个列来放置“删除”按钮
            cols = st.columns([1, 1.5, 2, 1.5, 1.5, 0.5]) # 模型ID | 模板 | 模型参数 | API Key Env | Base URL Env | 删除
            cols[0].write("**模型ID**")
            cols[1].write("**模板**")
            cols[2].write("**模型参数 (model/model_name)**")
            cols[3].write("**API Key Env**")
            cols[4].write("**Base URL Env**")
            cols[5].write("") # 删除列的标题留空

            # 对模型ID进行排序，以便用户界面更稳定
            sorted_model_ids = sorted(current_models_config.keys())

            for model_id in sorted_model_ids:
                details = current_models_config[model_id]
                # 每行重新创建列布局以避免Streamlit key冲突
                col_display = st.columns([1, 1.5, 2, 1.5, 1.5, 0.5]) 

                model_name_display = details.get("model_name") or details.get("model", "N/A")
                api_key_env_display = details.get("api_key_env", "N/A")
                base_url_env_display = details.get("base_url_env", "N/A")

                col_display[0].write(model_id)
                col_display[1].write(details.get("template", "N/A"))
                col_display[2].write(model_name_display)
                col_display[3].write(api_key_env_display)
                col_display[4].write(base_url_env_display)

                if model_id in user_defined_model_ids:
                    if col_display[5].button("删除", key=f"delete_model_{model_id}"):
                        try:
                            user_config = config_manager.load_user_config()
                            if "models" in user_config and model_id in user_config["models"]:
                                del user_config["models"][model_id]
                            
                            # 同时检查并移除步骤分配中对该模型的引用
                            if "steps" in user_config:
                                for step, assigned_model in user_config["steps"].items():
                                    if assigned_model == model_id:
                                        del user_config["steps"][step] # 移除分配，UI会提示重新分配
                            
                            config_manager.save_user_config(user_config)
                            st.success(f"模型 '{model_id}' 已成功删除！")
                            st.rerun()
                        except Exception as e:
                            st.error(f"删除模型失败: {e}")
                else:
                    col_display[5].write("") # 占位符，保持对齐
        else:
            st.info("未找到任何模型配置。")

        st.subheader("添加新模型")
        with st.form("add_new_model_form", clear_on_submit=True):
            new_model_id = st.text_input("新模型ID (例如: my_custom_gpt4)", key="new_model_id_input")
            
            # 动态设置默认选择的模板索引，优先选择包含 base_url_env 的模板
            default_template_index = 0
            if "openai_compatible" in template_names:
                default_template_index = template_names.index("openai_compatible")
            elif "ollama" in template_names:
                default_template_index = template_names.index("ollama")

            selected_template_name = st.selectbox("选择模板", 
                                                options=template_names, 
                                                index=default_template_index,
                                                key="selected_template_name_select")

            new_model_config = {}
            if selected_template_name:
                template_details = all_model_templates.get(selected_template_name, {})
                template_params = template_details.get("params", {})
                new_model_config["template"] = selected_template_name

                # 根据模板参数动态显示输入字段
                for param_name, param_type in template_params.items():
                    if param_name == "model_name" or param_name == "model": # 兼容两种命名
                        model_name_key = "new_model_name_input"
                        if "model_name" in new_model_config: # 避免重复
                            model_name_key = "new_model_model_input"
                        input_value = st.text_input(f"{param_name} (例如: gpt-4o 或 llama3)", key=model_name_key)
                        if input_value:
                            new_model_config[param_name] = input_value
                    elif param_type == "secret_env":
                        api_key_env_value = st.text_input(f"{param_name} (例如: OPENAI_API_KEY)", key=f"new_model_{param_name}_input")
                        if api_key_env_value:
                            new_model_config[param_name] = api_key_env_value
                    elif param_type == "url_env":
                        base_url_env_value = st.text_input(f"{param_name} (例如: http://localhost:11434)", key=f"new_model_{param_name}_input")
                        if base_url_env_value:
                            new_model_config[param_name] = base_url_env_value
                    # 其他可能的参数类型可以在这里添加
            
            
            submitted = st.form_submit_button("添加模型")
            if submitted:
                if not new_model_id:
                    st.error("模型ID不能为空！")
                elif new_model_id in current_models_config:
                    st.error(f"模型ID '{new_model_id}' 已存在，请选择其他ID。")
                elif not new_model_config.get("model_name") and not new_model_config.get("model"): # 确保模型参数至少有一个
                    st.error("模型名称/模型参数不能为空！")
                else:
                    try:
                        user_config = config_manager.load_user_config()
                        if "models" not in user_config:
                            user_config["models"] = {}
                        user_config["models"][new_model_id] = new_model_config
                        config_manager.save_user_config(user_config)
                        st.success(f"模型 '{new_model_id}' 已成功添加！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存模型失败: {e}")

        st.markdown("---")
        st.subheader("步骤模型分配")

        # 获取所有可用的模型ID，用于下拉选择
        available_model_ids = list(current_models_config.keys())
        # 获取当前步骤分配
        current_steps_config = full_config.get("steps", {})

        if available_model_ids:
            with st.form("step_assignment_form"):
                new_step_assignments = {}
                for step_name, assigned_model_id in current_steps_config.items():
                    # 查找当前分配模型在可用模型列表中的索引
                    default_index = 0
                    try:
                        default_index = available_model_ids.index(assigned_model_id)
                    except ValueError:
                        # 如果当前分配的模型ID不在可用列表中，则设为默认第一个或一个占位符
                        st.warning(f"步骤 '{step_name}' 当前分配的模型 '{assigned_model_id}' 不可用。请重新分配。")
                        default_index = 0 # 默认选择第一个可用模型

                    selected_model = st.selectbox(
                        f"为 '{step_name}' 分配模型",
                        options=available_model_ids,
                        index=default_index,
                        key=f"step_assign_{step_name}"
                    )
                    new_step_assignments[step_name] = selected_model
                
                submitted_steps = st.form_submit_button("保存步骤分配")
                if submitted_steps:
                    try:
                        user_config = config_manager.load_user_config()
                        if "steps" not in user_config:
                            user_config["steps"] = {}
                        user_config["steps"].update(new_step_assignments)
                        config_manager.save_user_config(user_config)
                        st.success("步骤模型分配已成功保存！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存步骤分配失败: {e}")
        else:
            st.info("没有可用的模型，无法分配步骤。请先添加模型。")

        st.markdown("---")
        st.subheader("嵌入模型配置")

        # 获取所有嵌入模型模板
        all_embedding_templates = config_manager.get_all_embedding_templates()
        embedding_template_names = list(all_embedding_templates.keys())
        
        # 加载所有嵌入模型配置
        current_embeddings_config = full_config.get("embeddings", {})
        active_embedding_model_id = full_config.get("active_embedding_model")

        if current_embeddings_config:
            user_config_embeddings = config_manager.load_user_config().get("embeddings", {})
            user_defined_embedding_ids = list(user_config_embeddings.keys())

            st.write("以下是所有可用嵌入模型 (包括默认和您自定义的)。您可以删除自定义模型。")

            cols_embed = st.columns([1, 1.5, 2, 1.5, 1.5, 0.5])
            cols_embed[0].write("**模型ID**")
            cols_embed[1].write("**模板**")
            cols_embed[2].write("**模型参数 (model/model_name)**")
            cols_embed[3].write("**API Key Env**")
            cols_embed[4].write("**Base URL Env**")
            cols_embed[5].write("") # 删除列的标题留空

            sorted_embedding_ids = sorted(current_embeddings_config.keys())

            for embed_id in sorted_embedding_ids:
                details = current_embeddings_config[embed_id]
                col_embed_display = st.columns([1, 1.5, 2, 1.5, 1.5, 0.5])

                model_name_display = details.get("model_name") or details.get("model", "N/A")
                api_key_env_display = details.get("api_key_env", "N/A")
                base_url_env_display = details.get("base_url_env", "N/A")
                
                # 突出显示当前活跃的模型
                display_id = f"**{embed_id} (活跃)**" if embed_id == active_embedding_model_id else embed_id

                col_embed_display[0].write(display_id)
                col_embed_display[1].write(details.get("template", "N/A"))
                col_embed_display[2].write(model_name_display)
                col_embed_display[3].write(api_key_env_display)
                col_embed_display[4].write(base_url_env_display)

                if embed_id in user_defined_embedding_ids:
                    if col_embed_display[5].button("删除", key=f"delete_embed_model_{embed_id}"):
                        try:
                            user_config = config_manager.load_user_config()
                            if "embeddings" in user_config and embed_id in user_config["embeddings"]:
                                del user_config["embeddings"][embed_id]
                            
                            # 如果删除的是活跃模型，则重置活跃模型ID
                            if user_config.get("active_embedding_model") == embed_id:
                                del user_config["active_embedding_model"] # 待用户重新选择
                            
                            config_manager.save_user_config(user_config)
                            st.success(f"嵌入模型 '{embed_id}' 已成功删除！")
                            st.rerun()
                        except Exception as e:
                            st.error(f"删除嵌入模型失败: {e}")
                else:
                    col_embed_display[5].write("") # 占位符
        else:
            st.info("未找到任何嵌入模型配置。")

        st.subheader("添加新嵌入模型")
        with st.form("add_new_embedding_model_form", clear_on_submit=True):
            new_embed_id = st.text_input("新嵌入模型ID (例如: my_custom_embed)", key="new_embed_id_input")
            
            default_embed_template_index = 0
            if "openai" in embedding_template_names:
                default_embed_template_index = embedding_template_names.index("openai")
            elif "ollama" in embedding_template_names:
                default_embed_template_index = embedding_template_names.index("ollama")

            selected_embed_template_name = st.selectbox("选择模板", 
                                                    options=embedding_template_names, 
                                                    index=default_embed_template_index,
                                                    key="selected_embed_template_name_select")

            new_embedding_config = {}
            if selected_embed_template_name:
                template_details = all_embedding_templates.get(selected_embed_template_name, {})
                template_params = template_details.get("params", {})
                new_embedding_config["template"] = selected_embed_template_name

                for param_name, param_type in template_params.items():
                    if param_name == "model_name" or param_name == "model":
                        input_value = st.text_input(f"{param_name} (例如: text-embedding-3-small)", key=f"new_embed_param_{param_name}")
                        if input_value:
                            new_embedding_config[param_name] = input_value
                    elif param_type == "secret_env":
                        input_value = st.text_input(f"{param_name} (例如: OPENAI_API_KEY)", key=f"new_embed_param_{param_name}")
                        if input_value:
                            new_embedding_config[param_name] = input_value
                    elif param_type == "url_env":
                        input_value = st.text_input(f"{param_name} (例如: http://localhost:11434)", key=f"new_embed_param_{param_name}")
                        if input_value:
                            new_embedding_config[param_name] = input_value
            
            submitted_embed = st.form_submit_button("添加嵌入模型")
            if submitted_embed:
                if not new_embed_id:
                    st.error("嵌入模型ID不能为空！")
                elif new_embed_id in current_embeddings_config:
                    st.error(f"嵌入模型ID '{new_embed_id}' 已存在，请选择其他ID。")
                elif not new_embedding_config.get("model_name") and not new_embedding_config.get("model"):
                    st.error("嵌入模型名称/模型参数不能为空！")
                else:
                    try:
                        user_config = config_manager.load_user_config()
                        if "embeddings" not in user_config:
                            user_config["embeddings"] = {}
                        user_config["embeddings"][new_embed_id] = new_embedding_config
                        config_manager.save_user_config(user_config)
                        st.success(f"嵌入模型 '{new_embed_id}' 已成功添加！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存嵌入模型失败: {e}")
        
        st.markdown("---")
        st.subheader("选择当前活跃的嵌入模型")

        # 获取所有可用的嵌入模型ID
        available_embedding_ids = list(current_embeddings_config.keys())
        current_active_embed_id = full_config.get("active_embedding_model")

        if available_embedding_ids:
            with st.form("active_embedding_selection_form"):
                default_active_index = 0
                if current_active_embed_id and current_active_embed_id in available_embedding_ids:
                    default_active_index = available_embedding_ids.index(current_active_embed_id)
                elif "local_bge_embedding" in available_embedding_ids: # 尝试默认选择一个常用模型
                    default_active_index = available_embedding_ids.index("local_bge_embedding")
                
                selected_active_embed_id = st.selectbox(
                    "选择活跃的嵌入模型:",
                    options=available_embedding_ids,
                    index=default_active_index,
                    key="active_embedding_selector"
                )
                
                submitted_active_embed = st.form_submit_button("保存活跃嵌入模型")
                if submitted_active_embed:
                    try:
                        user_config = config_manager.load_user_config()
                        user_config["active_embedding_model"] = selected_active_embed_id
                        config_manager.save_user_config(user_config)
                        st.success(f"活跃嵌入模型已设置为 '{selected_active_embed_id}'！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存活跃嵌入模型失败: {e}")
        else:
            st.info("没有可用的嵌入模型可选。请先添加嵌入模型。")
        
        st.markdown("---")
        st.subheader("写作风格库管理") # 仅管理库，不选择活跃风格

        # 获取所有写作风格
        current_writing_styles = full_config.get("writing_styles", {})

        if current_writing_styles:
            user_config_styles = config_manager.load_user_config().get("writing_styles", {})
            user_defined_style_ids = list(user_config_styles.keys())

            st.write("以下是所有可用写作风格 (包括默认和您自定义的)。您可以删除自定义风格。")

            cols_style = st.columns([1, 4, 0.5]) # 风格ID | 描述 | 删除
            cols_style[0].write("**风格ID**")
            cols_style[1].write("**描述**")
            cols_style[2].write("") # 删除列的标题留空

            sorted_style_ids = sorted(current_writing_styles.keys())

            for style_id in sorted_style_ids:
                description = current_writing_styles[style_id]
                col_style_display = st.columns([1, 4, 0.5])

                col_style_display[0].write(style_id)
                col_style_display[1].write(description)

                if style_id in user_defined_style_ids:
                    if col_style_display[2].button("删除", key=f"delete_style_{style_id}"):
                        try:
                            user_config = config_manager.load_user_config()
                            if "writing_styles" in user_config and style_id in user_config["writing_styles"]:
                                del user_config["writing_styles"][style_id]
                            
                            config_manager.save_user_config(user_config)
                            st.success(f"写作风格 '{style_id}' 已成功删除！")
                            st.rerun()
                        except Exception as e:
                            st.error(f"删除写作风格失败: {e}")
                else:
                    col_style_display[2].write("") # 占位符
        else:
            st.info("未找到任何写作风格。")
        
        st.subheader("添加新写作风格到库中")
        with st.form("add_new_writing_style_form", clear_on_submit=True):
            new_style_id = st.text_input("新风格ID (例如: news_report)", key="new_style_id_input")
            new_style_description = st.text_area("风格描述 (例如: 以客观、简洁、事实为基础的语言撰写)", key="new_style_description_input")
            
            submitted_style = st.form_submit_button("添加风格")
            if submitted_style:
                if not new_style_id:
                    st.error("风格ID不能为空！")
                elif new_style_id in current_writing_styles:
                    st.error(f"风格ID '{new_style_id}' 已存在，请选择其他ID。")
                elif not new_style_description:
                    st.error("风格描述不能为空！")
                else:
                    try:
                        user_config = config_manager.load_user_config()
                        if "writing_styles" not in user_config:
                            user_config["writing_styles"] = {}
                        user_config["writing_styles"][new_style_id] = new_style_description
                        config_manager.save_user_config(user_config)
                        st.success(f"写作风格 '{new_style_id}' 已成功添加！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存风格失败: {e}")