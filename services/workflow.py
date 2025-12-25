"""
工作流协调中心 (Workflow Manager)
系统的 Facade 层，负责将 UI 请求分发至具体的 Service 处理。
已实现与 UI 框架 (Streamlit) 的彻底解耦。
"""
from __future__ import annotations
import logging
from core.exceptions import LLMOperationError
from core.schemas import ProjectContext

# 引入子服务
from services.writing_service import WritingService
from services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)

def run_step(step_name: str, context: ProjectContext, full_config: dict, writing_style_description: str, stream_callback=None):
    """
    业务逻辑统一入口点。
    
    Args:
        step_name: 步骤名称
        context: ProjectContext 对象 (纯 Python 领域模型)
        full_config: 全局配置字典
        writing_style_description: 风格描述字符串
        stream_callback: 流式输出回调
    """
    logger.info(f"路由请求: {step_name} (项目根目录: {context.project_root})")

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
            res = KnowledgeService.sync_bible(context, context.world_bible, full_config)
        elif step_name == "plan":
            res = WritingService.run_plan(context, writing_style_description, full_config, _execute_chain)
        elif step_name == "outline":
            res = WritingService.run_outline(context, writing_style_description, _execute_chain)
        elif step_name == "retrieve_for_draft":
            res = WritingService.retrieve_for_draft(context, full_config)
        elif step_name == "generate_draft":
            res = WritingService.generate_draft(context, writing_style_description, full_config, _execute_chain)
        elif step_name == "generate_revision":
            res = WritingService.run_revision(context, writing_style_description, _execute_chain)

        # 2. 知识相关业务
        elif step_name == "critique":
            res = KnowledgeService.run_critique(context, writing_style_description, _execute_chain)
        elif step_name == "update_graph":
            res = KnowledgeService.update_graph(context)
        
        else:
            raise ValueError(f"未知的步骤名称: {step_name}")

        return res

    except Exception as e:
        logger.error(f"执行 {step_name} 失败: {e}", exc_info=True)
        raise LLMOperationError(f"业务执行失败: {e}")
