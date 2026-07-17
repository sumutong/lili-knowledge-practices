#!/usr/bin/env python3
"""
多维时序异常检测系统
依赖: pip install numpy pandas scikit-learn torch matplotlib plotly
"""
import json
import logging
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnomalyDetection")

# ─── 数据类型 ─────────────────────────────────────────────
class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class Anomaly:
    timestamp: datetime
    metric: str
    value: float
    expected: float
    deviation: float  # 偏离程度（标准差倍数）
    level: AlertLevel
    method: str
    score: float

# ─── 统计方法 ─────────────────────────────────────────────
class StatisticalDetector:
    """统计异常检测：3-Sigma + IQR + 移动平均"""

    def __init__(self, window_size: int = 100, sigma_threshold: float = 3.0):
        self.window_size = window_size
        self.sigma_threshold = sigma_threshold
        self.history: dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))

    def detect_3sigma(self, metric: str, value: float) -> Optional[Anomaly]:
        """3-Sigma 异常检测"""
        data = self.history[metric]
        data.append(value)

        if len(data) < 30:  # 数据不足
            return None

        arr = np.array(data)
        mean = np.mean(arr)
        std = np.std(arr)

        if std == 0:
            return None

        z_score = abs(value - mean) / std
        if z_score > self.sigma_threshold:
            return Anomaly(
                timestamp=datetime.now(),
                metric=metric,
                value=value,
                expected=mean,
                deviation=z_score,
                level=AlertLevel.CRITICAL if z_score > 5 else AlertLevel.WARNING,
                method="3-sigma",
                score=float(z_score),
            )
        return None

    def detect_iqr(self, metric: str, value: float, multiplier: float = 1.5) -> Optional[Anomaly]:
        """IQR (四分位距) 异常检测"""
        data = list(self.history[metric])
        if len(data) < 30:
            return None

        q1 = np.percentile(data, 25)
        q3 = np.percentile(data, 75)
        iqr = q3 - q1
        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr

        if value < lower or value > upper:
            deviation = min(abs(value - lower), abs(value - upper)) / (iqr + 1e-8)
            return Anomaly(
                timestamp=datetime.now(),
                metric=metric,
                value=value,
                expected=(q1 + q3) / 2,
                deviation=deviation,
                level=AlertLevel.WARNING if deviation < 3 else AlertLevel.CRITICAL,
                method="IQR",
                score=deviation,
            )
        return None

    def detect_change_point(self, metric: str, value: float, window: int = 30) -> Optional[Anomaly]:
        """变点检测：滑动窗口均值突变"""
        data = list(self.history[metric])
        if len(data) < window * 2:
            return None

        prev_window = np.mean(data[-window*2:-window])
        curr_window = np.mean(data[-window:])

        if prev_window == 0:
            return None

        change_rate = abs(curr_window - prev_window) / abs(prev_window)
        if change_rate > 0.3:  # 30% 变化
            return Anomaly(
                timestamp=datetime.now(),
                metric=metric,
                value=value,
                expected=prev_window,
                deviation=change_rate,
                level=AlertLevel.WARNING,
                method="change-point",
                score=change_rate,
            )
        return None

# ─── 机器学习方法 ─────────────────────────────────────────
class MLDetector:
    """机器学习异常检测"""

    def __init__(self):
        self.if_model = IsolationForest(
            n_estimators=100,
            contamination=0.05,  # 预期异常比例
            random_state=42,
        )
        self.lof_model = LocalOutlierFactor(
            n_neighbors=20,
            contamination=0.05,
            novelty=True,
        )
        self.scaler = StandardScaler()
        self.is_trained = False

    def train(self, data: np.ndarray):
        """训练模型"""
        # data: [n_samples, n_features]
        scaled = self.scaler.fit_transform(data)

        self.if_model.fit(scaled)

        # LOF 需要部分正常数据先 fit
        normal_mask = self.if_model.predict(scaled) == 1
        if normal_mask.sum() > 20:
            self.lof_model.fit(scaled[normal_mask])
        else:
            self.lof_model.fit(scaled)

        self.is_trained = True
        logger.info(f"ML models trained on {len(data)} samples")

    def detect(self, features: np.ndarray) -> dict[str, Any]:
        """检测异常"""
        if not self.is_trained:
            return {"isolation_forest": 1, "lof": 1, "score": 0.0}

        scaled = self.scaler.transform(features.reshape(1, -1))

        # Isolation Forest
        if_pred = self.if_model.predict(scaled)[0]  # 1=normal, -1=anomaly
        if_score = -self.if_model.score_samples(scaled)[0]  # 越小越异常

        # LOF
        lof_pred = self.lof_model.predict(scaled)[0]
        lof_score = -self.lof_model.score_samples(scaled)[0]

        # 综合分数
        combined_score = (if_score + lof_score) / 2

        return {
            "isolation_forest": int(if_pred),
            "lof": int(lof_pred),
            "score": float(combined_score),
            "is_anomaly": if_pred == -1 or lof_pred == -1,
        }

# ─── 深度学习方法: LSTM-Autoencoder ──────────────────────
class LSTMAutoencoder(nn.Module):
    """LSTM 自编码器用于时序异常检测"""

    def __init__(self, input_dim: int, hidden_dim: int = 64, latent_dim: int = 16):
        super().__init__()

        # Encoder
        self.encoder_lstm = nn.LSTM(
            input_dim, hidden_dim, batch_first=True, bidirectional=True
        )
        self.encoder_fc = nn.Linear(hidden_dim * 2, latent_dim)

        # Decoder
        self.decoder_fc = nn.Linear(latent_dim, hidden_dim * 2)
        self.decoder_lstm = nn.LSTM(
            hidden_dim * 2, hidden_dim, batch_first=True, bidirectional=True
        )
        self.output_fc = nn.Linear(hidden_dim * 2, input_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [batch, seq_len, input_dim]
        返回: [batch, seq_len, input_dim]
        """
        batch_size, seq_len, _ = x.shape

        # Encode
        enc_out, (h_n, c_n) = self.encoder_lstm(x)
        latent = self.encoder_fc(enc_out[:, -1, :])  # 取最后时刻

        # Decode
        latent_expanded = latent.unsqueeze(1).repeat(1, seq_len, 1)
        dec_in = self.decoder_fc(latent_expanded)
        dec_out, _ = self.decoder_lstm(dec_in)
        reconstructed = self.output_fc(dec_out)

        return reconstructed

    def anomaly_score(self, x: torch.Tensor) -> np.ndarray:
        """计算每个点的异常分数（重构误差）"""
        self.eval()
        with torch.no_grad():
            recon = self.forward(x)
            # MSE 在每个时间步
            mse = torch.mean((x - recon) ** 2, dim=2)  # [batch, seq_len]
            return mse.cpu().numpy()

class DeepDetector:
    """深度学习异常检测"""

    def __init__(self, input_dim: int, seq_len: int = 60, threshold_percentile: float = 95):
        self.model = LSTMAutoencoder(input_dim)
        self.seq_len = seq_len
        self.threshold_percentile = threshold_percentile
        self.scaler = StandardScaler()
        self.threshold: Optional[float] = None

    def train(self, data: np.ndarray, epochs: int = 50, batch_size: int = 32):
        """
        data: [n_samples, n_features]
        使用滑动窗口构造序列
        """
        scaled = self.scaler.fit_transform(data)

        # 构造序列
        sequences = []
        for i in range(len(scaled) - self.seq_len + 1):
            sequences.append(scaled[i:i+self.seq_len])

        if not sequences:
            logger.warning("Not enough data for sequence generation")
            return

        X = torch.tensor(np.array(sequences), dtype=torch.float32)
        dataset = torch.utils.data.TensorDataset(X)
        loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        criterion = nn.MSELoss()

        self.model.train()
        for epoch in range(epochs):
            total_loss = 0
            for batch_x, in loader:
                optimizer.zero_grad()
                recon = self.model(batch_x)
                loss = criterion(recon, batch_x)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(loader):.4f}")

        # 计算阈值（基于训练集重构误差）
        self.model.eval()
        with torch.no_grad():
            all_errors = []
            for batch_x, in loader:
                errors = self.model.anomaly_score(batch_x)
                all_errors.extend(errors.flatten().tolist())

            self.threshold = np.percentile(all_errors, self.threshold_percentile)
            logger.info(f"Anomaly threshold: {self.threshold:.4f}")

    def detect(self, sequence: np.ndarray) -> dict:
        """检测单个序列是否异常"""
        scaled = self.scaler.transform(sequence.reshape(1, -1)) if len(sequence.shape) == 1 \
                 else self.scaler.transform(sequence)

        x = torch.tensor(scaled, dtype=torch.float32).unsqueeze(0)  # [1, seq_len, dim]
        errors = self.model.anomaly_score(x)

        max_error = float(errors.max())
        is_anomaly = max_error > self.threshold if self.threshold else False

        return {
            "score": max_error,
            "threshold": self.threshold,
            "is_anomaly": is_anomaly,
            "error_curve": errors[0].tolist(),
        }

# ─── 根因分析 ─────────────────────────────────────────────
class RootCauseAnalyzer:
    """简单的根因分析：找偏差最大的维度"""

    def __init__(self, metric_names: list[str]):
        self.metric_names = metric_names

    def analyze(
        self, current: np.ndarray, expected: np.ndarray
    ) -> list[dict]:
        """
        current: 当前多维数据点
        expected: 预期值（历史均值 / 预测值）
        """
        deviations = []
        for i, name in enumerate(self.metric_names):
            if expected[i] == 0:
                continue
            dev = abs(current[i] - expected[i]) / (abs(expected[i]) + 1e-8)
            deviations.append({
                "metric": name,
                "current": float(current[i]),
                "expected": float(expected[i]),
                "deviation": float(dev),
            })

        # 按偏离程度排序
        deviations.sort(key=lambda x: x["deviation"], reverse=True)
        return deviations

# ─── 异常检测管线 ─────────────────────────────────────────
class AnomalyDetectionPipeline:
    """完整的异常检测管线"""

    def __init__(self, metric_names: list[str]):
        self.metric_names = metric_names
        self.stat = StatisticalDetector(window_size=200)
        self.ml = MLDetector()
        self.deep = DeepDetector(input_dim=len(metric_names))
        self.rca = RootCauseAnalyzer(metric_names)

        self.anomaly_history: list[Anomaly] = []
        self.alert_callbacks = []

    def register_alert(self, callback):
        """注册告警回调"""
        self.alert_callbacks.append(callback)

    def process(self, metrics: dict[str, float]) -> list[Anomaly]:
        """
        处理单个数据点
        metrics: {'cpu': 0.85, 'memory': 0.72, 'disk_io': 120, ...}
        """
        anomalies = []

        # 1. 统计方法（逐个指标）
        for name, value in metrics.items():
            anomaly = self.stat.detect_3sigma(name, value)
            if anomaly:
                anomalies.append(anomaly)
                continue

            anomaly = self.stat.detect_iqr(name, value)
            if anomaly:
                anomalies.append(anomaly)
                continue

            anomaly = self.stat.detect_change_point(name, value)
            if anomaly:
                anomalies.append(anomaly)

        # 2. 多维 ML 检测
        feature_array = np.array([metrics[name] for name in self.metric_names])
        ml_result = self.ml.detect(feature_array)
        if ml_result["is_anomaly"]:
            anomalies.append(Anomaly(
                timestamp=datetime.now(),
                metric="__multidimensional__",
                value=0,
                expected=0,
                deviation=ml_result["score"],
                level=AlertLevel.WARNING,
                method="ml-ensemble",
                score=ml_result["score"],
            ))

        # 3. 触发告警
        for anomaly in anomalies:
            self.anomaly_history.append(anomaly)
            for callback in self.alert_callbacks:
                callback(anomaly)

        return anomalies

    def analyze_root_cause(self, current: dict[str, float]) -> list[dict]:
        """根因分析"""
        current_arr = np.array([current[n] for n in self.metric_names])
        expected_arr = np.array([
            np.mean(list(self.stat.history[n])) if self.stat.history[n] else 0
            for n in self.metric_names
        ])
        return self.rca.analyze(current_arr, expected_arr)

# ─── 告警处理器 ───────────────────────────────────────────
class AlertHandler:
    """告警去重、分级、通知"""

    def __init__(self, dedup_window: int = 300, escalation_time: int = 600):
        self.dedup_window = dedup_window  # 5 分钟内同类告警去重
        self.escalation_time = escalation_time  # 10 分钟内升级
        self.last_alert: dict[str, datetime] = {}
        self.alert_counts: dict[str, int] = defaultdict(int)

    def handle(self, anomaly: Anomaly):
        """处理告警"""
        key = f"{anomaly.metric}:{anomaly.method}"

        # 去重
        if key in self.last_alert:
            delta = (datetime.now() - self.last_alert[key]).total_seconds()
            if delta < self.dedup_window:
                return  # 去重，不重复发送

        self.last_alert[key] = datetime.now()
        self.alert_counts[key] += 1

        # 升级
        if self.alert_counts[key] > 5:
            anomaly.level = AlertLevel.CRITICAL

        # 通知
        logger.warning(
            f"[{anomaly.level.value.upper()}] {anomaly.metric} "
            f"value={anomaly.value:.2f} expected={anomaly.expected:.2f} "
            f"deviation={anomaly.deviation:.2f} method={anomaly.method}"
        )

        # 实际发送通知（钉钉/邮件/短信）
        if anomaly.level == AlertLevel.CRITICAL:
            self._send_urgent_notification(anomaly)

    def _send_urgent_notification(self, anomaly: Anomaly):
        """紧急通知"""
        # 钉钉机器人 Webhook
        import requests
        webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=xxx"
        message = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"🚨 严重异常: {anomaly.metric}",
                "text": (
                    f"## 🚨 严重异常告警\n\n"
                    f"- **指标**: {anomaly.metric}\n"
                    f"- **当前值**: {anomaly.value}\n"
                    f"- **预期值**: {anomaly.expected}\n"
                    f"- **偏离度**: {anomaly.deviation:.1f}σ\n"
                    f"- **检测方法**: {anomaly.method}\n"
                    f"- **时间**: {anomaly.timestamp}\n"
                ),
            },
        }
        try:
            requests.post(webhook_url, json=message, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
