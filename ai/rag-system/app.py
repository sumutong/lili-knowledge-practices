# === Block 1 ===
#!/usr/bin/env python3
"""
企业文档 RAG 知识库系统
依赖: pip install langchain langchain-openai chromadb pypdf docx2txt unstructured
      fastapi uvicorn python-multipart tiktoken
"""
import hashlib
import logging
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredMarkdownLoader,
    TextLoader,
    WebBaseLoader,
)
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain.vectorstores import Chroma
from langchain.prompts import PromptTemplate
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RAG")

# ─── 配置 ─────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-xxx")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 200))
TOP_K = int(os.getenv("TOP_K", 5))

# ─── 初始化向量存储 ───────────────────────────────────────
embeddings = OpenAIEmbeddings(
    model=EMBEDDING_MODEL,
    api_key=OPENAI_API_KEY,
)

chroma_client = chromadb.PersistentClient(
    path=CHROMA_PERSIST_DIR,
    settings=Settings(anonymized_telemetry=False),
)

vectorstore = Chroma(
    client=chroma_client,
    collection_name="enterprise_docs",
    embedding_function=embeddings,
)

# ─── LLM 配置 ─────────────────────────────────────────────
llm = ChatOpenAI(
    model=LLM_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0.3,
    max_tokens=1024,
)

# 自定义 Prompt
RAG_PROMPT = PromptTemplate(
    template="""你是一个专业的企业知识库助手。根据以下参考文档回答问题。

## 参考文档
{context}

## 对话历史
{chat_history}

## 用户问题
{question}

## 回答规则
1. 仅根据参考文档回答，不编造信息
2. 如果文档中没有相关信息，明确说「未找到相关信息」
3. 引用具体来源（文档名称、段落）
4. 回答简洁专业，使用中文

## 回答
""",
    input_variables=["context", "chat_history", "question"],
)

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vectorstore.as_retriever(search_kwargs={"k": TOP_K}),
    chain_type_kwargs={"prompt": RAG_PROMPT},
    return_source_documents=True,
)

# ─── 文档集合管理 ─────────────────────────────────────────
class CollectionManager:
    """管理多个文档集合（按项目/部门隔离）"""

    @staticmethod
    def list_collections() -> list[str]:
        return chroma_client.list_collections()

    @staticmethod
    def get_collection(name: str):
        return Chroma(
            client=chroma_client,
            collection_name=name,
            embedding_function=embeddings,
        )

    @staticmethod
    def create_collection(name: str) -> Chroma:
        return Chroma(
            client=chroma_client,
            collection_name=name,
            embedding_function=embeddings,
        )

    @staticmethod
    def delete_collection(name: str):
        chroma_client.delete_collection(name)

# ─── 文档加载器 ───────────────────────────────────────────
class DocumentLoader:
    """多格式文档加载器"""

    SUPPORTED_EXTENSIONS = {
        ".pdf": "pdf",
        ".docx": "docx",
        ".md": "markdown",
        ".txt": "text",
        ".html": "html",
        ".htm": "html",
    }

    @classmethod
    async def load_from_file(cls, file_path: str, metadata: dict = None) -> list[Document]:
        ext = Path(file_path).suffix.lower()
        loader_type = cls.SUPPORTED_EXTENSIONS.get(ext)

        if loader_type == "pdf":
            loader = PyPDFLoader(file_path)
        elif loader_type == "docx":
            loader = Docx2txtLoader(file_path)
        elif loader_type == "markdown":
            loader = UnstructuredMarkdownLoader(file_path)
        elif loader_type in ("text", "html"):
            loader = TextLoader(file_path, encoding="utf-8")
        else:
            raise ValueError(f"不支持的文件格式: {ext}")

        docs = loader.load()

        # 添加元数据
        if metadata:
            for doc in docs:
                doc.metadata.update(metadata)

        return docs

    @classmethod
    async def load_from_url(cls, url: str, metadata: dict = None) -> list[Document]:
        loader = WebBaseLoader(url)
        docs = loader.load()
        if metadata:
            for doc in docs:
                doc.metadata.update(metadata)
        return docs

    @classmethod
    async def load_from_text(cls, text: str, metadata: dict = None) -> list[Document]:
        doc = Document(page_content=text, metadata=metadata or {})
        return [doc]

# ─── 文档处理器 ───────────────────────────────────────────
class DocumentProcessor:
    """文档分块 + 去重 + 索引"""

    def __init__(self, collection_name: str = "enterprise_docs"):
        self.collection_name = collection_name
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", "。", ".", "!", "?", "；", ";", " ", ""],
            length_function=len,
        )

    def chunk_documents(self, docs: list[Document]) -> list[Document]:
        """文档分块"""
        chunks = self.text_splitter.split_documents(docs)
        # 计算每个 chunk 的哈希用于去重
        for chunk in chunks:
            chunk.metadata["chunk_hash"] = hashlib.md5(
                chunk.page_content.encode()
            ).hexdigest()
            chunk.metadata["chunk_index"] = chunks.index(chunk)
        logger.info(f"分块完成: {len(docs)} 文档 → {len(chunks)} 块")
        return chunks

    def deduplicate(self, chunks: list[Document]) -> list[Document]:
        """基于哈希去重"""
        seen = set()
        unique = []
        for chunk in chunks:
            h = chunk.metadata["chunk_hash"]
            if h not in seen:
                seen.add(h)
                unique.append(chunk)
        removed = len(chunks) - len(unique)
        if removed:
            logger.info(f"去重: 移除 {removed} 个重复块")
        return unique

    async def index_documents(self, docs: list[Document], source_name: str) -> int:
        """索引文档到向量库"""
        # 添加来源信息
        for doc in docs:
            doc.metadata["source_name"] = source_name
            doc.metadata["indexed_at"] = datetime.now().isoformat()

        chunks = self.chunk_documents(docs)
        chunks = self.deduplicate(chunks)

        vectorstore = self.get_vectorstore()
        vectorstore.add_documents(chunks)
        logger.info(f"索引完成: {len(chunks)} 个向量块 (来源: {source_name})")
        return len(chunks)

    async def delete_by_source(self, source_name: str):
        """按来源删除文档"""
        vectorstore = self.get_vectorstore()
        collection = vectorstore._collection
        # 查询该来源的所有文档
        results = collection.get(where={"source_name": source_name})
        if results["ids"]:
            collection.delete(ids=results["ids"])
            logger.info(f"已删除来源 {source_name}: {len(results['ids'])} 条")

    def get_vectorstore(self) -> Chroma:
        return CollectionManager.get_collection(self.collection_name)

# ─── 查询服务 ─────────────────────────────────────────────
class QueryService:
    """RAG 查询 + 对话历史"""

    def __init__(self, processor: DocumentProcessor):
        self.processor = processor
        self.chat_histories: dict[str, list] = {}  # session_id -> history

    async def ask(
        self,
        question: str,
        session_id: str = "default",
        collection_name: str = "enterprise_docs",
        top_k: int = TOP_K,
    ) -> dict:
        """RAG 问答"""
        vectorstore = CollectionManager.get_collection(collection_name)
        retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})

        # 检索
        docs = retriever.invoke(question)
        context = "\n\n---\n\n".join(
            f"[来源: {d.metadata.get('source_name', '未知')}]\n{d.page_content}"
            for d in docs
        )

        # 获取历史
        history = self.chat_histories.get(session_id, [])[-6:]
        history_text = "\n".join(
            f"{'用户' if h['role']=='user' else '助手'}: {h['content']}"
            for h in history
        )

        # 生成回答
        prompt = RAG_PROMPT.format(
            context=context,
            chat_history=history_text,
            question=question,
        )

        result = await llm.ainvoke(prompt)

        # 保存历史
        if session_id not in self.chat_histories:
            self.chat_histories[session_id] = []
        self.chat_histories[session_id].append({"role": "user", "content": question})
        self.chat_histories[session_id].append({"role": "assistant", "content": result.content})

        return {
            "answer": result.content,
            "sources": [
                {
                    "content": d.page_content[:300],
                    "source": d.metadata.get("source_name", ""),
                    "page": d.metadata.get("page", ""),
                    "relevance": getattr(d, "relevance_score", None),
                }
                for d in docs
            ],
        }

    def clear_history(self, session_id: str):
        self.chat_histories.pop(session_id, None)

# ─── FastAPI 应用 ─────────────────────────────────────────
app = FastAPI(title="RAG 知识库系统", version="2.0")
processor = DocumentProcessor()
query_service = QueryService(processor)

# ─── 请求模型 ─────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str
    session_id: str = "default"
    collection: str = "enterprise_docs"

class TextIngestRequest(BaseModel):
    text: str
    source_name: str
    metadata: dict = {}

# ─── API 路由 ─────────────────────────────────────────────

@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    collection: str = "enterprise_docs",
    source_name: str = "",
):
    """上传并索引文档"""
    ext = Path(file.filename).suffix.lower()
    if ext not in DocumentLoader.SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件格式: {ext}")

    # 保存临时文件
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        metadata = {
            "filename": file.filename,
            "file_size": len(content),
            "uploaded_at": datetime.now().isoformat(),
        }

        docs = await DocumentLoader.load_from_file(
            tmp_path,
            metadata=metadata,
        )

        proc = DocumentProcessor(collection_name=collection)
        chunk_count = await proc.index_documents(
            docs,
            source_name=source_name or file.filename,
        )

        return {
            "success": True,
            "filename": file.filename,
            "chunks_indexed": chunk_count,
            "collection": collection,
        }
    finally:
        os.unlink(tmp_path)

@app.post("/api/documents/url")
async def ingest_url(req: dict):
    """从 URL 导入文档"""
    url = req.get("url")
    source_name = req.get("source_name", url)
    collection = req.get("collection", "enterprise_docs")

    docs = await DocumentLoader.load_from_url(url, {"source_url": url})
    proc = DocumentProcessor(collection_name=collection)
    count = await proc.index_documents(docs, source_name)
    return {"success": True, "chunks_indexed": count}

@app.post("/api/documents/text")
async def ingest_text(req: TextIngestRequest):
    """直接导入文本"""
    docs = await DocumentLoader.load_from_text(req.text, req.metadata)
    proc = DocumentProcessor(collection_name="enterprise_docs")
    count = await proc.index_documents(docs, req.source_name)
    return {"success": True, "chunks_indexed": count}

@app.post("/api/query")
async def query(req: QueryRequest):
    """RAG 问答"""
    result = await query_service.ask(
        question=req.question,
        session_id=req.session_id,
        collection_name=req.collection,
    )
    return {"success": True, **result}

@app.get("/api/collections")
async def list_collections():
    """列出所有文档集合"""
    collections = chroma_client.list_collections()
    return {
        "collections": [
            {"name": c.name, "count": c.count()}
            for c in collections
        ]
    }

@app.delete("/api/collections/{name}")
async def delete_collection(name: str):
    """删除文档集合"""
    CollectionManager.delete_collection(name)
    return {"success": True}

@app.delete("/api/documents/{source_name}")
async def delete_documents(source_name: str, collection: str = "enterprise_docs"):
    """按来源删除文档"""
    proc = DocumentProcessor(collection_name=collection)
    await proc.delete_by_source(source_name)
    return {"success": True}

@app.get("/health")
async def health():
    return {"status": "healthy", "vector_count": vectorstore._collection.count()}

@app.get("/")
async def index():
    """简易 Web 前端"""
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>RAG 知识库问答</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, sans-serif; background: #f5f5f5; }
        .container { max-width: 800px; margin: 40px auto; padding: 20px; }
        h1 { text-align: center; color: #333; margin-bottom: 24px; }
        .chat-box { background: white; border-radius: 12px; padding: 20px; min-height: 400px; max-height: 500px; overflow-y: auto; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .msg { margin-bottom: 16px; display: flex; }
        .msg.user { justify-content: flex-end; }
        .msg-content { max-width: 75%; padding: 12px 16px; border-radius: 12px; line-height: 1.6; }
        .user .msg-content { background: #1890ff; color: white; }
        .assistant .msg-content { background: #f0f0f0; color: #333; }
        .sources { font-size: 12px; color: #999; margin-top: 8px; padding-top: 8px; border-top: 1px solid #e8e8e8; }
        .input-area { display: flex; gap: 12px; }
        input { flex: 1; padding: 12px 16px; border: 2px solid #e8e8e8; border-radius: 8px; font-size: 15px; outline: none; }
        input:focus { border-color: #1890ff; }
        button { padding: 12px 24px; background: #1890ff; color: white; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; }
        button:hover { background: #40a9ff; }
        .upload-area { margin-bottom: 16px; }
        .upload-area input[type="file"] { padding: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 RAG 知识库问答</h1>
        <div class="upload-area">
            <input type="file" id="fileInput" accept=".pdf,.docx,.md,.txt" multiple>
            <button onclick="uploadFiles()">上传文档</button>
            <span id="uploadStatus"></span>
        </div>
        <div class="chat-box" id="chatBox"></div>
        <div class="input-area">
            <input id="questionInput" placeholder="输入你的问题..." onkeydown="if(event.key==='Enter')ask()">
            <button onclick="ask()">发送</button>
        </div>
    </div>
    <script>
        const sessionId = 'web-' + Date.now();
        async function ask() {
            const input = document.getElementById('questionInput');
            const question = input.value.trim();
            if (!question) return;
            appendMessage('user', question);
            input.value = '';
            try {
                const resp = await fetch('/api/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question, session_id: sessionId }),
                });
                const data = await resp.json();
                let answer = data.answer;
                if (data.sources && data.sources.length) {
                    answer += '<div class="sources">📖 参考: ' +
                        data.sources.map(s => s.source).join(', ') + '</div>';
                }
                appendMessage('assistant', answer, true);
            } catch (e) {
                appendMessage('assistant', '抱歉，请求失败: ' + e.message);
            }
        }
        function appendMessage(role, content, isHtml) {
            const box = document.getElementById('chatBox');
            const div = document.createElement('div');
            div.className = 'msg ' + role;
            const contentDiv = document.createElement('div');
            contentDiv.className = 'msg-content';
            if (isHtml) contentDiv.innerHTML = content;
            else contentDiv.textContent = content;
            div.appendChild(contentDiv);
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }
        async function uploadFiles() {
            const files = document.getElementById('fileInput').files;
            const status = document.getElementById('uploadStatus');
            for (const file of files) {
                const form = new FormData();
                form.append('file', file);
                status.textContent = '上传中...';
                const resp = await fetch('/api/documents/upload', { method: 'POST', body: form });
                const data = await resp.json();
                status.textContent = `✅ ${file.name} - ${data.chunks_indexed} 块已索引`;
                setTimeout(() => status.textContent = '', 3000);
            }
        }
    </script>
</body>
</html>
""")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# === Block 2 ===
# ─── multimodal_rag.py ────────────────────────────────────
import base64
import io
from typing import Optional

import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

class MultiModalEmbedder:
    """图文混合向量编码器"""

    def __init__(self, clip_model_name: str = "openai/clip-vit-base-patch32"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.clip_model = CLIPModel.from_pretrained(clip_model_name).to(self.device)
        self.clip_processor = CLIPProcessor.from_pretrained(clip_model_name)

    def embed_text(self, text: str) -> list[float]:
        """文本 → 向量"""
        inputs = self.clip_processor(
            text=[text],
            return_tensors="pt",
            padding=True,
            truncation=True,
        ).to(self.device)
        with torch.no_grad():
            text_features = self.clip_model.get_text_features(**inputs)
            # 归一化
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        return text_features.cpu().numpy()[0].tolist()

    def embed_image(self, image: Image.Image) -> list[float]:
        """图片 → 向量"""
        inputs = self.clip_processor(
            images=image,
            return_tensors="pt",
        ).to(self.device)
        with torch.no_grad():
            image_features = self.clip_model.get_image_features(**inputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        return image_features.cpu().numpy()[0].tolist()

    def embed_image_path(self, image_path: str) -> list[float]:
        return self.embed_image(Image.open(image_path))

    def embed_image_base64(self, b64_str: str) -> list[float]:
        image_data = base64.b64decode(b64_str)
        return self.embed_image(Image.open(io.BytesIO(image_data)))

class MultiModalRAG:
    """图文混合 RAG 检索"""

    def __init__(self, collection_name: str = "multimodal_docs"):
        self.embedder = MultiModalEmbedder()
        self.collection_name = collection_name
        self.chroma_client = chromadb.PersistentClient(path="./mm_chroma_db")
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_text(self, text: str, doc_id: str, metadata: dict = None):
        """添加文本"""
        embedding = self.embedder.embed_text(text)
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            metadatas=[{**(metadata or {}), "type": "text", "content": text[:500]}],
        )

    def add_image(self, image_path: str, doc_id: str,
                  caption: Optional[str] = None, metadata: dict = None):
        """添加图片（同时索引图片向量和描述文本）"""
        # 图片向量
        img_embedding = self.embedder.embed_image_path(image_path)
        self.collection.add(
            ids=[f"{doc_id}_img"],
            embeddings=[img_embedding],
            metadatas=[{**(metadata or {}), "type": "image", "path": image_path}],
        )

        # 如果有标题，也索引文本
        if caption:
            text_embedding = self.embedder.embed_text(caption)
            self.collection.add(
                ids=[f"{doc_id}_caption"],
                embeddings=[text_embedding],
                metadatas=[{**(metadata or {}), "type": "caption", "content": caption}],
            )

    def search_text(self, query: str, top_k: int = 5) -> list[dict]:
        """文本搜索"""
        embedding = self.embedder.embed_text(query)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
        )
        return self._format_results(results)

    def search_image(self, image_path: str, top_k: int = 5) -> list[dict]:
        """以图搜图"""
        embedding = self.embedder.embed_image_path(image_path)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
        )
        return self._format_results(results)

    def search_multimodal(self, query: str, top_k: int = 5) -> list[dict]:
        """混合搜索（返回文本和图片结果）"""
        embedding = self.embedder.embed_text(query)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
        )
        return self._format_results(results)

    def _format_results(self, results: dict) -> list[dict]:
        formatted = []
        if not results["ids"] or not results["ids"][0]:
            return []
        for i, doc_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0
            formatted.append({
                "id": doc_id,
                "metadata": metadata,
                "distance": distance,
                "score": 1 - distance if distance else 1,  # cosine distance → similarity
            })
        return formatted

# ─── 使用示例 ─────────────────────────────────────────────
def demo():
    rag = MultiModalRAG()

    # 索引产品文档和图片
    rag.add_text("产品 X 是一款高性能笔记本，搭载 M3 芯片，续航 18 小时", "prod_x_desc")
    rag.add_image("./images/laptop_x.jpg", "laptop_x",
                  caption="产品 X 笔记本电脑外观图 - 银色金属机身")
    rag.add_text("退换货政策：7 天无理由退货，15 天换货", "return_policy")

    # 文本搜索
    print("=== 搜索: 笔记本电池续航 ===")
    results = rag.search_text("笔记本电池续航")
    for r in results:
        print(f"  [{r['metadata'].get('type')}] {r['metadata'].get('content', '')[:100]} (score: {r['score']:.3f})")

    # 以图搜图
    print("\n=== 以图搜图 ===")
    results = rag.search_image("./images/query_laptop.jpg")
    for r in results:
        print(f"  [{r['metadata'].get('type')}] {r['metadata'].get('path', '')} (score: {r['score']:.3f})")

if __name__ == "__main__":
    demo()

