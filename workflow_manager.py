"""
工作流协调中心 (Workflow Manager)
系统的 Facade 层，负责将 UI 请求分发至具体的 Service 处理。
"""
import logging
import requests
from custom_exceptions import LLMOperationError, ToolOperationError, VectorStoreOperationError
from langchain_core.exceptions import OutputParserException

# 引入子服务
from services.writing_service import WritingService
from services.research_service import ResearchService
from services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)

def run_step(step_name: str, state: dict, full_config: dict, writing_style_description: str, stream_callback=None):
    """
    业务逻辑统一入口点。
    """
    logger.info(f"路由请求: {step_name} (项目: {state.get('project_name')})")

    def _execute_chain(chain, inputs):
        """执行链的包装器，支持流式与普通模式"""
        if stream_callback:
            full_text = ""
            for chunk in chain.stream(inputs):
                full_text += chunk
                stream_callback(chunk)
            return full_text
        return chain.invoke(inputs)

    try:
        res = {}
        # 1. 写作相关业务
        if step_name == "update_bible":
            res = WritingService.update_project_bible(state, state.get("world_bible"), full_config)
        elif step_name == "plan":
            res = WritingService.run_plan(state, writing_style_description, _execute_chain)
        elif step_name == "outline":
            res = WritingService.run_outline(state, writing_style_description, _execute_chain)
        elif step_name == "retrieve_for_draft":
            res = WritingService.retrieve_for_draft(state, full_config)
        elif step_name == "generate_draft":
            res = WritingService.generate_draft(state, writing_style_description, full_config, _execute_chain)
        elif step_name == "generate_revision":
            res = WritingService.run_revision(state, writing_style_description, _execute_chain)

        # 2. 研究相关业务
        elif step_name == "research":
            res = ResearchService.run_research(state, writing_style_description, _execute_chain)

        # 3. 知识相关业务
        elif step_name == "critique":
            res = KnowledgeService.run_critique(state, writing_style_description, _execute_chain)
        elif step_name == "update_graph":
            res = KnowledgeService.update_graph(state)
        elif step_name == "run_naming":
            res = KnowledgeService.run_naming(state, state.get("collection_name"), state.get("communities_for_naming", {}))
        
        else:
            raise ValueError(f"未知的步骤名称: {step_name}")

        # 自动同步结果到状态字典 (统一状态处理逻辑)
        if isinstance(res, dict):
            state.update(res)
        return res

    except Exception as e:
        # 统一的错误处理逻辑 (保持原有健壮性)
        logger.error(f"执行 {step_name} 失败: {e}", exc_info=True)
        # 此处可根据异常类型抛出自定义友好异常 (LLMOperationError 等)
        # 简化版：
        raise LLMOperationError(f"业务执行失败: {e}")