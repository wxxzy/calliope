"""
Vector Store Manager
负责管理ChromaDB向量数据库的连接、集合创建、数据索引和检索。
"""
import os
# import chromadb # 移除直接导入，因为langchain_chroma会处理
from langchain_chroma import Chroma
from embedding_provider import get_embedding_model

# --- ChromaDB 客户端和集合管理 ---
# 使用单例模式确保全局只有一个ChromaDB客户端实例
_chroma_client_instance = None # 更名以避免与chromadb.Client混淆

def get_chroma_client():
    """获取ChromaDB客户端单例。"""
    global _chroma_client_instance
    if _chroma_client_instance is None:
        # 为了持久化，使用PersistentClient
        import chromadb # 仅在需要时导入
        chroma_path = os.getenv("CHROMA_PERSIST_DIRECTORY", "./data/chroma_db")
        os.makedirs(chroma_path, exist_ok=True) # 确保路径存在
        
        _chroma_client_instance = chromadb.PersistentClient(path=chroma_path)
        print(f"ChromaDB持久化客户端已初始化于: {chroma_path}")
    return _chroma_client_instance

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
    print(f"ChromaDB集合 '{collection_name}' 已准备就绪。")
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
            print(f"集合 '{collection_name}' 已被删除。")
        except Exception as e:
            print(f"尝试删除集合 '{collection_name}' 时发生错误: {e}")
            # 即使删除失败，也继续尝试创建，get_or_create_collection是幂等的
    else:
        print(f"集合 '{collection_name}' 不存在，无需删除。")
        
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
        print("警告: 尝试索引空文本，操作已跳过。")
        return

    # 1. 使用传入的切分器切块
    chunks = text_splitter.split_text(text)
    
    # 2. 获取集合
    vectorstore = get_or_create_collection(collection_name)
    
    # 3. 添加到向量数据库
    metadatas = [metadata] * len(chunks) if metadata else None
    vectorstore.add_texts(texts=chunks, metadatas=metadatas)
    
    print(f"成功将 {len(chunks)} 个文本块索引到集合 '{collection_name}'。")

# --- 检索 ---
def retrieve_context(collection_name: str, query: str, n_results: int = 5) -> list[str]:
    """
    从指定集合中检索与查询最相关的文本块。

    Args:
        collection_name (str): 从哪个集合检索。
        query (str): 查询字符串。
        n_results (int): 返回最相关的多少个结果。

    Returns:
        list[str]: 相关的文本块内容列表。
    """
    vectorstore = get_or_create_collection(collection_name)
    
    # 使用 similarity_search 进行检索
    results = vectorstore.similarity_search(query, k=n_results)
    
    # 提取文档内容
    retrieved_docs = [doc.page_content for doc in results]
    print(f"从 '{collection_name}' 中为查询 '{query}' 检索到 {len(retrieved_docs)} 个相关文档。")
    return retrieved_docs

# --- Test function ---
if __name__ == '__main__':
    try:
        print("--- 测试 Vector Store Manager ---")
        
        test_collection = "project_test"
        
        print(f"\n--- 步骤1: 重置测试集合 '{test_collection}' ---")
        reset_collection(test_collection)

        print(f"\n--- 步骤2: 索引'世界观'文本 ---")
        from text_splitter_provider import get_text_splitter
        splitter = get_text_splitter('default_chinese') # 获取一个切分器实例

        world_bible = """
        主角：艾拉，一位记忆侦探，能够进入他人的记忆寻找线索。她性格冷静，但对“数据幽灵”有深深的恐惧。
        反派：代号为“Morpheus”的数据幽灵，一个能够篡改和窃取记忆的AI。
        故事背景：发生在一个名为“新亚特兰蒂斯”的赛博朋克城市。
        """
        index_text(test_collection, world_bible, splitter, metadata={"source": "world_bible"})

        print(f"\n--- 步骤3: 索引'第一章'文本 ---")
        chapter_1 = """
        雨夜，新亚特兰蒂斯的霓虹灯在湿滑的街道上投下斑驳的光影。艾拉接到了一桩新案子：一位富商的记忆被离奇窃取。
        现场唯一的线索是一个数字签名，Morpheus。艾拉感到一阵寒意，她知道，她最不愿面对的敌人回来了。
        """

        index_text(test_collection, chapter_1, splitter, metadata={"source": "chapter_1"})

        print(f"\n--- 步骤4: 检索与'艾拉和Morpheus的关系'相关的内容 ---")
        retrieved = retrieve_context(test_collection, "艾拉和Morpheus是什么关系？", n_results=2)
        
        print("\n--- 检索结果 ---")
        for i, doc in enumerate(retrieved):
            print(f"结果 {i+1}:\n{doc}\n")
        
        assert any("数据幽灵" in doc for doc in retrieved)
        print("测试通过！")

    except (ValueError, FileNotFoundError, ImportError) as e:
        print(f"\n测试失败: {e}")
    except Exception as e:
        print(f"\n发生了意外的错误: {e}")
