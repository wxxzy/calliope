"""
研究业务服务 (Research Service)
处理在线搜索与信息总结业务逻辑。
"""
from chains import create_research_chain
import tool_provider

class ResearchService:
    @staticmethod
    def run_research(state: dict, writing_style: str, execute_func):
        """执行多源研究搜索与总结"""
        search_tool = tool_provider.get_tool(state.get("selected_tool_id"))
        chain = create_research_chain(search_tool, writing_style=writing_style)
        inputs = {
            "plan": state.get("plan"),
            "user_prompt": state.get("user_prompt"),
            "research_results": state.get("research_results"),
            "refinement_instruction": state.get("refinement_instruction")
        }
        return {"research_results": execute_func(chain, inputs)}
