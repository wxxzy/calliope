from chains.writing import (
    create_planner_chain, create_outliner_chain, 
    create_draft_generation_chain, create_revise_generation_chain
)
from chains.research import create_research_chain
from chains.knowledge import (
    create_query_rewrite_chain, create_chapter_summary_chain,
    create_critic_chain, create_graph_extraction_chain,
    create_community_naming_chain, retrieve_with_rewriting,
    create_consistency_sentinel_chain
)

# 别名兼容逻辑（如果 workflow_manager 引用了特定名称）
retrieve_documents_for_drafting = retrieve_with_rewriting
retrieve_documents_for_revising = retrieve_with_rewriting
