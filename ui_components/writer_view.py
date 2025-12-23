import streamlit as st
import vector_store_manager
import text_splitter_provider
import tool_provider
import export_manager

def render_writer_view(full_config, run_step_with_spinner_func):
    collection_name = st.session_state.collection_name
    vector_store_manager.get_or_create_collection(collection_name)

    # 获取所有写作风格
    global_writing_styles_library = full_config.get("writing_styles", {})
    style_options = ["无 (默认)"] + list(global_writing_styles_library.keys())

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
            st.session_state.project_writing_style_description = global_writing_styles_library.get(selected_project_style_id, "")
            st.rerun()

        if st.session_state.project_writing_style_description:
            st.markdown(f"**风格描述:** *{st.session_state.project_writing_style_description}*")
        else:
            st.info("采用默认风格。")

    with st.container(border=True):
        st.subheader("🧠 核心记忆 (世界观)")
        st.text_area("在此输入项目的核心设定...", key="world_bible", height=200)
        if st.button("更新核心记忆"):
            with st.spinner("正在存入向量数据库..."):
                text_splitter = text_splitter_provider.get_text_splitter('default_recursive')
                vector_store_manager.index_text(collection_name, st.session_state.world_bible, text_splitter, metadata={"source": "world_bible"})
            st.success("核心记忆已更新！")

    with st.container(border=True):
        st.subheader("第一步：规划")
        st.text_area("请输入您的整体写作需求：", key="user_prompt", height=100)

        if 'plan' not in st.session_state:
            if st.button("生成写作计划", type="primary"):
                result = run_step_with_spinner_func("plan", "正在调用“规划师”...", full_config)
                if result and "plan" in result:
                    st.session_state.new_plan = result["plan"]
                    st.rerun()
        else:
            st.text_area("写作计划", key="plan", height=200)
            st.text_input("优化指令", key="plan_refinement_instruction")
            if st.button("迭代优化计划", type="secondary"):
                st.session_state.refinement_instruction = st.session_state.plan_refinement_instruction
                result = run_step_with_spinner_func("plan", "正在优化...", full_config)
                if result and "plan" in result:
                    st.session_state.new_plan = result["plan"]
                    st.session_state.clear_specific_refinement = "plan_refinement_instruction"
                    st.rerun()

    if 'plan' in st.session_state:
        with st.container(border=True):
            st.subheader("第二步：研究")
            user_tools = tool_provider.get_user_tools_config()
            st.selectbox("选择搜索工具:", options=list(user_tools.keys()), key="selected_tool_id")

            if 'research_results' not in st.session_state:
                if st.button("开始研究", type="primary"):
                    result = run_step_with_spinner_func("research", "进行研究...", full_config)
                    if result and "research_results" in result:
                        st.session_state.new_research_results = result["research_results"]
                        st.rerun()
            else:
                st.text_area("研究摘要", key="research_results", height=200)
                st.text_input("优化指令", key="research_refinement_instruction")
                if st.button("迭代优化摘要", type="secondary"):
                    st.session_state.refinement_instruction = st.session_state.research_refinement_instruction
                    result = run_step_with_spinner_func("research", "优化摘要...", full_config)
                    if result and "research_results" in result:
                        st.session_state.new_research_results = result["research_results"]
                        st.session_state.clear_specific_refinement = "research_refinement_instruction"
                        st.rerun()

        with st.container(border=True):
            st.subheader("第三步：大纲")
            if 'outline' not in st.session_state:
                if st.button("生成大纲", type="primary"):
                    result = run_step_with_spinner_func("outline", "调用“大纲师”...", full_config)
                    if result and "outline" in result:
                        st.session_state.new_outline = result["outline"]
                        st.rerun()
            else:
                st.text_area("文章大纲", key="outline", height=400)
                st.text_input("优化指令", key="outline_refinement_instruction")
                
                if st.session_state.get("auto_run_outline_refinement"):
                    del st.session_state.auto_run_outline_refinement
                    st.session_state.refinement_instruction = st.session_state.outline_refinement_instruction
                    result = run_step_with_spinner_func("outline", "优化大纲...", full_config)
                    if result and "outline" in result:
                        st.session_state.new_outline = result["outline"]
                        st.session_state.clear_specific_refinement = "outline_refinement_instruction"
                        if "current_critique" in st.session_state: del st.session_state.current_critique
                        st.rerun()

                if st.button("迭代优化大纲", type="secondary"):
                    st.session_state.refinement_instruction = st.session_state.outline_refinement_instruction
                    result = run_step_with_spinner_func("outline", "优化大纲...", full_config)
                    if result and "outline" in result:
                        st.session_state.new_outline = result["outline"]
                        st.session_state.clear_specific_refinement = "outline_refinement_instruction"
                        st.rerun()
                
                with st.expander("🧐 AI 评审员反馈", expanded=False):
                    if st.button("🔍 请求 AI 评审 (大纲)", key="critique_outline_btn"):
                        st.session_state.critique_target_type = "outline"
                        result = run_step_with_spinner_func("critique", "审阅大纲...", full_config)
                        if result and "current_critique" in result:
                            st.session_state.current_critique = result["current_critique"]
                            st.rerun()
                    if st.session_state.get("current_critique") and st.session_state.get("critique_target_type") == "outline":
                        st.markdown(st.session_state.current_critique)
                        def adopt_critique_callback():
                            st.session_state.outline_refinement_instruction = f"参考建议：\n{st.session_state.current_critique}"
                            st.session_state.auto_run_outline_refinement = True
                        st.button("🔧 采纳建议", key="refine_outline_with_critique", on_click=adopt_critique_callback)

        with st.container(border=True):
            st.subheader("第四步：撰写 (RAG增强)")
            if 'outline_sections' in st.session_state:
                total_chaps = len(st.session_state.outline_sections)
                done_chaps = st.session_state.get('drafting_index', 0)
                progress = done_chaps / total_chaps if total_chaps > 0 else 0
                p_col1, p_col2 = st.columns([4, 1])
                with p_col1: st.progress(progress, text=f"进度: {done_chaps}/{total_chaps}")
                with p_col2: st.metric("总字数", f"{sum(len(d) for d in st.session_state.get('drafts', [])):,}")

            if st.button("准备撰写 (解析大纲)"):
                st.session_state.outline_sections = [s.strip() for s in st.session_state.outline.split('\n- ') if s.strip()]
                st.session_state.drafts = []
                st.session_state.drafting_index = 0
                keys_to_clear = ['draft_context_review_mode', 'draft_retrieved_docs', 'draft_selected_docs_mask', 'user_selected_docs', 'retrieved_docs', 'current_critique', 'draft_refinement_instruction']
                for key in keys_to_clear:
                    if key in st.session_state: del st.session_state[key]
                st.rerun()

            if st.session_state.get('draft_context_review_mode'):
                st.info("审核记忆片段")
                docs_to_review = st.session_state.get('draft_retrieved_docs', [])
                selected_mask = st.session_state.get('draft_selected_docs_mask', {})
                for i, doc in enumerate(docs_to_review):
                    is_selected = st.checkbox(f"参考片段 {i+1}", value=selected_mask.get(i, False), key=f"draft_doc_{i}")
                    if is_selected: st.markdown(f"> {doc[:200]}...")
                    selected_mask[i] = is_selected
                st.session_state.draft_selected_docs_mask = selected_mask
                if st.button("✅ 生成", type="primary"):
                    st.session_state['user_selected_docs'] = [docs_to_review[i] for i, selected in selected_mask.items() if selected]
                    result = run_step_with_spinner_func("generate_draft", "生成内容...", full_config)
                    if result and "new_draft_content" in result:
                        st.session_state.drafts.append(result["new_draft_content"])
                        st.session_state.drafting_index += 1
                    del st.session_state['draft_context_review_mode']
                    st.rerun()

            elif 'outline_sections' in st.session_state:
                total = len(st.session_state.outline_sections)
                current = st.session_state.get('drafting_index', 0)
                if current < total:
                    st.info(f"待写: **{st.session_state.outline_sections[current].splitlines()[0]}**")
                    if st.button(f"撰写章节 {current + 1}/{total}", type="primary"):
                        st.session_state.section_to_write = st.session_state.outline_sections[current]
                        retrieval_result = run_step_with_spinner_func("retrieve_for_draft", "检索记忆...", full_config)
                        if retrieval_result and "retrieved_docs" in retrieval_result:
                            st.session_state.draft_context_review_mode = True
                            st.session_state.draft_retrieved_docs = retrieval_result['retrieved_docs']
                            st.session_state.draft_selected_docs_mask = {i: True for i in range(len(retrieval_result['retrieved_docs']))}
                            st.rerun()
                else:
                    st.success("全部完成！")

            if st.session_state.get('drafts') and st.session_state.get("drafting_index", 0) > 0:
                idx = len(st.session_state.drafts)
                st.markdown("---")
                st.subheader(f"优化第 {idx} 章")
                st.text_input("本章优化指令", key="draft_refinement_instruction")
                
                def perform_rewrite(instruction):
                    old_content = st.session_state.drafts[-1]
                    st.session_state.current_chapter_draft = old_content
                    st.session_state.refinement_instruction = instruction
                    st.session_state.drafts.pop()
                    st.session_state.drafting_index -= 1
                    result = run_step_with_spinner_func("generate_draft", "重写中...", full_config)
                    if result and "new_draft_content" in result:
                        st.session_state.drafts.append(result["new_draft_content"])
                        st.session_state.drafting_index += 1
                        st.success("重写成功！")
                    else:
                        st.session_state.drafts.append(old_content)
                        st.session_state.drafting_index += 1
                    st.rerun()

                if st.session_state.get("auto_run_draft_refinement"):
                    del st.session_state.auto_run_draft_refinement
                    perform_rewrite(st.session_state.draft_refinement_instruction)

                if st.button(f"重写第 {idx} 章"):
                    perform_rewrite(st.session_state.draft_refinement_instruction)

                with st.expander(f"🧐 第 {idx} 章评审"):
                    if st.button(f"🔍 请求评审 (第 {idx} 章)"):
                        st.session_state.critique_target_type = "draft"
                        result = run_step_with_spinner_func("critique", "审阅章节...", full_config)
                        if result and "current_critique" in result:
                            st.session_state.current_critique = result["current_critique"]
                            st.rerun()
                    if st.session_state.get("current_critique") and st.session_state.get("critique_target_type") == "draft":
                        st.markdown(st.session_state.current_critique)
                        def adopt_draft_critique_callback():
                            st.session_state.draft_refinement_instruction = f"参考建议：\n{st.session_state.current_critique}"
                            st.session_state.auto_run_draft_refinement = True
                        st.button("🔧 采纳并重写", on_click=adopt_draft_critique_callback)

            if st.session_state.get('drafts'):
                with st.expander("📖 查看完整初稿", expanded=False):
                    for i, draft in enumerate(st.session_state.drafts):
                        st.markdown(f"#### 第 {i+1} 章 (字数: {len(draft)})")
                        st.write(draft)
                        st.markdown("---")

    if st.session_state.get("drafting_index", 0) > 0 and st.session_state.get("drafting_index") == len(st.session_state.get("outline_sections", [])):
        with st.container(border=True):
            st.subheader("第五步：修订")
            if st.session_state.get('revise_context_review_mode'):
                # (此处逻辑可由 EPUB 等导出功能扩展，暂时保持原有简单逻辑)
                pass
            elif 'final_manuscript' not in st.session_state:
                if st.button("开始修订全文", type="primary"):
                    st.session_state.full_draft = "\n\n".join(st.session_state.drafts)
                    result = run_step_with_spinner_func("generate_revision", "总编辑审阅中...", full_config)
                    if result: st.session_state.update(result); st.rerun()

    if 'final_manuscript' in st.session_state:
        with st.container(border=True):
            st.header("🎉 最终成品")
            st.markdown(st.session_state.final_manuscript)
            st.subheader("📦 导出作品")
            title = st.session_state.get('project_name', '未命名')
            content = st.session_state.final_manuscript
            c1, c2, c3 = st.columns(3)
            with c1: st.download_button("📥 Markdown", export_manager.export_as_markdown(title, content), f"{title}.md", "text/markdown")
            with c2: st.download_button("📥 PDF", export_manager.export_as_pdf(title, content), f"{title}.pdf", "application/pdf")
            with c3: st.download_button("📥 EPUB", export_manager.export_as_epub(title, content), f"{title}.epub", "application/epub+zip")
