#!/usr/bin/env python3
"""
推荐系统 - 多路召回 + 精排
依赖: pip install numpy pandas scikit-learn implicit faiss-cpu torch
"""
import hashlib
import logging
import pickle
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import faiss
import implicit
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from scipy.sparse import csr_matrix
from sklearn.preprocessing import LabelEncoder, MinMaxScaler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Recommender")

# ─── 数据类型 ─────────────────────────────────────────────
@dataclass
class Item:
    item_id: str
    title: str
    category: str
    tags: list[str] = field(default_factory=list)
    embedding: Optional[np.ndarray] = None
    popularity: float = 0.0

@dataclass
class UserProfile:
    user_id: str
    age: int = 0
    gender: str = ""
    interests: list[str] = field(default_factory=list)
    recent_items: list[str] = field(default_factory=list)
    embedding: Optional[np.ndarray] = None

# ─── 特征工程 ─────────────────────────────────────────────
class FeatureEngineer:
    """特征处理：类别编码、分桶、归一化、交叉特征"""

    def __init__(self):
        self.encoders: dict[str, LabelEncoder] = {}
        self.scaler = MinMaxScaler()

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        features = df.copy()

        # 类别特征编码
        for col in ['gender', 'category', 'city']:
            if col in features.columns:
                le = LabelEncoder()
                features[f'{col}_encoded'] = le.fit_transform(features[col].astype(str))
                self.encoders[col] = le

        # 数值特征分桶
        if 'age' in features.columns:
            features['age_bucket'] = pd.cut(
                features['age'],
                bins=[0, 18, 25, 35, 45, 60, 100],
                labels=[0, 1, 2, 3, 4, 5]
            ).astype(int)

        # 时间特征
        if 'timestamp' in features.columns:
            features['hour'] = pd.to_datetime(features['timestamp']).dt.hour
            features['dayofweek'] = pd.to_datetime(features['timestamp']).dt.dayofweek
            features['is_weekend'] = features['dayofweek'].isin([5, 6]).astype(int)

        # 交叉特征
        if 'category' in features.columns and 'gender' in features.columns:
            features['cat_gender'] = features['category'] + '_' + features['gender']

        # 统计特征
        if 'user_id' in features.columns and 'item_id' in features.columns:
            user_stats = features.groupby('user_id').agg(
                user_click_count=('item_id', 'count'),
                user_distinct_items=('item_id', 'nunique'),
                user_avg_rating=('rating', 'mean'),
            )
            features = features.merge(user_stats, on='user_id', how='left')

            item_stats = features.groupby('item_id').agg(
                item_click_count=('user_id', 'count'),
                item_avg_rating=('rating', 'mean'),
            )
            features = features.merge(item_stats, on='item_id', how='left')

        return features

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        features = df.copy()
        for col, le in self.encoders.items():
            if col in features.columns:
                features[f'{col}_encoded'] = le.transform(features[col].astype(str))
        return features

# ─── 召回层 ───────────────────────────────────────────────
class RecallLayer:
    """多路召回融合"""

    def __init__(self, items: list[Item]):
        self.items = {item.item_id: item for item in items}
        self.als_model = None
        self.vector_index = None
        self.item_id_to_idx: dict[str, int] = {}

    # ─── ALS 协同过滤召回 ─────────────────────────────────
    def train_als(self, interactions: pd.DataFrame):
        """训练 ALS 矩阵分解模型"""
        # 构建稀疏矩阵
        user_encoder = LabelEncoder()
        item_encoder = LabelEncoder()

        user_idx = user_encoder.fit_transform(interactions['user_id'])
        item_idx = item_encoder.fit_transform(interactions['item_id'])
        ratings = interactions['rating'].values

        self.item_id_to_idx = dict(zip(item_encoder.classes_, range(len(item_encoder.classes_))))

        sparse_matrix = csr_matrix(
            (ratings, (user_idx, item_idx)),
            shape=(len(user_encoder.classes_), len(item_encoder.classes_))
        )

        # ALS 训练
        self.als_model = implicit.als.AlternatingLeastSquares(
            factors=128,
            regularization=0.01,
            iterations=20,
        )
        self.als_model.fit(sparse_matrix)

        # 构建 Faiss 向量索引
        item_factors = self.als_model.item_factors.astype(np.float32)
        self.vector_index = faiss.IndexFlatIP(item_factors.shape[1])  # 内积相似度
        self.vector_index.add(item_factors)

        logger.info(f"ALS trained: {len(user_encoder.classes_)} users, {len(item_encoder.classes_)} items")

    def recall_als(self, user_id: int, top_k: int = 100) -> list[str]:
        """基于 ALS 用户向量召回"""
        if not self.als_model or not self.vector_index:
            return []

        # 获取用户向量
        user_factor = self.als_model.user_factors[user_id].astype(np.float32).reshape(1, -1)

        # Faiss 向量检索
        scores, indices = self.vector_index.search(user_factor, top_k)

        # idx 转 item_id
        idx_to_id = {v: k for k, v in self.item_id_to_idx.items()}
        return [idx_to_id[idx] for idx in indices[0] if idx in idx_to_id]

    # ─── 热度召回 ─────────────────────────────────────────
    def recall_hot(self, top_k: int = 20) -> list[str]:
        """基于热度的召回"""
        sorted_items = sorted(
            self.items.values(),
            key=lambda x: x.popularity,
            reverse=True,
        )
        return [item.item_id for item in sorted_items[:top_k]]

    # ─── 内容向量召回（基于 item embedding） ───────────────
    def build_content_index(self):
        """构建 item 内容向量 Faiss 索引"""
        embeddings = []
        id_to_idx = {}

        for i, item in enumerate(self.items.values()):
            if item.embedding is not None:
                embeddings.append(item.embedding.astype(np.float32))
                id_to_idx[item.item_id] = i

        if not embeddings:
            return

        emb_matrix = np.array(embeddings)
        self.content_index = faiss.IndexFlatIP(emb_matrix.shape[1])
        self.content_index.add(emb_matrix)
        self.content_id_to_idx = id_to_idx
        self.content_idx_to_id = {v: k for k, v in id_to_idx.items()}

    def recall_content(self, user_embedding: np.ndarray, top_k: int = 50) -> list[str]:
        """基于用户偏好的内容召回"""
        if not hasattr(self, 'content_index'):
            return []

        user_vec = user_embedding.astype(np.float32).reshape(1, -1)
        _, indices = self.content_index.search(user_vec, top_k)

        return [
            self.content_idx_to_id[idx]
            for idx in indices[0]
            if idx in self.content_idx_to_id
        ]

    # ─── 多路融合 ─────────────────────────────────────────
    def multi_recall(
        self,
        user_id: Optional[int] = None,
        user_embedding: Optional[np.ndarray] = None,
        als_k: int = 100,
        hot_k: int = 30,
        content_k: int = 50,
    ) -> list[str]:
        """融合多路召回结果"""
        candidates = []

        # ALS 召回
        if user_id is not None and self.als_model:
            candidates.extend(self.recall_als(user_id, als_k))

        # 内容召回
        if user_embedding is not None:
            candidates.extend(self.recall_content(user_embedding, content_k))

        # 热度召回（冷启动兜底）
        candidates.extend(self.recall_hot(hot_k))

        # 去重
        seen = set()
        unique = []
        for item_id in candidates:
            if item_id not in seen:
                seen.add(item_id)
                unique.append(item_id)

        return unique

# ─── 精排层: DeepFM ───────────────────────────────────────
class DeepFM(nn.Module):
    """DeepFM: FM 线性部分 + DNN 深层部分"""

    def __init__(
        self,
        feature_sizes: dict[str, int],  # 每类特征的 cardinality
        embedding_dim: int = 16,
        hidden_dims: list[int] = [256, 128, 64],
        dropout: float = 0.2,
    ):
        super().__init__()

        # Embedding 层
        self.embeddings = nn.ModuleDict({
            name: nn.Embedding(size, embedding_dim)
            for name, size in feature_sizes.items()
        })

        # DNN 深层部分
        total_embed_dim = len(feature_sizes) * embedding_dim
        layers = []
        input_dim = total_embed_dim
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(input_dim, hidden_dim))
            layers.append(nn.BatchNorm1d(hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            input_dim = hidden_dim
        self.dnn = nn.Sequential(*layers)

        # FM 一阶部分
        self.linear = nn.ModuleDict({
            name: nn.Embedding(size, 1)
            for name, size in feature_sizes.items()
        })

        # 输出层
        self.output = nn.Linear(hidden_dims[-1] + 1, 1)

    def forward(self, features: dict[str, torch.Tensor]) -> torch.Tensor:
        """features: { 'user_id': tensor, 'item_id': tensor, 'category': tensor, ... }"""

        # Embedding 向量
        embed_vectors = [
            self.embeddings[name](features[name])
            for name in features
        ]
        embed_concat = torch.cat(embed_vectors, dim=1)  # [batch, n_feat*emb_dim]

        # FM 一阶
        fm_first = sum(
            self.linear[name](features[name])
            for name in features
        )  # [batch, 1]

        # FM 二阶交叉
        embed_stack = torch.stack(embed_vectors, dim=1)  # [batch, n_feat, emb_dim]
        sum_square = embed_stack.sum(dim=1).pow(2)        # [batch, emb_dim]
        square_sum = embed_stack.pow(2).sum(dim=1)        # [batch, emb_dim]
        fm_second = 0.5 * (sum_square - square_sum).sum(dim=1, keepdim=True)  # [batch, 1]

        # DNN 深层
        dnn_out = self.dnn(embed_concat)  # [batch, hidden_dim]

        # 组合输出
        combined = torch.cat([dnn_out, fm_first + fm_second], dim=1)
        logit = self.output(combined)
        return torch.sigmoid(logit).squeeze(-1)

    def predict(self, features: dict[str, torch.Tensor]) -> np.ndarray:
        """推理预测（返回 numpy 数组）"""
        self.eval()
        with torch.no_grad():
            return self.forward(features).cpu().numpy()

# ─── 完整的推荐管线 ───────────────────────────────────────
class RecommendationPipeline:
    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.recall_layer: Optional[RecallLayer] = None
        self.rank_model: Optional[DeepFM] = None
        self.items: dict[str, Item] = {}
        self.users: dict[str, UserProfile] = {}

    def load_data(self, items_df: pd.DataFrame, interactions_df: pd.DataFrame):
        """加载数据并初始化"""
        # 解析 items
        for _, row in items_df.iterrows():
            self.items[row['item_id']] = Item(
                item_id=row['item_id'],
                title=row['title'],
                category=row.get('category', ''),
                tags=row.get('tags', '').split(',') if 'tags' in row else [],
            )

        # 初始化召回层
        self.recall_layer = RecallLayer(list(self.items.values()))
        self.recall_layer.train_als(interactions_df)

        # 特征工程
        self.features_df = self.feature_engineer.fit_transform(interactions_df)

    def train_rank_model(self, train_df: pd.DataFrame, epochs: int = 10):
        """训练精排模型"""
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # 确定特征维度
        feature_sizes = {}
        for col in ['user_id', 'item_id', 'category_encoded', 'gender_encoded', 'age_bucket', 'hour', 'dayofweek']:
            if col in train_df.columns:
                feature_sizes[col] = train_df[col].nunique() + 1

        self.rank_model = DeepFM(feature_sizes).to(device)
        optimizer = torch.optim.Adam(self.rank_model.parameters(), lr=0.001)
        criterion = nn.BCELoss()

        for epoch in range(epochs):
            self.rank_model.train()
            total_loss = 0

            # Mini-batch 训练
            batch_size = 256
            indices = np.random.permutation(len(train_df))

            for start in range(0, len(indices), batch_size):
                batch_idx = indices[start:start + batch_size]
                batch = train_df.iloc[batch_idx]

                features = {
                    name: torch.tensor(batch[name].values, dtype=torch.long, device=device)
                    for name in feature_sizes
                }
                labels = torch.tensor(batch['label'].values, dtype=torch.float32, device=device)

                optimizer.zero_grad()
                preds = self.rank_model(features)
                loss = criterion(preds, labels)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            logger.info(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss:.4f}")

    def recommend(self, user_id: str, top_k: int = 20) -> list[dict]:
        """推荐主流程"""
        # 1. 多路召回
        user_profile = self.users.get(user_id)
        candidate_ids = self.recall_layer.multi_recall(
            user_embedding=user_profile.embedding if user_profile else None,
        )

        # 2. 构造特征
        candidates = [self.items[cid] for cid in candidate_ids if cid in self.items]
        if not candidates:
            return []

        # 3. 精排打分
        batch_features = {
            'item_id': torch.tensor([hash(c.item_id) % 10000 for c in candidates]),
            'category_encoded': torch.tensor([hash(c.category) % 1000 for c in candidates]),
        }

        if self.rank_model:
            scores = self.rank_model.predict(batch_features)
        else:
            scores = np.array([item.popularity for item in candidates])

        # 4. 排序 & 多样性重排
        ranked = sorted(
            zip(candidates, scores), key=lambda x: x[1], reverse=True
        )

        # 简单 MMR 多样性重排
        results = self._mmr_rerank(ranked, top_k, lambda_param=0.7)

        return [
            {
                "item_id": item.item_id,
                "title": item.title,
                "category": item.category,
                "score": float(score),
            }
            for item, score in results
        ]

    def _mmr_rerank(
        self,
        ranked: list[tuple[Item, float]],
        top_k: int,
        lambda_param: float = 0.7,
    ) -> list[tuple[Item, float]]:
        """MMR 多样性重排"""
        if not ranked:
            return []

        selected = [ranked[0]]
        remaining = ranked[1:]

        while len(selected) < top_k and remaining:
            mmr_scores = []
            for item, score in remaining:
                relevance = score
                # 多样性（与已选商品类别的差异）
                categories = {s[0].category for s in selected}
                similarity = 1.0 if item.category in categories else 0.0
                mmr = lambda_param * relevance - (1 - lambda_param) * similarity
                mmr_scores.append(mmr)

            best_idx = np.argmax(mmr_scores)
            selected.append(remaining.pop(best_idx))

        return selected
