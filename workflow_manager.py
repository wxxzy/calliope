
"""
工作流管理器 (Workflow Manager)
将UI逻辑与业务逻辑分离的核心。
它根据应用的当前状态，决定并执行下一步的操作。
"""
from chains import (
    create_planner_chain, create_research_chain, create_outliner_chain,
    retrieve_documents_for_drafting, create_draft_generation_chain,
    retrieve_documents_for_revising, create_revise_generation_chain
)
import tool_provider
import text_splitter_provider
import vector_store_manager
import re_ranker_provider
import logging
from custom_exceptions import LLMOperationError, ToolOperationError, VectorStoreOperationError
from langchain_core.exceptions import OutputParserException
import requests

# --- 优雅地处理可选的 LLM 提供商异常 ---
# 我们将尝试导入常用提供商的异常，但如果库未安装，也不会导致程序崩溃。
# 将同一类型的异常分组，以便在 except 块中统一处理。

_AuthenticationErrors = []
_RateLimitErrors = []
_APIErrors = []

try:
    from openai import AuthenticationError, RateLimitError, APIError
    _AuthenticationErrors.append(AuthenticationError)
    _RateLimitErrors.append(RateLimitError)
    _APIErrors.append(APIError)
except ImportError:
    pass

try:
    from anthropic import AuthenticationError, RateLimitError, APIError
    _AuthenticationErrors.append(AuthenticationError)
    _RateLimitErrors.append(RateLimitError)
    _APIErrors.append(APIError)
except ImportError:
    pass

try:
    from google.api_core.exceptions import PermissionDenied, ResourceExhausted, GoogleAPICallError
    # 将 Google 的异常映射到我们的分类中
    # PermissionDenied 类似于 AuthenticationError
    _AuthenticationErrors.append(PermissionDenied)
    # ResourceExhausted 类似于 RateLimitError
    _RateLimitErrors.append(ResourceExhausted)
    # GoogleAPICallError 作为通用的 API 错误
    _APIErrors.append(GoogleAPICallError)
except ImportError:
    pass

# 元组化，以便在 except 块中直接使用
AUTH_ERRORS = tuple(_AuthenticationErrors)
RATE_LIMIT_ERRORS = tuple(_RateLimitErrors)
API_ERRORS = tuple(_APIErrors)


workflow_logger = logging.getLogger(__name__) # 获取当前模块的logger

def run_step(step_name: str, state: dict, full_config: dict, writing_style_description: str):
    """
    根据步骤名称、当前状态、完整配置和写作风格描述，执行相应的业务逻辑。
    此函数现在包含了详细的错误处理逻辑。
    """
    workflow_logger.info(f"开始执行步骤: {step_name}, 项目: {state.get('project_name')}")
    collection_name = state.get("collection_name")

    try:
        if step_name == "plan":
            planner_chain = create_planner_chain(writing_style=writing_style_description)
            planner_input = {
                "user_prompt": state.get("user_prompt"),
                "plan": state.get("plan"), # 传递当前计划（如果存在）
                "refinement_instruction": state.get("refinement_instruction") # 传递优化指令（如果存在）
            }
            plan = planner_chain.invoke(planner_input)
            workflow_logger.info(f"步骤 'plan' 完成，生成计划。")
            return {"plan": plan}

        elif step_name == "research":
            search_tool = tool_provider.get_tool(state.get("selected_tool_id"))
            research_chain = create_research_chain(search_tool=search_tool, writing_style=writing_style_description)
            research_input = {
                "plan": state.get("plan"),
                "user_prompt": state.get("user_prompt"),
                "research_results": state.get("research_results"), # 传递当前摘要（如果存在）
                "refinement_instruction": state.get("refinement_instruction") # 传递优化指令（如果存在）
            }
            results = research_chain.invoke(research_input)
            workflow_logger.info(f"步骤 'research' 完成，生成研究摘要。")
            return {"research_results": results}

        elif step_name == "outline":
            outliner_chain = create_outliner_chain(writing_style=writing_style_description)
            outliner_input = {
                "plan": state.get("plan"),
                "user_prompt": state.get("user_prompt"),
                "research_results": state.get("research_results"),
                "outline": state.get("outline"), # 传递当前大纲（如果存在）
                "refinement_instruction": state.get("refinement_instruction") # 传递优化指令（如果存在）
            }
            outline = outliner_chain.invoke(outliner_input)
            workflow_logger.info(f"步骤 'outline' 完成，生成大纲。")
            return {"outline": outline}

        elif step_name == "retrieve_for_draft":
            retrieved_docs = retrieve_documents_for_drafting(
                collection_name=collection_name,
                section_to_write=state.get("section_to_write")
            )
            workflow_logger.info(f"步骤 'retrieve_for_draft' 完成，检索到 {len(retrieved_docs)} 个文档。")
            return {"retrieved_docs": retrieved_docs}

        elif step_name == "generate_draft":
            active_splitter_id = full_config.get('active_text_splitter', 'default_recursive') 
            text_splitter = text_splitter_provider.get_text_splitter(active_splitter_id)
            
            generation_chain = create_draft_generation_chain(writing_style=writing_style_description)
            generation_input = {
                "user_prompt": state.get("user_prompt"),
                "research_results": state.get("research_results"),
                "outline": state.get("outline"),
                "section_to_write": state.get("section_to_write"),
                "user_selected_docs": state.get("user_selected_docs", []),
                "previous_chapter_draft": state.get("current_chapter_draft"), # 传递当前草稿以供优化
                "refinement_instruction": state.get("refinement_instruction") # 传递优化指令
            }
            new_draft_content = generation_chain.invoke(generation_input)
            
            # 当生成的是最终接受的章节时，才进行索引
            # (注意：当前逻辑下，每次优化也会重新索引，这是一个可以后续改进的点)
            if new_draft_content and not state.get("refinement_instruction"):
                try:
                    vector_store_manager.index_text(collection_name, new_draft_content, text_splitter, metadata={"source": f"chapter_{state.get('drafting_index', 0) + 1}"})
                    workflow_logger.info(f"新草稿章节已成功索引。")
                except Exception as e:
                    workflow_logger.error(f"步骤 'generate_draft' 中索引草稿内容时发生向量数据库错误: {e}", exc_info=True)
                    raise VectorStoreOperationError(f"无法将新章节存入记忆库: {e}")
            
            workflow_logger.info(f"步骤 'generate_draft' 完成。")
            return {"new_draft_content": new_draft_content}

        elif step_name == "retrieve_for_revise":
            retrieved_docs = retrieve_documents_for_revising(
                collection_name=collection_name,
                full_draft=state.get("full_draft")
            )
            workflow_logger.info(f"步骤 'retrieve_for_revise' 完成，检索到 {len(retrieved_docs)} 个文档。")
            return {"retrieved_docs": retrieved_docs}

        elif step_name == "generate_revision":
            generation_chain = create_revise_generation_chain(writing_style=writing_style_description)
            generation_input = {
                "plan": state.get("plan"),
                "outline": state.get("outline"),
                "full_draft": state.get("full_draft"),
                "user_selected_docs": state.get("user_selected_docs", [])
            }
            final_manuscript = generation_chain.invoke(generation_input)
            workflow_logger.info(f"步骤 'generate_revision' 完成。")
            return {"final_manuscript": final_manuscript}
            
        else:
            workflow_logger.error(f"发现未知步骤名称: {step_name}")
            raise ValueError(f"未知的步骤名称: {step_name}")

    except AUTH_ERRORS as e:
        workflow_logger.error(f"步骤 '{step_name}' 发生认证错误: {e}", exc_info=True)
        raise LLMOperationError("API认证失败。请检查您的API密钥是否正确、有效，并在.env文件或系统配置中正确设置。")
    except RATE_LIMIT_ERRORS as e:
        workflow_logger.error(f"步骤 '{step_name}' 发生速率限制错误: {e}", exc_info=True)
        raise LLMOperationError("API请求已达到速率限制。请稍后重试或检查您的账户用量。")
    except API_ERRORS as e:
        workflow_logger.error(f"步骤 '{step_name}' 发生API错误: {e}", exc_info=True)
        # 尝试提供更具体的模型名称错误提示
        if "model_not_found" in str(e).lower() or "does not exist" in str(e).lower():
            raise LLMOperationError(f"API返回错误：模型未找到。请检查您在“系统配置”中为 '{step_name}' 分配的模型名称是否正确。")
        raise LLMOperationError(f"API返回错误: {e}。这可能是模型名称不正确、服务暂时不可用或输入内容触发了安全策略。")
    except requests.exceptions.ConnectionError as e:
        workflow_logger.error(f"步骤 '{step_name}' 发生网络连接错误: {e}", exc_info=True)
        raise LLMOperationError("网络连接错误。请检查您的网络连接以及API服务地址（Base URL）是否正确。")
    except OutputParserException as e:
        workflow_logger.error(f"步骤 '{step_name}' 发生输出解析错误: {e}", exc_info=True)
        raise LLMOperationError(f"无法按预期格式解析模型的输出。这可能是暂时的模型输出不稳定，您可以直接重试。如果问题持续，可能需要调整Prompt。")
    except Exception as e:
        # 捕获所有其他未知异常
        workflow_logger.error(f"步骤 '{step_name}' 发生未知错误: {e}", exc_info=True)
        
        error_str = str(e).lower()
        # 专门处理流式输出中断的错误
        if "invalid chunk" in error_str or "missing finish reason" in error_str:
            raise LLMOperationError(f"模型输出流异常中断: {e}。这通常是临时网络问题或模型提供方服务不稳定所致，直接重试通常可以解决。")

        # 特别处理工具调用相关的错误
        if step_name == "research":
             raise ToolOperationError(f"执行“研究”步骤时发生未知错误: {e}。请检查工具配置和网络连接。")
        
        # 其他所有未知错误
        raise LLMOperationError(f"执行 '{step_name}' 步骤时发生未知错误: {e}")

