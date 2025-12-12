"""
Vector Store Manager
负责管理ChromaDB向量数据库的连接、集合创建、数据索引和检索。
"""
import os
import chromadb
from typing import List, Optional
from langchain_chroma import Chroma
from embedding_provider import get_embedding_model
import logging

logger = logging.getLogger(__name__)

# --- ChromaDB 客户端和集合管理 ---
_chroma_client_instance = None 

def get_chroma_client():
    """获取ChromaDB客户端单例。"""
    global _chroma_client_instance
    if _chroma_client_instance is None:
        chroma_path = os.getenv("CHROMA_PERSIST_DIRECTORY", "./data/chroma_db")
        os.makedirs(chroma_path, exist_ok=True) # 确保路径存在
        
        _chroma_client_instance = chromadb.PersistentClient(path=chroma_path)
        logger.info(f"ChromaDB持久化客户端已初始化于: {chroma_path}")
    return _chroma_client_instance

def list_all_collections() -> List[str]:
    """列出ChromaDB中所有集合的名称。"""
    client = get_chroma_client()
    collections = client.list_collections()
    return [c.name for c in collections]

def get_or_create_collection(collection_name: str):
    """获取或创建一个ChromaDB集合，并返回一个LangChain的VectorStore实例。"""
    client = get_chroma_client()
    embedding_function = get_embedding_model() # 获取当前激活的embedding模型
    
    # 确保集合在被LangChain包装前已存在
    client.get_or_create_collection(name=collection_name)
    
    vectorstore = Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=embedding_function
    )
    logger.info(f"ChromaDB集合 '{collection_name}' 已准备就绪。")
    return vectorstore

def reset_collection(collection_name: str):
    """重置（删除并重建）一个集合。"""
    client = get_chroma_client()
    
    # 检查集合是否存在
    collections = client.list_collections()
    collection_exists = any(c.name == collection_name for c in collections)
    
    if collection_exists:
        try:
            client.delete_collection(name=collection_name)
            logger.info(f"集合 '{collection_name}' 已被删除。")
        except Exception as e:
            logger.error(f"尝试删除集合 '{collection_name}' 时发生错误: {e}", exc_info=True)
            # 即使删除失败，也继续尝试创建，get_or_create_collection是幂等的
    else:
        logger.info(f"集合 '{collection_name}' 不存在，无需删除。")
        
    return get_or_create_collection(collection_name)


# --- 文本处理与索引 ---
def index_text(collection_name: str, text: str, text_splitter, metadata: dict = None):
    """
    将大段文本切块、向量化并存入指定的集合。
    
    Args:
        collection_name (str): 目标集合的名称。
        text (str): 要索引的文本内容。
        text_splitter: 一个已实例化的LangChain TextSplitter对象。
        metadata (dict): (可选) 与此文本关联的元数据。
    """
    if not text or not text.strip():
        logger.warning("尝试索引空文本，操作已跳过。")
        return

    # 1. 使用传入的切分器切块
    chunks = text_splitter.split_text(text)
    
    # 2. 获取集合
    vectorstore = get_or_create_collection(collection_name)
    
    # 3. 添加到向量数据库
    metadatas = [metadata] * len(chunks) if metadata else None
    vectorstore.add_texts(texts=chunks, metadatas=metadatas)
    
    logger.info(f"成功将 {len(chunks)} 个文本块索引到集合 '{collection_name}'。")

# --- 检索 ---
def retrieve_context(collection_name: str, query: str, n_results: int = 5, re_ranker=None, re_ranker_top_n: int = 3) -> list[str]:
    """
    从指定集合中检索与查询最相关的文本块，并支持可选的重排。

    Args:
        collection_name (str): 从哪个集合检索。
        query (str): 查询字符串。
        n_results (int): 初始检索返回的文档数量。
        re_ranker: (可选) 已实例化的重排器模型，例如 CrossEncoder。
        re_ranker_top_n (int): 重排后返回的最终文档数量。

    Returns:
        list[str]: 相关的文本块内容列表。
    """
    vectorstore = get_or_create_collection(collection_name)
    
    # 如果有重排器，则初始检索更多文档
    initial_n_results = n_results * 3 if re_ranker else n_results 
    results_with_scores = vectorstore.similarity_search_with_score(query, k=initial_n_results)
    
    retrieved_docs = [doc.page_content for doc, score in results_with_scores]
    logger.debug(f"从 '{collection_name}' 中为查询 '{query}' 初始检索到 {len(retrieved_docs)} 个文档。")

    if re_ranker and retrieved_docs:
        logger.debug(f"正在使用重排器重新排序前 {len(retrieved_docs)} 个文档...")
        # 准备重排器输入格式: [(query, doc_content), ...]
        reranker_input = [(query, doc_content) for doc_content in retrieved_docs]
        scores = re_ranker.predict(reranker_input)
        
        # 将文档和分数配对
        ranked_docs_with_scores = sorted(zip(retrieved_docs, scores), key=lambda x: x[1], reverse=True)
        
        # 返回重排后的前 re_ranker_top_n 个文档
        final_retrieved_docs = [doc for doc, score in ranked_docs_with_scores[:re_ranker_top_n]]
        logger.debug(f"重排后返回前 {len(final_retrieved_docs)} 个文档。")
        return final_retrieved_docs
    else:
        return retrieved_docs # 如果没有重排器或没有文档，则返回初始检索结果

def get_collection_data(collection_name: str) -> dict:
    """
    获取指定集合的所有数据。

    Args:
        collection_name (str): 集合名称。

    Returns:
        dict: 包含 'ids', 'documents', 'metadatas' 的字典。
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(name=collection_name)
        data = collection.get(include=['metadatas', 'documents'])
        logger.debug(f"成功从集合 '{collection_name}' 获取 {len(data['ids'])} 条数据。")
        return data
    except ValueError:
        logger.warning(f"集合 '{collection_name}' 不存在，无法获取数据。")
        return {'ids': [], 'documents': [], 'metadatas': []}
    except Exception as e:
        logger.error(f"获取集合 '{collection_name}' 数据时发生错误: {e}", exc_info=True)
        return {'ids': [], 'documents': [], 'metadatas': []}

def delete_documents(collection_name: str, ids: List[str]):
    """
    根据ID列表从指定集合中删除文档。

    Args:
        collection_name (str): 集合名称。
        ids (List[str]): 要删除的文档ID列表。
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(name=collection_name)
        collection.delete(ids=ids)
        logger.info(f"成功从集合 '{collection_name}' 中删除 {len(ids)} 个文档。")
    except Exception as e:
        logger.error(f"从集合 '{collection_name}' 删除文档时发生错误: {e}", exc_info=True)

def update_document(collection_name: str, doc_id: str, new_text: str = None, new_metadata: dict = None):
    """
    更新指定ID的文档内容或元数据。

    Args:
        collection_name (str): 集合名称。
        doc_id (str): 要更新的文档ID。
        new_text (str, optional): 新的文本内容。
        new_metadata (dict, optional): 新的元数据。
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(name=collection_name)
        update_args = {"ids": [doc_id]}
        if new_text is not None:
            update_args["documents"] = [new_text]
        if new_metadata is not None:
            update_args["metadatas"] = [new_metadata]
        
        if "documents" in update_args or "metadatas" in update_args:
            collection.update(**update_args)
            logger.info(f"成功更新了集合 '{collection_name}' 中的文档 (ID: {doc_id})。")
        else:
            logger.warning("未提供要更新的内容 (new_text 或 new_metadata)。")

    except Exception as e:
        logger.error(f"更新集合 '{collection_name}' 中的文档时发生错误: {e}", exc_info=True)

# --- Test function ---
if __name__ == '__main__':
    # 假设 get_embedding_model 和 get_re_ranker 已正确配置和工作
    os.environ["CHROMA_PERSIST_DIRECTORY"] = "./data/chroma_test_reranker_db" # 使用单独的测试目录

    try:
        logger.info("--- 测试 Vector Store Manager 的重排检索功能 ---")
        
        test_collection = "reranker_test_collection"
        reset_collection(test_collection)

        from text_splitter_provider import get_text_splitter
        splitter = get_text_splitter('default_recursive') # 或 'user_semantic_splitter'
        
        # 索引一些测试数据
        index_text(test_collection, "制作一杯美味咖啡的关键在于咖啡豆的质量和冲泡水温的控制。", splitter, metadata={"source": "coffee_guide"})
        index_text(test_collection, "浓缩咖啡的制作需要高压萃取，通常用于制作拿铁和卡布奇诺。", splitter, metadata={"source": "espresso_basics"})
        index_text(test_collection, "茶是一种健康的饮品，有绿茶、红茶、乌龙茶等多种类型。", splitter, metadata={"source": "tea_facts"})
        index_text(test_collection, "挑选新鲜的咖啡豆是制作优质咖啡的第一步，建议购买烘焙日期较近的。", splitter, metadata={"source": "coffee_beans"})
        index_text(test_collection, "冲泡咖啡的水温应在90-96摄氏度之间，过高或过低都会影响风味。", splitter, metadata={"source": "water_temp"})

        # 1. 不使用重排器进行检索
        logger.info("\n--- 不使用重排器检索 (k=2) ---")
        query_no_reranker = "如何冲泡一杯好喝的咖啡？"
        results_no_reranker = retrieve_context(test_collection, query_no_reranker, n_results=2)
        for doc in results_no_reranker:
            logger.info(f"- {doc[:50]}...")

        # 2. 使用重排器进行检索
        logger.info("\n--- 使用重排器检索 (初始k=5, 重排后k=2) ---")
        reranker_instance = get_re_ranker() # 获取重排器实例
        if reranker_instance:
            query_with_reranker = "咖啡的最佳冲泡方法是什么？"
            results_with_reranker = retrieve_context(test_collection, query_with_reranker, n_results=5, re_ranker=reranker_instance, re_ranker_top_n=2)
            for doc in results_with_reranker:
                logger.info(f"- {doc[:50]}...")
            assert len(results_with_reranker) == 2
        else:
            logger.warning("未能获取重排器实例，跳过重排器测试。请确保 user_config.yaml 中已配置活跃重排器。")

        logger.info("\n重排检索测试通过！(如果重排器测试被执行)")

    except (ValueError, FileNotFoundError, ImportError) as e:
        logger.error(f"\n测试失败: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"\n发生了意外的错误: {e}", exc_info=True)
    finally:
        # 清理测试目录
        import shutil
        chroma_test_path = os.getenv("CHROMA_PERSIST_DIRECTORY")
        if os.path.exists(chroma_test_path):
            shutil.rmtree(chroma_test_path)
            logger.info(f"\n清理测试目录: {chroma_test_path}")
