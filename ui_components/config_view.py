import streamlit as st
import config_manager
import re_ranker_provider
import text_splitter_provider

def render_config_view(full_config):
    st.header("系统配置")
    
    # 加载所有模型模板
    all_model_templates = config_manager.get_all_model_templates()
    template_names = list(all_model_templates.keys())

    # 获取当前模型配置
    current_models_config = full_config.get("models", {})

    st.subheader("现有模型配置")
    if current_models_config:
        user_config_models = config_manager.load_user_config().get("models", {})
        user_defined_model_ids = list(user_config_models.keys())

        st.write("以下是所有可用模型 (包括默认和您自定义的)。您可以删除自定义模型。")
        
        cols = st.columns([1, 1.5, 2, 1.5, 1.5, 0.5])
        cols[0].write("**模型ID**")
        cols[1].write("**模板**")
        cols[2].write("**模型参数 (model/model_name)**")
        cols[3].write("**API Key Env**")
        cols[4].write("**Base URL Env**")
        cols[5].write("")

        sorted_model_ids = sorted(current_models_config.keys())

        for model_id in sorted_model_ids:
            details = current_models_config[model_id]
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
                        if "steps" in user_config:
                            for step, assigned_model in user_config["steps"].items():
                                if assigned_model == model_id:
                                    del user_config["steps"][step]
                        config_manager.save_user_config(user_config)
                        st.success(f"模型 '{model_id}' 已成功删除！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"删除模型失败: {e}")
            else:
                col_display[5].write("")
    else:
        st.info("未找到任何模型配置。")

    st.subheader("添加新模型")
    with st.form("add_new_model_form", clear_on_submit=True):
        new_model_id = st.text_input("新模型ID (例如: my_custom_gpt4)", key="new_model_id_input")
        
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

            for param_name, param_type in template_params.items():
                if param_name == "model_name" or param_name == "model":
                    model_name_key = "new_model_name_input"
                    if "model_name" in new_model_config:
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
        
        submitted = st.form_submit_button("添加模型")
        if submitted:
            if not new_model_id:
                st.error("模型ID不能为空！")
            elif new_model_id in current_models_config:
                st.error(f"模型ID '{new_model_id}' 已存在，请选择其他ID。")
            elif not new_model_config.get("model_name") and not new_model_config.get("model"):
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

    available_model_ids = list(current_models_config.keys())
    current_steps_config = full_config.get("steps", {})

    if available_model_ids:
        with st.form("step_assignment_form"):
            new_step_assignments = {}
            for step_name, assigned_model_id in current_steps_config.items():
                default_index = 0
                try:
                    default_index = available_model_ids.index(assigned_model_id)
                except ValueError:
                    st.warning(f"步骤 '{step_name}' 当前分配的模型 '{assigned_model_id}' 不可用。")
                    default_index = 0

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
        st.info("没有可用的模型，无法分配步骤。")

    st.markdown("---")
    st.subheader("嵌入模型配置")

    all_embedding_templates = config_manager.get_all_embedding_templates()
    embedding_template_names = list(all_embedding_templates.keys())
    
    current_embeddings_config = full_config.get("embeddings", {})
    active_embedding_model_id = full_config.get("active_embedding_model")

    if current_embeddings_config:
        user_config_embeddings = config_manager.load_user_config().get("embeddings", {})
        user_defined_embedding_ids = list(user_config_embeddings.keys())

        st.write("以下是所有可用嵌入模型。您可以删除自定义模型。")

        cols_embed = st.columns([1, 1.5, 2, 1.5, 1.5, 0.5])
        cols_embed[0].write("**模型ID**")
        cols_embed[1].write("**模板**")
        cols_embed[2].write("**模型参数 (model/model_name)**")
        cols_embed[3].write("**API Key Env**")
        cols_embed[4].write("**Base URL Env**")
        cols_embed[5].write("")

        sorted_embedding_ids = sorted(current_embeddings_config.keys())

        for embed_id in sorted_embedding_ids:
            details = current_embeddings_config[embed_id]
            col_embed_display = st.columns([1, 1.5, 2, 1.5, 1.5, 0.5])

            model_name_display = details.get("model_name") or details.get("model", "N/A")
            api_key_env_display = details.get("api_key_env", "N/A")
            base_url_env_display = details.get("base_url_env", "N/A")
            
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
                        if user_config.get("active_embedding_model") == embed_id:
                            del user_config["active_embedding_model"]
                        config_manager.save_user_config(user_config)
                        st.success(f"嵌入模型 '{embed_id}' 已成功删除！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"删除嵌入模型失败: {e}")
            else:
                col_embed_display[5].write("")
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
                st.error(f"嵌入模型ID '{new_embed_id}' 已存在。")
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
    st.subheader("选择活跃的嵌入模型")

    available_embedding_ids = list(current_embeddings_config.keys())
    if available_embedding_ids:
        with st.form("active_embedding_selection_form"):
            default_active_index = 0
            if active_embedding_model_id and active_embedding_model_id in available_embedding_ids:
                default_active_index = available_embedding_ids.index(active_embedding_model_id)
            
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

    st.markdown("---")
    st.subheader("写作风格库管理")

    current_writing_styles = full_config.get("writing_styles", {})
    if current_writing_styles:
        user_config_styles = config_manager.load_user_config().get("writing_styles", {})
        user_defined_style_ids = list(user_config_styles.keys())

        st.write("以下是所有可用写作风格。您可以删除自定义风格。")
        cols_style = st.columns([1, 4, 0.5])
        cols_style[0].write("**风格ID**")
        cols_style[1].write("**描述**")
        cols_style[2].write("")

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
    
    st.subheader("添加新写作风格")
    with st.form("add_new_writing_style_form", clear_on_submit=True):
        new_style_id = st.text_input("新风格ID", key="new_style_id_input")
        new_style_description = st.text_area("风格描述", key="new_style_description_input")
        if st.form_submit_button("添加风格"):
            if new_style_id and new_style_description:
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

    st.markdown("---")
    st.subheader("重排器配置")
    all_reranker_templates = re_ranker_provider.get_re_ranker_provider_templates()
    reranker_template_names = list(all_reranker_templates.keys())
    current_rerankers_config = full_config.get("re_rankers", {})
    active_reranker_id = full_config.get("active_re_ranker_id")

    if current_rerankers_config:
        user_config_rerankers = config_manager.load_user_config().get("re_rankers", {})
        user_defined_reranker_ids = list(user_config_rerankers.keys())
        st.write("以下是所有可用重排器。")
        cols_reranker = st.columns([1, 2, 2, 0.5])
        cols_reranker[0].write("**重排器ID**")
        cols_reranker[1].write("**模板**")
        cols_reranker[2].write("**模型名称**")
        
        for reranker_id in sorted(current_rerankers_config.keys()):
            details = current_rerankers_config[reranker_id]
            col_reranker_display = st.columns([1, 2, 2, 0.5])
            display_id = f"**{reranker_id} (活跃)**" if reranker_id == active_reranker_id else reranker_id
            col_reranker_display[0].write(display_id)
            col_reranker_display[1].write(details.get("template", "N/A"))
            col_reranker_display[2].write(details.get("model_name", "N/A"))

            if reranker_id in user_defined_reranker_ids:
                if col_reranker_display[3].button("删除", key=f"delete_reranker_{reranker_id}"):
                    try:
                        user_config = config_manager.load_user_config()
                        if "re_rankers" in user_config and reranker_id in user_config["re_rankers"]:
                            del user_config["re_rankers"][reranker_id]
                        if user_config.get("active_re_ranker_id") == reranker_id:
                            del user_config["active_re_ranker_id"]
                        config_manager.save_user_config(user_config)
                        st.success(f"重排器 '{reranker_id}' 已成功删除！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"删除重排器失败: {e}")

    st.subheader("添加新重排器")
    with st.form("add_new_reranker_form", clear_on_submit=True):
        new_reranker_id = st.text_input("新重排器ID", key="new_reranker_id_input")
        selected_reranker_template_name = st.selectbox("选择模板", options=reranker_template_names, key="selected_reranker_template_name_select")
        new_reranker_config = {"template": selected_reranker_template_name}
        if selected_reranker_template_name:
            template_details = all_reranker_templates.get(selected_reranker_template_name, {})
            for param_name, param_type in template_details.get("params", {}).items():
                val = st.text_input(f"{param_name}", key=f"new_reranker_param_{param_name}")
                if val: new_reranker_config[param_name] = val
        if st.form_submit_button("添加重排器"):
            if new_reranker_id and new_reranker_config.get("model_name"):
                try:
                    user_config = config_manager.load_user_config()
                    if "re_rankers" not in user_config: user_config["re_rankers"] = {}
                    user_config["re_rankers"][new_reranker_id] = new_reranker_config
                    config_manager.save_user_config(user_config)
                    st.success(f"重排器 '{new_reranker_id}' 已成功添加！")
                    st.rerun()
                except Exception as e: st.error(f"保存失败: {e}")

    st.markdown("---")
    st.subheader("RAG检索设置")
    current_rag_config = full_config.get("rag", {})
    with st.form("rag_settings_form"):
        recall_k = st.number_input("初始召回数量 (recall_k)", min_value=1, max_value=100, value=current_rag_config.get("recall_k", 20))
        rerank_k = st.number_input("精排后数量 (rerank_k)", min_value=1, max_value=20, value=current_rag_config.get("rerank_k", 5))
        if st.form_submit_button("保存RAG设置"):
            try:
                user_config = config_manager.load_user_config()
                user_config["rag"] = {"recall_k": recall_k, "rerank_k": rerank_k}
                config_manager.save_user_config(user_config)
                st.success("RAG设置已保存！")
                st.rerun()
            except Exception as e: st.error(f"保存失败: {e}")

    st.markdown("---")
    st.subheader("文本切分器配置")
    user_splitters_config = text_splitter_provider.get_user_splitters_config()
    available_splitter_ids = list(user_splitters_config.keys())
    current_active_splitter_id = full_config.get("active_text_splitter")

    if available_splitter_ids:
        with st.form("active_splitter_selection_form"):
            selected_active_splitter_id = st.selectbox("活跃切分器:", options=available_splitter_ids, index=available_splitter_ids.index(current_active_splitter_id) if current_active_splitter_id in available_splitter_ids else 0)
            if st.form_submit_button("保存活跃切分器"):
                try:
                    user_config = config_manager.load_user_config()
                    user_config["active_text_splitter"] = selected_active_splitter_id
                    config_manager.save_user_config(user_config)
                    st.success("活跃切分器已设置！")
                    st.rerun()
                except Exception as e: st.error(f"保存失败: {e}")
