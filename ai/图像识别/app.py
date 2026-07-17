#!/usr/bin/env python3
"""
商品图片分类 — 训练 + 推理部署
依赖: pip install torch torchvision fastapi uvicorn pillow python-multipart
"""
import io
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torch import amp
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR, SequentialLR
from torch.utils.data import DataLoader, Dataset, random_split
from torchvision import datasets, models, transforms
from torchvision.models import ResNet50_Weights

logging.basicConfig(level=logging.INFO)

# ─── 配置 ───────────────────────────────────────────────────
@dataclass
class TrainConfig:
    data_dir: str = "./data/products"
    num_classes: int = 101
    image_size: int = 224
    batch_size: int = 64
    epochs: int = 30
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    warmup_epochs: int = 3
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    num_workers: int = 4
    use_amp: bool = True  # 混合精度
    label_smoothing: float = 0.1

config = TrainConfig()

# ─── 数据增强 ───────────────────────────────────────────────
class AugmentedDataset(Dataset):
    """自定义数据集，支持更灵活的数据增强"""

    def __init__(self, data_dir: str, split: str = "train"):
        self.data_dir = Path(data_dir)
        self.split = split
        self.samples = self._load_samples()

        if split == "train":
            self.transform = transforms.Compose([
                transforms.RandomResizedCrop(config.image_size, scale=(0.7, 1.0)),
                transforms.RandomHorizontalFlip(p=0.5),
                transforms.RandomRotation(degrees=15),
                transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1),
                transforms.RandomAffine(degrees=0, translate=(0.1, 0.1)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                transforms.RandomErasing(p=0.3, scale=(0.02, 0.15)),
            ])
        else:
            self.transform = transforms.Compose([
                transforms.Resize(int(config.image_size * 1.14)),
                transforms.CenterCrop(config.image_size),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])

    def _load_samples(self):
        samples = []
        for class_dir in self.data_dir.iterdir():
            if not class_dir.is_dir():
                continue
            class_idx = int(class_dir.name) if class_dir.name.isdigit() else hash(class_dir.name) % config.num_classes
            for img_path in class_dir.glob("*"):
                if img_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                    samples.append((str(img_path), class_idx))
        return samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        try:
            image = Image.open(path).convert("RGB")
            return self.transform(image), label
        except Exception as e:
            logging.warning(f"加载图片失败 {path}: {e}")
            # 返回一个随机替代
            return torch.randn(3, 224, 224), label

# ─── 模型 ───────────────────────────────────────────────────
class ProductClassifier(nn.Module):
    """带标签平滑的分类器"""

    def __init__(self, num_classes: int, backbone: str = "resnet50"):
        super().__init__()
        if backbone == "resnet50":
            self.backbone = models.resnet50(weights=ResNet50_Weights.IMAGENET1K_V2)
            in_features = self.backbone.fc.in_features
            self.backbone.fc = nn.Identity()
        elif backbone == "efficientnet_b0":
            self.backbone = models.efficientnet_b0(weights="IMAGENET1K_V1")
            in_features = self.backbone.classifier[1].in_features
            self.backbone.classifier = nn.Identity()
        else:
            raise ValueError(f"不支持的 backbone: {backbone}")

        # 分类头
        self.head = nn.Sequential(
            nn.Linear(in_features, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes),
        )

    def forward(self, x):
        features = self.backbone(x)
        return self.head(features)

    def extract_features(self, x):
        """提取特征向量（用于相似搜索）"""
        return self.backbone(x)

# ─── 标签平滑损失 ───────────────────────────────────────────
class LabelSmoothingCrossEntropy(nn.Module):
    def __init__(self, smoothing: float = 0.1):
        super().__init__()
        self.smoothing = smoothing

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        n_classes = pred.size(-1)
        log_probs = F.log_softmax(pred, dim=-1)
        with torch.no_grad():
            true_dist = torch.zeros_like(log_probs)
            true_dist.fill_(self.smoothing / (n_classes - 1))
            true_dist.scatter_(1, target.unsqueeze(1), 1.0 - self.smoothing)
        return torch.mean(torch.sum(-true_dist * log_probs, dim=-1))

# ─── 训练器 ─────────────────────────────────────────────────
class Trainer:
    def __init__(self):
        self.model = ProductClassifier(config.num_classes).to(config.device)
        self.criterion = LabelSmoothingCrossEntropy(config.label_smoothing)
        self.optimizer = AdamW(
            self.model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )
        self.scaler = amp.GradScaler(enabled=config.use_amp)
        self.best_acc = 0.0
        self.metrics_history: list[dict] = []

    def train_epoch(self, loader: DataLoader, epoch: int):
        self.model.train()
        total_loss = 0.0
        correct = 0
        total = 0

        for batch_idx, (images, labels) in enumerate(loader):
            images, labels = images.to(config.device), labels.to(config.device)

            self.optimizer.zero_grad()

            with amp.autocast(device_type=config.device, enabled=config.use_amp):
                outputs = self.model(images)
                loss = self.criterion(outputs, labels)

            self.scaler.scale(loss).backward()
            self.scaler.step(self.optimizer)
            self.scaler.update()

            total_loss += loss.item()
            _, preds = outputs.max(1)
            correct += preds.eq(labels).sum().item()
            total += labels.size(0)

            if batch_idx % 50 == 0:
                logging.info(
                    f"Epoch {epoch:3d} [{batch_idx:4d}/{len(loader):4d}] "
                    f"Loss: {loss.item():.4f} Acc: {correct/total:.4f}"
                )

        return total_loss / len(loader), correct / total

    @torch.no_grad()
    def evaluate(self, loader: DataLoader):
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0
        all_preds = []
        all_labels = []

        for images, labels in loader:
            images, labels = images.to(config.device), labels.to(config.device)
            outputs = self.model(images)
            loss = self.criterion(outputs, labels)
            total_loss += loss.item()
            _, preds = outputs.max(1)
            correct += preds.eq(labels).sum().item()
            total += labels.size(0)
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(labels.cpu().tolist())

        return total_loss / len(loader), correct / total, all_preds, all_labels

    def fit(self, train_loader: DataLoader, val_loader: DataLoader):
        warmup = LinearLR(self.optimizer, start_factor=0.1, total_iters=config.warmup_epochs * len(train_loader))
        cosine = CosineAnnealingLR(self.optimizer, T_max=config.epochs - config.warmup_epochs)
        scheduler = SequentialLR(self.optimizer, schedulers=[warmup, cosine], milestones=[config.warmup_epochs * len(train_loader)])

        for epoch in range(1, config.epochs + 1):
            train_loss, train_acc = self.train_epoch(train_loader, epoch)
            val_loss, val_acc, _, _ = self.evaluate(val_loader)

            logging.info(
                f"Epoch {epoch:3d} | Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} | "
                f"Val Loss: {val_loss:.4f} Acc: {val_acc:.4f}"
            )

            self.metrics_history.append({
                "epoch": epoch, "train_loss": train_loss, "train_acc": train_acc,
                "val_loss": val_loss, "val_acc": val_acc,
            })

            if val_acc > self.best_acc:
                self.best_acc = val_acc
                self.save("best_model.pth")
                logging.info(f"  ✓ 保存最佳模型 (acc={val_acc:.4f})")

            scheduler.step()

    def save(self, path: str):
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "best_acc": self.best_acc,
            "config": config,
            "metrics": self.metrics_history,
        }, path)

    @staticmethod
    def load(path: str) -> "Trainer":
        checkpoint = torch.load(path, map_location=config.device, weights_only=False)
        trainer = Trainer()
        trainer.model.load_state_dict(checkpoint["model_state_dict"])
        trainer.best_acc = checkpoint.get("best_acc", 0.0)
        trainer.metrics_history = checkpoint.get("metrics", [])
        trainer.model.eval()
        return trainer

# ─── 模型量化 ───────────────────────────────────────────────
def quantize_model(model: nn.Module, calibration_loader: DataLoader):
    """动态量化 — 减小模型体积，加速推理"""
    model.eval()
    model.to("cpu")

    # 量化主干网络
    model.backbone = torch.quantization.quantize_dynamic(
        model.backbone,
        {nn.Linear, nn.Conv2d},
        dtype=torch.qint8,
    )
    logging.info("模型量化完成")
    return model

# ─── 推理服务 ───────────────────────────────────────────────
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

class InferenceService:
    """FastAPI 图像分类推理服务"""

    def __init__(self, model_path: str, label_map: dict[int, str]):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.trainer = Trainer.load(model_path)
        self.model = self.trainer.model.to(self.device)
        self.model.eval()
        self.label_map = label_map

        # 图像预处理
        self.transform = transforms.Compose([
            transforms.Resize(int(config.image_size * 1.14)),
            transforms.CenterCrop(config.image_size),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def predict(self, image: Image.Image, top_k: int = 5) -> list[dict]:
        """推理单张图片"""
        tensor = self.transform(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            outputs = self.model(tensor)
            probs = F.softmax(outputs, dim=1)

        topk_probs, topk_indices = torch.topk(probs, top_k)

        results = []
        for prob, idx in zip(topk_probs[0].cpu().tolist(), topk_indices[0].cpu().tolist()):
            results.append({
                "label_id": idx,
                "label": self.label_map.get(idx, f"class_{idx}"),
                "confidence": round(prob, 4),
            })
        return results

    def predict_batch(self, images: list[Image.Image], top_k: int = 5) -> list[list[dict]]:
        """批量推理"""
        tensors = torch.stack([self.transform(img) for img in images]).to(self.device)

        with torch.no_grad():
            outputs = self.model(tensors)
            probs = F.softmax(outputs, dim=1)

        topk_probs, topk_indices = torch.topk(probs, top_k)

        batch_results = []
        for i in range(len(images)):
            item = []
            for prob, idx in zip(topk_probs[i].cpu().tolist(), topk_indices[i].cpu().tolist()):
                item.append({
                    "label_id": idx,
                    "label": self.label_map.get(idx, f"class_{idx}"),
                    "confidence": round(prob, 4),
                })
            batch_results.append(item)
        return batch_results

    def extract_feature(self, image: Image.Image) -> np.ndarray:
        """提取图像特征向量（用于以图搜图）"""
        tensor = self.transform(image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            features = self.model.extract_features(tensor)
        return features.cpu().numpy().flatten()


# 创建 FastAPI 应用
app = FastAPI(title="商品图片分类服务", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

service: Optional[InferenceService] = None


@app.on_event("startup")
async def load_model():
    global service
    # 示例标签映射
    labels = {
        0: "手机", 1: "笔记本电脑", 2: "耳机", 3: "手表", 4: "相机",
        5: "平板电脑", 6: "键盘", 7: "鼠标", 8: "显示器", 9: "音箱",
    }
    service = InferenceService("best_model.pth", labels)
    logging.info("模型加载完成")


@app.post("/predict")
async def predict(file: UploadFile = File(...), top_k: int = 5):
    if not service:
        raise HTTPException(503, "模型未就绪")

    try:
        image = Image.open(io.BytesIO(await file.read())).convert("RGB")
    except Exception:
        raise HTTPException(400, "无法解析图片")

    results = service.predict(image, top_k)
    return {"filename": file.filename, "predictions": results}


@app.post("/predict/batch")
async def predict_batch(files: list[UploadFile] = File(...)):
    if not service:
        raise HTTPException(503, "模型未就绪")

    images = []
    for file in files:
        try:
            images.append(Image.open(io.BytesIO(await file.read())).convert("RGB"))
        except Exception:
            raise HTTPException(400, f"无法解析图片: {file.filename}")

    results = service.predict_batch(images)
    return {"predictions": results}


@app.post("/extract-feature")
async def extract_feature(file: UploadFile = File(...)):
    if not service:
        raise HTTPException(503, "模型未就绪")
    image = Image.open(io.BytesIO(await file.read())).convert("RGB")
    feature = service.extract_feature(image)
    return {"feature": feature.tolist(), "dim": len(feature)}


@app.get("/health")
async def health():
    return {"status": "ok", "model_loaded": service is not None}


# ─── 主函数 ─────────────────────────────────────────────────
def main():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        # 训练模式
        full_dataset = AugmentedDataset(config.data_dir, "train")
        train_size = int(0.85 * len(full_dataset))
        val_size = len(full_dataset) - train_size
        train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])

        train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True,
                                  num_workers=config.num_workers, pin_memory=True, drop_last=True)
        val_loader = DataLoader(val_dataset, batch_size=config.batch_size, shuffle=False,
                                num_workers=config.num_workers, pin_memory=True)

        trainer = Trainer()
        trainer.fit(train_loader, val_loader)
        logging.info(f"训练完成! 最佳准确率: {trainer.best_acc:.4f}")


if __name__ == "__main__":
    main()
