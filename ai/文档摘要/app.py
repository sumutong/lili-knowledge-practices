#!/usr/bin/env python3
"""
多格式文档智能摘要系统
依赖: pip install pypdf docx2txt sumy langchain openai tiktoken transformers torch
"""
import hashlib
import logging
import os
import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import tiktoken
from openai import OpenAI
from sumy.nlp.stemmers import Stemmer
from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lex_rank import LexRankSummarizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.summarizers.text_rank import TextRankSummarizer
from sumy.utils import get_stop_words
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DocumentSummarizer")

# ─── 配置 ─────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-xxx")
LLM_MODEL = "gpt-4o-mini"
LANGUAGE = "chinese"

@dataclass
class SummaryResult:
    title: str
    summary: str
    key_points: list[str]
    method: str
    original_length: int
    summary_length: int
    compression_ratio: float
    processing_time: float

# ─── 文档加载器 ───────────────────────────────────────────
class DocumentLoader:
    """多格式文档加载"""

    @staticmethod
    def load(file_path: str) -> str:
        ext = Path(file_path).suffix.lower()

        if ext == '.pdf':
            return DocumentLoader._load_pdf(file_path)
        elif ext in ['.docx', '.doc']:
            return DocumentLoader._load_docx(file_path)
        elif ext in ['.md', '.markdown']:
            return DocumentLoader._load_markdown(file_path)
        elif ext == '.txt':
            return DocumentLoader._load_text(file_path)
        else:
            raise ValueError(f"Unsupported format: {ext}")

    @staticmethod
    def _load_pdf(path: str) -> str:
        from pypdf import PdfReader
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    @staticmethod
    def _load_docx(path: str) -> str:
        import docx2txt
        return docx2txt.process(path)

    @staticmethod
    def _load_markdown(path: str) -> str:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    @staticmethod
    def _load_text(path: str) -> str:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

# ─── 文本预处理 ───────────────────────────────────────────
class TextPreprocessor:
    """文本清洗与分句"""

    @staticmethod
    def clean(text: str) -> str:
        """清洗文本"""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除特殊字符（保留必要标点）
        text = re.sub(r'[^\w\s.,!?;:，。！？；：\-\n]', '', text)
        return text.strip()

    @staticmethod
    def split_sentences(text: str, lang: str = "chinese") -> list[str]:
        """分句"""
        if lang == "chinese":
            # 中文分句
            sentences = re.split(r'(?<=[。！？；\n])\s*', text)
        else:
            # 英文分句
            sentences = re.split(r'(?<=[.!?])\s+', text)

        return [s.strip() for s in sentences if len(s.strip()) > 5]

    @staticmethod
    def split_paragraphs(text: str) -> list[str]:
        """分段"""
        paragraphs = text.split('\n\n')
        return [p.strip() for p in paragraphs if len(p.strip()) > 10]

# ─── 抽取式摘要 ───────────────────────────────────────────
class ExtractiveSummarizer:
    """抽取式摘要：TextRank / LexRank / LSA / TF-IDF"""

    def __init__(self, language: str = "chinese"):
        self.language = language

    def textrank(self, text: str, num_sentences: int = 5) -> list[str]:
        """TextRank 摘要"""
        try:
            parser = PlaintextParser.from_string(text, Tokenizer(self.language))
            stemmer = Stemmer(self.language)
            summarizer = TextRankSummarizer(stemmer)
            summarizer.stop_words = get_stop_words(self.language)
            summary_sentences = summarizer(parser.document, num_sentences)
            return [str(s) for s in summary_sentences]
        except Exception as e:
            logger.warning(f"TextRank failed: {e}, falling back to TF-IDF")
            return self.tfidf(text, num_sentences)

    def lexrank(self, text: str, num_sentences: int = 5) -> list[str]:
        """LexRank 摘要"""
        parser = PlaintextParser.from_string(text, Tokenizer(self.language))
        summarizer = LexRankSummarizer()
        summarizer.stop_words = get_stop_words(self.language)
        return [str(s) for s in summarizer(parser.document, num_sentences)]

    def lsa(self, text: str, num_sentences: int = 5) -> list[str]:
        """LSA (Latent Semantic Analysis) 摘要"""
        parser = PlaintextParser.from_string(text, Tokenizer(self.language))
        summarizer = LsaSummarizer()
        summarizer.stop_words = get_stop_words(self.language)
        return [str(s) for s in summarizer(parser.document, num_sentences)]

    def tfidf(self, text: str, num_sentences: int = 5) -> list[str]:
        """基于 TF-IDF 的关键句抽取"""
        sentences = TextPreprocessor.split_sentences(text)
        if len(sentences) <= num_sentences:
            return sentences

        vectorizer = TfidfVectorizer()
        try:
            tfidf_matrix = vectorizer.fit_transform(sentences)
            # 每句的平均 TF-IDF 分数
            scores = np.array(tfidf_matrix.sum(axis=1)).flatten()
            top_indices = np.argsort(scores)[-num_sentences:]
            # 保持原文顺序
            top_indices = sorted(top_indices)
            return [sentences[i] for i in top_indices]
        except Exception:
            return sentences[:num_sentences]

    def mmr(
        self, text: str, num_sentences: int = 5, lambda_param: float = 0.7
    ) -> list[str]:
        """MMR (Maximal Marginal Relevance) 多样性摘要"""
        sentences = TextPreprocessor.split_sentences(text)
        if len(sentences) <= num_sentences:
            return sentences

        # TF-IDF 向量
        vectorizer = TfidfVectorizer()
        tfidf = vectorizer.fit_transform(sentences).toarray()

        # 计算相似度矩阵
        sim_matrix = cosine_similarity(tfidf)

        # 每句的相关性分数（中心度）
        relevance = sim_matrix.mean(axis=1)

        selected = []
        remaining = list(range(len(sentences)))

        # 选第一个（相关性最高）
        first = int(np.argmax(relevance))
        selected.append(first)
        remaining.remove(first)

        for _ in range(num_sentences - 1):
            mmr_scores = []
            for idx in remaining:
                rel = relevance[idx]
                # 与已选句子的最大相似度
                sim_to_selected = max(sim_matrix[idx][s] for s in selected) if selected else 0
                mmr = lambda_param * rel - (1 - lambda_param) * sim_to_selected
                mmr_scores.append((idx, mmr))

            best_idx = max(mmr_scores, key=lambda x: x[1])[0]
            selected.append(best_idx)
            remaining.remove(best_idx)

        return [sentences[i] for i in sorted(selected)]

# ─── 生成式摘要（LLM） ────────────────────────────────────
class GenerativeSummarizer:
    """基于 LLM 的生成式摘要"""

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.encoder = tiktoken.encoding_for_model(LLM_MODEL)

    def summarize(self, text: str, max_summary_length: int = 500) -> str:
        """单次摘要（适合短文档）"""
        # 如果文本过长，先截断
        tokens = self.encoder.encode(text)
        if len(tokens) > 14000:
            text = self.encoder.decode(tokens[:14000])

        response = self.client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "system",
                "content": f"""你是一个专业文档摘要助手。请生成一份简洁、准确的摘要。
要求：
1. 控制摘要长度在 {max_summary_length} 字以内
2. 保留原文核心观点和关键数据
3. 使用原文语言（中文输出中文，英文输出英文）
4. 结构清晰，必要时使用要点列表
5. 不添加原文没有的内容""",
            }, {
                "role": "user",
                "content": f"请总结以下文档：\n\n{text}",
            }],
            temperature=0.3,
            max_tokens=max_summary_length,
        )
        return response.choices[0].message.content.strip()

    def map_reduce_summarize(
        self, text: str, chunk_size: int = 8000, chunk_overlap: int = 500
    ) -> str:
        """Map-Reduce 长文档摘要"""

        # 1. Map: 分块摘要
        chunks = self._split_text(text, chunk_size, chunk_overlap)
        logger.info(f"Split into {len(chunks)} chunks")

        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Summarizing chunk {i+1}/{len(chunks)}")
            summary = self.summarize(chunk, max_summary_length=300)
            chunk_summaries.append(summary)

        # 2. Reduce: 合并摘要
        combined = "\n---\n".join(chunk_summaries)
        final_summary = self.summarize(combined, max_summary_length=1000)

        return final_summary

    def refine_summarize(self, text: str, chunk_size: int = 8000) -> str:
        """Refine 方法：逐步精炼摘要"""
        chunks = self._split_text(text, chunk_size, 0)
        summary = ""

        for chunk in chunks:
            summary = self._refine_summary(summary, chunk)

        return summary

    def _refine_summary(self, existing_summary: str, new_text: str) -> str:
        """用新文本精炼已有摘要"""
        if not existing_summary:
            return self.summarize(new_text)

        response = self.client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "system",
                "content": "根据新增内容，精炼和更新已有摘要。保留所有重要信息。",
            }, {
                "role": "user",
                "content": f"已有摘要:\n{existing_summary}\n\n新增内容:\n{new_text}\n\n请输出更新后的摘要：",
            }],
            temperature=0.3,
            max_tokens=800,
        )
        return response.choices[0].message.content.strip()

    def extract_key_points(self, text: str, num_points: int = 5) -> list[str]:
        """提取关键要点"""
        response = self.client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "system",
                "content": f"从文档中提取最重要的 {num_points} 个关键要点。每个要点一行，以 '- ' 开头。",
            }, {
                "role": "user",
                "content": text[:14000],
            }],
            temperature=0.1,
            max_tokens=500,
        )

        content = response.choices[0].message.content
        points = re.findall(r'[-*]\s*(.+)', content)
        return points[:num_points] if points else [content]

    def _split_text(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        """按 Token 数分块"""
        tokens = self.encoder.encode(text)
        chunks = []

        start = 0
        while start < len(tokens):
            end = start + chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoder.decode(chunk_tokens)
            chunks.append(chunk_text)
            start = end - overlap

        return chunks

# ─── 层级摘要器 ───────────────────────────────────────────
class HierarchicalSummarizer:
    """层级摘要：先提取段落要点，再汇总摘要"""

    def __init__(self):
        self.gen = GenerativeSummarizer()

    def summarize(self, text: str) -> str:
        """层级摘要流程"""
        paragraphs = TextPreprocessor.split_paragraphs(text)
        logger.info(f"Processing {len(paragraphs)} paragraphs")

        # 第一层：每个段落生成一句话摘要
        para_summaries = []
        for para in paragraphs:
            if len(para) < 100:
                para_summaries.append(para)
                continue

            summary = self.gen.summarize(
                f"用一句话总结以下段落的核心内容：\n\n{para}",
                max_summary_length=100,
            )
            para_summaries.append(summary)

        # 第二层：汇总所有段落摘要
        combined = "\n".join(para_summaries)
        final_summary = self.gen.summarize(combined, max_summary_length=800)

        return final_summary

# ─── 文档摘要管线 ─────────────────────────────────────────
class DocumentSummaryPipeline:
    """完整的文档摘要管线"""

    def __init__(self):
        self.loader = DocumentLoader()
        self.preprocessor = TextPreprocessor()
        self.extractive = ExtractiveSummarizer()
        self.generative = GenerativeSummarizer()
        self.hierarchical = HierarchicalSummarizer()

    def process(
        self,
        file_path: str,
        method: str = "auto",  # extractive / generative / hybrid / auto
        num_sentences: int = 10,
    ) -> SummaryResult:
        """处理文档并生成摘要"""
        import time
        start_time = time.time()

        # 加载文档
        text = self.loader.load(file_path)
        cleaned = self.preprocessor.clean(text)
        title = Path(file_path).stem

        if method == "auto":
            # 自动选择方法：短文档用生成式，长文档用混合
            tokens = tiktoken.encoding_for_model(LLM_MODEL).encode(cleaned)
            method = "generative" if len(tokens) < 8000 else "hybrid"

        logger.info(f"Summarizing '{title}' ({len(cleaned)} chars) using {method}")

        # 生成摘要
        if method == "extractive":
            summary_sentences = self.extractive.textrank(cleaned, num_sentences)
            summary = "".join(summary_sentences)
            key_points = summary_sentences[:5]

        elif method == "generative":
            if len(cleaned) > 30000:
                summary = self.generative.map_reduce_summarize(cleaned)
            else:
                summary = self.generative.summarize(cleaned)
            key_points = self.generative.extract_key_points(cleaned)

        elif method == "hybrid":
            # 混合方法：抽取式粗筛 + 生成式精炼
            extract_sentences = self.extractive.textrank(cleaned, num_sentences=30)
            merged = "".join(extract_sentences)
            summary = self.generative.summarize(merged)
            key_points = self.generative.extract_key_points(merged)

        elif method == "hierarchical":
            summary = self.hierarchical.summarize(cleaned)
            key_points = self.generative.extract_key_points(cleaned)

        else:
            raise ValueError(f"Unknown method: {method}")

        elapsed = time.time() - start_time

        return SummaryResult(
            title=title,
            summary=summary,
            key_points=key_points,
            method=method,
            original_length=len(cleaned),
            summary_length=len(summary),
            compression_ratio=len(summary) / max(len(cleaned), 1),
            processing_time=elapsed,
        )

# ─── 使用示例 ─────────────────────────────────────────────
if __name__ == "__main__":
    pipeline = DocumentSummaryPipeline()

    result = pipeline.process("document.pdf", method="hybrid")

    print(f"\n{'='*60}")
    print(f"文档: {result.title}")
    print(f"方法: {result.method}")
    print(f"压缩比: {result.compression_ratio:.1%}")
    print(f"耗时: {result.processing_time:.1f}s")
    print(f"{'='*60}\n")
    print("📝 摘要:\n")
    print(result.summary)
    print(f"\n🔑 关键要点:")
    for p in result.key_points:
        print(f"  • {p}")
