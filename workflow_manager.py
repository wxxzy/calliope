
"""
工作流管理器 (Workflow Manager)
将UI逻辑与业务逻辑分离的核心。
它根据应用的当前状态，决定并执行下一步的操作。
"""
from chains import (
    create_planner_chain, create_research_chain, create_outliner_chain,
    retrieve_documents_for_drafting, create_draft_generation_chain,
    retrieve_documents_for_revising, create_revise_generation_chain,
    create_chapter_summary_chain, create_critic_chain
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

# 元组化，以便在 except 块中直接使用
AUTH_ERRORS = tuple(_AuthenticationErrors)
RATE_LIMIT_ERRORS = tuple(_RateLimitErrors)
API_ERRORS = tuple(_APIErrors)


workflow_logger = logging.getLogger(__name__) # 获取当前模块的logger

def run_step(step_name: str, state: dict, full_config: dict, writing_style_description: str, stream_callback=None):
    """
    根据步骤名称、当前状态、完整配置和写作风格描述，执行相应的业务逻辑。
    此函数现在包含了详细的错误处理逻辑，并支持流式输出。
    
    Args:
        stream_callback (callable, optional): 一个接受字符串块的回调函数，用于流式输出。
    """
    workflow_logger.info(f"开始执行步骤: {step_name}, 项目: {state.get('project_name')}")
    collection_name = state.get("collection_name")

    def _execute_chain(chain, inputs):
        """辅助函数：根据是否有回调决定使用 invoke 还是 stream"""
        if stream_callback:
            full_text = ""
            for chunk in chain.stream(inputs):
                full_text += chunk
                stream_callback(chunk)
            return full_text
        else:
            return chain.invoke(inputs)

    try:
        if step_name == "critique":
            # 获取待审阅内容，根据当前上下文判断是审阅大纲还是草稿
            target_type = state.get("critique_target_type", "draft") # 'outline' or 'draft'
            
            content_to_review = ""
            if target_type == "outline":
                content_to_review = state.get("outline", "")
            else:
                # 默认审阅最新生成的章节草稿
                drafts = state.get("drafts", [])
                content_to_review = drafts[-1] if drafts else ""
            
            if not content_to_review:
                raise ValueError("没有找到可供审阅的内容。")

            critic_chain = create_critic_chain(writing_style=writing_style_description)
            critique_input = {
                "stage": "章节撰写" if target_type == "draft" else "大纲设计",
                "plan": state.get("plan", ""),
                "content_to_review": content_to_review
            }
            
            critique = _execute_chain(critic_chain, critique_input)
            workflow_logger.info(f"步骤 'critique' 完成。")
            return {"current_critique": critique}

        elif step_name == "plan":
            planner_chain = create_planner_chain(writing_style=writing_style_description)
            planner_input = {
                "user_prompt": state.get("user_prompt"),
                "plan": state.get("plan"), # 传递当前计划（如果存在）
                "refinement_instruction": state.get("refinement_instruction") # 传递优化指令（如果存在）
            }
            plan = _execute_chain(planner_chain, planner_input)
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
            results = _execute_chain(research_chain, research_input)
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
            outline = _execute_chain(outliner_chain, outliner_input)
            workflow_logger.info(f"步骤 'outline' 完成，生成大纲。")
            return {"outline": outline}

        elif step_name == "retrieve_for_draft":
            # 获取RAG配置和重排序器
            active_re_ranker_id = full_config.get("active_re_ranker_id")
            re_ranker = re_ranker_provider.get_re_ranker(active_re_ranker_id)
            rag_config = full_config.get("rag", {})
            
            # 检索步骤不需要流式输出，因为返回的是列表
            retrieved_docs = retrieve_documents_for_drafting(
                collection_name=collection_name,
                section_to_write=state.get("section_to_write"),
                recall_k=rag_config.get("recall_k", 20),
                rerank_k=rag_config.get("rerank_k", 5),
                re_ranker=re_ranker
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
            
            new_draft_content = _execute_chain(generation_chain, generation_input)
            
            # 当生成的是最终接受的章节时，才进行索引
            if new_draft_content and not state.get("refinement_instruction"):
                try:
                    # 步骤1: 为新章节生成摘要
                    workflow_logger.info("正在为新章节生成摘要...")
                    summary_chain = create_chapter_summary_chain()
                    # 摘要生成通常很快，不需要流式展示给用户
                    chapter_summary = summary_chain.invoke({"chapter_text": new_draft_content})
                    workflow_logger.info(f"章节摘要生成完毕: {chapter_summary[:100]}...")

                    # 步骤2: 索引该摘要，而不是全文
                    metadata = {
                        "project_name": state.get("project_name"),
                        "chapter_index": state.get("drafting_index", 0) + 1,
                        "section_title": state.get("section_to_write"),
                        "document_type": "chapter_summary", # 明确文档类型为章节摘要
                        "source": f"project_{state.get('project_name')}_chapter_{state.get('drafting_index', 0) + 1}_summary"
                    }
                    vector_store_manager.index_text(collection_name, chapter_summary, text_splitter, metadata=metadata)
                    workflow_logger.info(f"新章节的摘要已成功索引，元数据: {metadata}")

                except Exception as e:
                    workflow_logger.error(f"步骤 'generate_draft' 中索引章节摘要时发生向量数据库错误: {e}", exc_info=True)
                    raise VectorStoreOperationError(f"无法将新章节摘要存入记忆库: {e}")
            
            workflow_logger.info(f"步骤 'generate_draft' 完成。")
            return {"new_draft_content": new_draft_content}
        elif step_name == "retrieve_for_revise":
            # 获取RAG配置和重排序器
            active_re_ranker_id = full_config.get("active_re_ranker_id")
            re_ranker = re_ranker_provider.get_re_ranker(active_re_ranker_id)
            rag_config = full_config.get("rag", {})
            
            # 检索步骤不需要流式
            retrieved_docs = retrieve_documents_for_revising(
                collection_name=collection_name,
                full_draft=state.get("full_draft"),
                recall_k=rag_config.get("recall_k", 30), # 修订时使用默认较高的 recall
                rerank_k=rag_config.get("rerank_k", 7),  # 修订时使用默认较高的 rerank_k
                re_ranker=re_ranker
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
            final_manuscript = _execute_chain(generation_chain, generation_input)
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

