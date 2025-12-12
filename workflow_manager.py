"""
工作流管理器 (Workflow Manager)
将UI逻辑与业务逻辑分离的核心。
它根据应用的当前状态，决定并执行下一步的操作。
"""
from chains import create_planner_chain, create_research_chain, create_outliner_chain, create_drafter_chain, create_reviser_chain
import tool_provider
import text_splitter_provider
import vector_store_manager

def run_step(step_name: str, state: dict, full_config: dict, writing_style_description: str):
    """
    根据步骤名称、当前状态、完整配置和写作风格描述，执行相应的业务逻辑。

    Args:
        step_name (str): 要执行的步骤名称 (e.g., "plan", "research").
        state (dict): 应用的当前状态 (通常是 st.session_state)。
        full_config (dict): 完整的应用程序配置，用于获取模型ID、文本切分器ID等。
        writing_style_description (str): 活跃的写作风格描述。

    Returns:
        dict: 更新后的状态。
    """
    collection_name = state.get("collection_name")
    
    if step_name == "plan":
        planner_chain = create_planner_chain(writing_style=writing_style_description)
        plan = planner_chain.invoke({"user_prompt": state.get("user_prompt")})
        return {"plan": plan}

    elif step_name == "research":
        search_tool = tool_provider.get_tool(state.get("selected_tool_id"))
        research_chain = create_research_chain(search_tool=search_tool, writing_style=writing_style_description)
        research_input = {
            "plan": state.get("plan"),
            "user_prompt": state.get("user_prompt")
        }
        results = research_chain.invoke(research_input)
        return {"research_results": results}

    elif step_name == "outline":
        outliner_chain = create_outliner_chain(writing_style=writing_style_description)
        outliner_input = {
            "plan": state.get("plan"),
            "user_prompt": state.get("user_prompt"),
            "research_results": state.get("research_results")
        }
        outline = outliner_chain.invoke(outliner_input)
        return {"outline": outline}

    elif step_name == "draft":
        # 兼容旧代码，这里使用 full_config 获取 active_splitter_id
        active_splitter_id = full_config.get('active_text_splitter', 'default_recursive')
        text_splitter = text_splitter_provider.get_text_splitter(active_splitter_id)
        
        drafter_chain = create_drafter_chain(collection_name, writing_style=writing_style_description)
        drafter_input = {
            "user_prompt": state.get("user_prompt"),
            "research_results": state.get("research_results"),
            "outline": state.get("outline"),
            "section_to_write": state.get("section_to_write")
        }
        draft_content = drafter_chain.invoke(drafter_input)
        
        # 将新章节也加入记忆库
        vector_store_manager.index_text(collection_name, draft_content, text_splitter, metadata={"source": f"chapter_{state.get('drafting_index', 0) + 1}"})
        
        return {"new_draft_content": draft_content}
        
    elif step_name == "revise":
        reviser_chain = create_reviser_chain(collection_name, writing_style=writing_style_description)
        reviser_input = {
            "plan": state.get("plan"),
            "outline": state.get("outline"),
            "full_draft": state.get("full_draft")
        }
        final_manuscript = reviser_chain.invoke(reviser_input)
        return {"final_manuscript": final_manuscript}
        
    else:
        raise ValueError(f"未知的步骤名称: {step_name}")
