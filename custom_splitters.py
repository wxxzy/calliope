import logging
from typing import List
from langchain_text_splitters import TextSplitter
from semantic_chunking import SemanticChunker
from embedding_provider import get_embedding_model_name, get_embedding_model_config

logger = logging.getLogger(__name__)

class SemanticTextSplitter(TextSplitter):
    """
    一个包装 `semantic-chunking` 库的 LangChain 兼容文本切分器。
    这个库的API比较简单，只支持 `max_chunk_size` 和 `similarity_threshold`。
    """
    def __init__(self, 
                 max_chunk_size: int = 265,
                 similarity_threshold: float = 0.3,
                 **kwargs):
        super().__init__(**kwargs)
        self.max_chunk_size = max_chunk_size
        self.similarity_threshold = similarity_threshold
        
        # 获取活跃的embedding模型名称和配置
        embedding_model_id = get_embedding_model_name()
        embedding_config = get_embedding_model_config(embedding_model_id)
        
        if embedding_config and embedding_config.get("template") == "huggingface":
            model_name_or_path = embedding_config.get("model_name")
            if not model_name_or_path:
                raise ValueError("未在配置中为活跃的HuggingFace嵌入模型指定 'model_name'。")
        else:
            # 如果不是HuggingFace模型，回退到默认模型
            model_name_or_path = 'all-MiniLM-L6-v2'
            logger.warning(f"活跃的嵌入模型 '{embedding_model_id}' 不是 SentenceTransformer 类型，将回退到默认的 'all-MiniLM-L6-v2' 模型。")

        logger.info(f"正在初始化 SemanticChunker，使用模型: {model_name_or_path}")
        self.chunker = SemanticChunker(
            model_name=model_name_or_path,
            max_chunk_size=self.max_chunk_size,
            similarity_threshold=self.similarity_threshold,
        )

    def split_text(self, text: str) -> List[str]:
        """
        使用语义切分器切分文本。
        """
        if not text or not text.strip():
            return []
        
        try:
            chunks = self.chunker.semantic_chunk(text)
            logger.debug(f"通过 SemanticTextSplitter 将文本切分为 {len(chunks)} 个块。")
            return chunks
        except Exception as e:
            logger.error(f"SemanticTextSplitter 切分文本失败: {e}", exc_info=True)
            raise RuntimeError(f"语义切分失败: {e}")

# --- Test function ---
if __name__ == '__main__':
    test_text = """
    第一段。这是一个长句子，包含了很多内容，我们不希望它被轻易切断。第二句。
    第三段开始。这是另一句话。如果句子很短，比如这个。它们应该被合并。
    一个非常非常非常长的句子，它本身就超过了设定的块大小，它应该被强制切分，而不是作为一个单独的过长块存在，因为这会影响后续处理的效率和效果。这个句子的目的就是为了测试这个边界情况。
    第四段，语义上与前几段完全不同。例如，现在我们开始讨论完全不相关的量子物理学。
    量子力学是描述微观世界物质运动规律的物理学理论。它指出能量是不连续的，以光子形式传播。
    最后一段。
    """
    
    try:
        # 实例化 SemanticTextSplitter
        # 默认参数
        semantic_splitter = SemanticTextSplitter()
        chunks = semantic_splitter.split_text(test_text)
        print("\n--- Semantic Chunks (Default) ---")
        for i, chunk in enumerate(chunks):
            print(f"Chunk {i+1} ({len(chunk.split())} words):\n{chunk}\n---")
        
        # 尝试使用不同的参数
        semantic_splitter_custom = SemanticTextSplitter(
            max_chunk_size=50,
            similarity_threshold=0.45
        )
        chunks_custom = semantic_splitter_custom.split_text(test_text)
        print("\n--- Semantic Chunks (Custom) ---")
        for i, chunk in enumerate(chunks_custom):
            print(f"Chunk {i+1} ({len(chunk.split())} words):\n{chunk}\n---")

    except ValueError as e:
        print(f"错误: {e}")
        print("请确保 user_config.yaml 中已配置名为 'local_bge_embedding' 的HuggingFace嵌入模型，并且已安装其所需依赖。")
    except Exception as e:
        print(f"发生了意外的错误: {e}")
