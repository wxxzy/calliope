"""
写作工作流视图 (Writer Workflow View)
负责渲染 Tab 1 内容，包含从规划、大纲到撰写和导出的全过程 UI 交互。
"""
import streamlit as st
import vector_store_manager
import text_splitter_provider
import tool_provider
import export_manager

def render_writer_view(full_config, run_step_with_spinner_func):
    """
    渲染主写作流程界面。
    
    Args:
        full_config (dict): 全局合并配置。
        run_step_with_spinner_func (callable): 处理流式输出和加载状态的 UI包装器。
    """
    collection_name = st.session_state.collection_name
    vector_store_manager.get_or_create_collection(collection_name)

    # --- 创作辅助挂件 (New: Bible Sidebar Widget) ---
    with st.sidebar:
        st.markdown("---")
        st.subheader("🧐 当前场景百科")
        
        # 决定分析哪段文本：优先分析正要写的这一节，如果没有则分析最后一章
        analysis_text = ""
        if st.session_state.get("section_to_write"):
            analysis_text = st.session_state.section_to_write
        elif st.session_state.get("drafts"):
            analysis_text = st.session_state.drafts[-1]
        
        if analysis_text:
            from services.knowledge_service import KnowledgeService
            scene_data = KnowledgeService.get_scene_entities_info(collection_name, analysis_text)
            
            if scene_data:
                # 1. 冲突预警
                if scene_data['conflicts']:
                    for c in scene_data['conflicts']:
                        st.error(f"⚠️ 场景张力预警: {c}")
                
                # 2. 实体卡片
                for ent in scene_data['entities']:
                    with st.expander(f"**{ent['name']}** ({ent['faction']})"):
                        if ent['relations']:
                            st.write("**核心关联:**")
                            for r in ent['relations']:
                                st.caption(f"• {r}")
                        else:
                            st.caption("暂无更多关联设定")
                        
                        # --- 快速编辑功能 ---
                        st.divider()
                        with st.popover("🔧 修正/新增关系"):
                            st.caption(f"为 【{ent['name']}】 添加新关系")
                            new_rel = st.text_input("关系描述", placeholder="例如: 挚友", key=f"quick_r_{ent['name']}")
                            new_target = st.text_input("目标实体", placeholder="例如: 艾瑞克", key=f"quick_t_{ent['name']}")
                            if st.button("确认添加", key=f"quick_btn_{ent['name']}", width='stretch'):
                                if new_rel and new_target:
                                    KnowledgeService.quick_update_relation(collection_name, ent['name'], new_rel, new_target)
                                    st.success("已更新图谱！")
                                    st.rerun()
            else:
                st.info("未在当前内容中识别到已知实体。")
        else:
            st.info("开始撰写后，这里将自动浮现相关背景设定。")

    # 1. 写作风格选择器
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
            st.markdown(f"**风格描述:** *{st.session_state.project_writing_style_description}*", unsafe_allow_html=True)
        else:
            st.info("采用系统默认风格。", icon="ℹ️")

    # 3. 规划与研究 (Combined Step 1)
    with st.container(border=True):
        st.subheader("第一步：灵感构思 (规划+背景研究)")
        st.text_area("请输入您的整体写作需求：", key="user_prompt", height=100)
        
        # 将搜索工具选择集成到规划阶段
        user_tools = tool_provider.get_user_tools_config()
        st.selectbox("选择辅助研究工具:", options=list(user_tools.keys()), key="selected_tool_id")

        if 'plan' not in st.session_state:
            if st.button("生成写作计划与研究背景", type="primary", width='stretch'):
                result = run_step_with_spinner_func("plan", "规划师正在构思并检索资料...", full_config)
                if result:
                    st.rerun()
        else:
            st.text_area("写作计划", key="plan", height=200)
            
            # 显示自动研究的结果 (作为参考)
            if st.session_state.get("research_results"):
                with st.expander("🔍 查看同步生成的研究背景", expanded=False):
                    st.write(st.session_state.research_results)

            st.text_input("计划优化指令", key="plan_refinement_instruction")
            if st.button("迭代优化计划与资料", type="secondary"):
                st.session_state.refinement_instruction = st.session_state.plan_refinement_instruction
                result = run_step_with_spinner_func("plan", "正在重新构思并更新资料...", full_config)
                if result:
                    st.session_state.clear_specific_refinement = "plan_refinement_instruction"
                    st.rerun()

    if 'plan' in st.session_state:
        # 大纲环节 (Outliner) - 现在是第二步
        with st.container(border=True):
            st.subheader("第二步：大纲设计")
            if 'outline' not in st.session_state:
                if st.button("生成文章大纲", type="primary", width='stretch'):
                    result = run_step_with_spinner_func("outline", "大纲师正在规划结构...", full_config)
                    if result:
                        st.rerun()
            else:
                st.text_area("文章大纲", key="outline", height=400)
                st.text_input("大纲优化指令", key="outline_refinement_instruction")
                
                # 自动执行 (采纳建议后)
                if st.session_state.get("auto_run_outline_refinement"):
                    del st.session_state.auto_run_outline_refinement
                    st.session_state.refinement_instruction = st.session_state.outline_refinement_instruction
                    result = run_step_with_spinner_func("outline", "优化大纲中...", full_config)
                    if result and getattr(result, "outline", None):
                        st.session_state.new_outline = result.outline
                        st.session_state.clear_specific_refinement = "outline_refinement_instruction"
                        if "current_critique" in st.session_state: del st.session_state.current_critique
                        st.rerun()

                if st.button("迭代优化大纲", type="secondary", key="refine_outline_btn"):
                    st.session_state.refinement_instruction = st.session_state.outline_refinement_instruction
                    result = run_step_with_spinner_func("outline", "正在调整大纲结构...", full_config)
                    if result and getattr(result, "outline", None):
                        st.session_state.new_outline = result.outline
                        st.session_state.clear_specific_refinement = "outline_refinement_instruction"
                        st.rerun()
                
                with st.expander("🧐 AI 评审员意见 (大纲)", expanded=False):
                    if st.button("🔍 请求 AI 评审 (大纲)", key="critique_outline_btn"):
                        st.session_state.critique_target_type = "outline"
                        result = run_step_with_spinner_func("critique", "评论员正在阅读并分析...", full_config)
                        if result and getattr(result, "current_critique", None):
                            st.session_state.current_critique = result.current_critique
                            st.rerun()
                    if st.session_state.get("current_critique") and st.session_state.get("critique_target_type") == "outline":
                        st.markdown(st.session_state.current_critique)
                        
                        def adopt_critique_callback():
                            st.session_state.outline_refinement_instruction = f"请参考评审建议：\n{st.session_state.current_critique}"
                            st.session_state.auto_run_outline_refinement = True
                        
                        st.button("🔧 采纳建议并自动重写", key="refine_outline_with_critique", on_click=adopt_critique_callback)

        with st.container(border=True):
            st.subheader("第三步：正文撰写 (Hybrid RAG 增强)")
            if 'outline_sections' in st.session_state:
                total_chaps = len(st.session_state.outline_sections)
                done_chaps = st.session_state.get('drafting_index', 0)
                progress = done_chaps / total_chaps if total_chaps > 0 else 0
                p_col1, p_col2 = st.columns([4, 1])
                with p_col1: st.progress(progress, text=f"写作进度: {done_chaps}/{total_chaps}")
                with p_col2: st.metric("当前总字数", f"{sum(len(d) for d in st.session_state.get('drafts', [])):,}")

            if st.button("准备撰写 (解析大纲)", key="prepare_drafting"):
                st.session_state.outline_sections = [s.strip() for s in st.session_state.outline.split('\n- ') if s.strip()]
                st.session_state.drafts = []
                st.session_state.drafting_index = 0
                # 清理旧的校验警告
                if "consistency_warning" in st.session_state: del st.session_state.consistency_warning
                st.rerun()

            # --- 逻辑一致性预警展示 ---
            if st.session_state.get("consistency_warning"):
                st.error(f"🛡️ 逻辑一致性哨兵提醒：\n\n{st.session_state.consistency_warning}")
                if st.button("我知道了，忽略此警告"):
                    del st.session_state.consistency_warning
                    st.rerun()

            # 正常撰写逻辑逻辑...
            if st.session_state.get('draft_context_review_mode'):
                st.info("请确认以下背景资料是否参与本次撰写：")
                docs_to_review = st.session_state.get('draft_retrieved_docs', [])
                selected_mask = st.session_state.get('draft_selected_docs_mask', {})
                for i, doc in enumerate(docs_to_review):
                    is_selected = st.checkbox(f"记忆片段 {i+1}", value=selected_mask.get(i, False), key=f"draft_doc_{i}")
                    if is_selected: st.markdown(f"> {doc[:200]}...")
                    selected_mask[i] = is_selected
                st.session_state.draft_selected_docs_mask = selected_mask
                if st.button("✅ 确认资料并开始撰写", type="primary", key="confirm_docs_and_write"):
                    st.session_state['user_selected_docs'] = [docs_to_review[i] for i, s in selected_mask.items() if s]
                    result = run_step_with_spinner_func("generate_draft", "AI 写手正根据记忆进行创作...", full_config)
                    if result and getattr(result, "new_draft_content", None):
                        st.session_state.drafts.append(result.new_draft_content)
                        st.session_state.drafting_index += 1
                    del st.session_state['draft_context_review_mode']
                    st.rerun()

            elif 'outline_sections' in st.session_state:
                total = len(st.session_state.outline_sections)
                current = st.session_state.get('drafting_index', 0)
                if current < total:
                    st.info(f"待写章节: **{st.session_state.outline_sections[current].splitlines()[0]}**")
                    if st.button(f"撰写第 {current + 1} 章", type="primary", key=f"write_chapter_{current}"):
                        st.session_state.section_to_write = st.session_state.outline_sections[current]
                        ret_result = run_step_with_spinner_func("retrieve_for_draft", "正在检索图谱与向量库...", full_config)
                        if ret_result and getattr(ret_result, "retrieved_docs", None):
                            st.session_state.draft_context_review_mode = True
                            st.session_state.draft_retrieved_docs = ret_result.retrieved_docs
                            st.session_state.draft_selected_docs_mask = {i: True for i in range(len(ret_result.retrieved_docs))}
                            st.rerun()
                else:
                    st.success("🎉 全书初稿已撰写完毕！")

                # --- 检索过滤器 (New: RAG Filtering) ---
                with st.expander("🔍 检索范围高级设置 (可选)", expanded=False):
                    st.caption("设置后，AI 在生成本章时将优先/仅参考符合条件的记忆。")
                    col_f1, col_f2 = st.columns(2)
                    t_f = col_f1.text_input("限定时间", placeholder="例: 1990年", key="ui_time_filter")
                    l_f = col_f2.text_input("限定地点", placeholder="例: 黑铁堡", key="ui_loc_filter")
                    
                    active_filter = {}
                    filters = []
                    if t_f: filters.append({"time": t_f})
                    if l_f: filters.append({"location": l_f})
                    
                    if len(filters) > 1:
                        active_filter = {"$and": filters}
                    elif len(filters) == 1:
                        active_filter = filters[0]
                    else:
                        active_filter = None
                    
                    st.session_state.active_metadata_filter = active_filter
                    if active_filter:
                        st.info(f"当前已启用过滤条件: {active_filter}")

            # 章节内优化与评审
            if st.session_state.get('drafts') and st.session_state.get("drafting_index", 0) > 0:
                idx = len(st.session_state.drafts)
                st.markdown("---")
                st.subheader(f"优化第 {idx} 章")
                st.text_input("章节微调指令", key="draft_refinement_instruction", placeholder="例如：加入更多的心理活动描写")
                
                def perform_rewrite(instruction):
                    old_content = st.session_state.drafts[-1]
                    st.session_state.current_chapter_draft = old_content
                    st.session_state.refinement_instruction = instruction
                    st.session_state.drafts.pop()
                    st.session_state.drafting_index -= 1
                    result = run_step_with_spinner_func("generate_draft", "正在重写本章...", full_config)
                    if result and getattr(result, "new_draft_content", None):
                        st.session_state.drafts.append(result.new_draft_content)
                        st.session_state.drafting_index += 1
                        st.success("重写成功！")
                    else:
                        st.session_state.drafts.append(old_content)
                        st.session_state.drafting_index += 1
                    st.rerun()

                if st.session_state.get("auto_run_draft_refinement"):
                    del st.session_state.auto_run_draft_refinement
                    perform_rewrite(st.session_state.draft_refinement_instruction)

                if st.button(f"根据指令重写第 {idx} 章", type="secondary"):
                    perform_rewrite(st.session_state.draft_refinement_instruction)

                with st.expander(f"🧐 第 {idx} 章 AI 评审"):
                    if st.button(f"🔍 获取本章评审", key=f"critique_draft_{idx}_btn"):
                        st.session_state.critique_target_type = "draft"
                        result = run_step_with_spinner_func("critique", "评论员正在交叉比对大纲...", full_config)
                        if result and getattr(result, "current_critique", None):
                            st.session_state.current_critique = result.current_critique
                            st.rerun()
                    if st.session_state.get("current_critique") and st.session_state.get("critique_target_type") == "draft":
                        st.markdown(st.session_state.current_critique)
                        def adopt_draft_critique_callback():
                            st.session_state.draft_refinement_instruction = f"请参考建议重写：\n{st.session_state.current_critique}"
                            st.session_state.auto_run_draft_refinement = True
                        st.button("🔧 采纳建议并重写", on_click=adopt_draft_critique_callback)

            # 完整初稿展示
            if st.session_state.get('drafts'):
                with st.expander("📖 查看完整初稿 (实时预览)", expanded=False):
                    for i, draft in enumerate(st.session_state.drafts):
                        st.markdown(f"#### 第 {i+1} 章 (字数: {len(draft)})")
                        st.write(draft)
                        st.markdown("---")

    # 4. 修订与成品阶段...
    if st.session_state.get("drafting_index", 0) > 0 and st.session_state.get("drafting_index") == len(st.session_state.get("outline_sections", [])):
        with st.container(border=True):
            st.subheader("第四步：精修与润色")
            if 'final_manuscript' not in st.session_state:
                if st.button("开始修订全文 (总编辑介入)", type="primary"):
                    st.session_state.full_draft = "\n\n".join(st.session_state.drafts)
                    result = run_step_with_spinner_func("generate_revision", "正在润色并统一全文文风...", full_config)
                    # 结果已由包装器自动同步
                    if result:
                        st.rerun()

    if 'final_manuscript' in st.session_state:
        with st.container(border=True):
            st.header("🎉 最终成品")
            st.markdown(st.session_state.final_manuscript)
            st.subheader("📦 专业导出")
            title = st.session_state.get('project_name', '未命名')
            content = st.session_state.final_manuscript
            c1, c2, c3 = st.columns(3)
            with c1: st.download_button("📥 Markdown", export_manager.export_as_markdown(title, content), f"{title}.md", "text/markdown", key="dl_md")
            with c2: st.download_button("📥 PDF", export_manager.export_as_pdf(title, content), f"{title}.pdf", "application/pdf", key="dl_pdf")
            with c3: st.download_button("📥 EPUB", export_manager.export_as_epub(title, content), f"{title}.epub", "application/epub+zip", key="dl_epub")
