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

def delete_collection(collection_name: str):
    """
    彻底删除一个集合。
    """
    client = get_chroma_client()
    try:
        # 检查是否存在
        collections = client.list_collections()
        if any(c.name == collection_name for c in collections):
            client.delete_collection(name=collection_name)
            logger.info(f"ChromaDB 集合 '{collection_name}' 已彻底删除。")
            return True
        else:
            logger.info(f"集合 '{collection_name}' 不存在，跳过删除。")
            return False
    except Exception as e:
        logger.error(f"删除集合 '{collection_name}' 失败: {e}", exc_info=True)
        return False

def reset_collection(collection_name: str):
    """重置（删除并重建）一个集合。"""
    delete_collection(collection_name)
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
def retrieve_context(collection_name: str, query: str, recall_k: int = 20, re_ranker=None, rerank_k: int = 5, filter_dict: dict = None) -> list[str]:
    """
    从指定集合中检索与查询最相关的文本块，并支持元数据过滤和可选的重排。

    Args:
        collection_name (str): 从哪个集合检索。
        query (str): 查询字符串。
        recall_k (int): 初始检索返回的文档数量。
        re_ranker: (可选) 已实例化的重排器模型。
        rerank_k (int): 重排后返回的最终文档数量。
        filter_dict (dict): (可选) ChromaDB 元数据过滤字典，例如 {"time": "1990年"}。

    Returns:
        list[str]: 相关的文本块内容列表。
    """
    vectorstore = get_or_create_collection(collection_name)
    
    # 执行带过滤的检索
    results_with_scores = vectorstore.similarity_search_with_score(query, k=recall_k, filter=filter_dict)
    
    retrieved_docs = [doc.page_content for doc, score in results_with_scores]
    logger.debug(f"从 '{collection_name}' 中为查询 '{query}' 初始检索到 {len(retrieved_docs)} 个文档。")

    if re_ranker and retrieved_docs:
        logger.debug(f"正在使用重排器重新排序前 {len(retrieved_docs)} 个文档...")
        # 准备重排器输入格式: [(query, doc_content), ...]
        reranker_input = [(query, doc_content) for doc_content in retrieved_docs]
        scores = re_ranker.predict(reranker_input)
        
        # 将文档和分数配对
        ranked_docs_with_scores = sorted(zip(retrieved_docs, scores), key=lambda x: x[1], reverse=True)
        
        # 返回重排后的前 rerank_k 个文档
        final_retrieved_docs = [doc for doc, score in ranked_docs_with_scores[:rerank_k]]
        logger.debug(f"重排后返回前 {len(final_retrieved_docs)} 个文档。")
        return final_retrieved_docs
    else:
        # 如果没有重排器或没有文档，则返回初始检索结果的前 rerank_k 个（保持与重排一致的返回数量）
        return retrieved_docs[:rerank_k]

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
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(name=collection_name)
        collection.delete(ids=ids)
        logger.info(f"成功从集合 '{collection_name}' 中删除 {len(ids)} 个文档。")
    except Exception as e:
        logger.error(f"从集合 '{collection_name}' 删除文档时发生错误: {e}", exc_info=True)

def delete_by_metadata(collection_name: str, filter_dict: dict):
    """
    根据元数据过滤条件删除文档。
    例如：delete_by_metadata(col, {"source": "world_bible"})
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(name=collection_name)
        collection.delete(where=filter_dict)
        logger.info(f"已根据元数据 {filter_dict} 清理集合 '{collection_name}' 中的旧数据。")
        return True
    except Exception as e:
        logger.error(f"按元数据删除失败: {e}")
        return False

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
