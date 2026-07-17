#!/usr/bin/env python3
"""
视频智能分析系统
依赖: pip install opencv-python openai ultralytics transformers torch
      pip install pillow easyocr moviepy ffmpeg-python
"""
import base64
import io
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import ffmpeg
import numpy as np
from moviepy.editor import VideoFileClip
from openai import OpenAI
from PIL import Image
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VideoUnderstanding")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-xxx")

@dataclass
class VideoAnalysisResult:
    duration: float
    fps: float
    resolution: tuple[int, int]
    scenes: list[dict] = field(default_factory=list)
    objects: list[dict] = field(default_factory=list)
    keyframes: list[str] = field(default_factory=list)  # base64
    summary: str = ""
    captions: list[dict] = field(default_factory=list)  # [{time, text}]
    transcript: str = ""

# ─── 视频基础分析 ─────────────────────────────────────────
class VideoAnalyzer:
    """视频基本信息提取"""

    @staticmethod
    def get_info(video_path: str) -> dict:
        """获取视频基本信息"""
        cap = cv2.VideoCapture(video_path)

        info = {
            "duration": cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS),
            "fps": cap.get(cv2.CAP_PROP_FPS),
            "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "codec": int(cap.get(cv2.CAP_PROP_FOURCC)),
            "bitrate": cap.get(cv2.CAP_PROP_BITRATE),
        }
        cap.release()

        # 文件大小
        info["file_size"] = os.path.getsize(video_path)

        return info

    @staticmethod
    def extract_audio(video_path: str, output_path: str = None) -> str:
        """提取音频"""
        if output_path is None:
            output_path = video_path.rsplit('.', 1)[0] + '.wav'

        clip = VideoFileClip(video_path)
        clip.audio.write_audiofile(output_path, logger=None)
        clip.close()

        return output_path

# ─── 场景切分 ─────────────────────────────────────────────
class SceneDetector:
    """视频场景切分（基于帧间差异）"""

    def __init__(self, threshold: float = 30.0, min_scene_length: float = 1.0):
        self.threshold = threshold
        self.min_scene_length = min_scene_length

    def detect_scenes(self, video_path: str) -> list[dict]:
        """
        检测场景切换点
        返回: [{start_time, end_time, keyframe_index}]
        """
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        scenes = []
        scene_start = 0
        prev_hist = None
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 计算直方图
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist = cv2.normalize(hist, hist).flatten()

            if prev_hist is not None:
                # 计算直方图差异
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)

                if diff > self.threshold:
                    scene_end = frame_idx
                    duration = (scene_end - scene_start) / fps

                    if duration >= self.min_scene_length:
                        scenes.append({
                            "start_time": scene_start / fps,
                            "end_time": scene_end / fps,
                            "duration": duration,
                            "start_frame": scene_start,
                            "end_frame": scene_end,
                        })

                    scene_start = frame_idx

            prev_hist = hist
            frame_idx += 1

        # 最后一个场景
        if scene_start < total_frames - 1:
            scenes.append({
                "start_time": scene_start / fps,
                "end_time": total_frames / fps,
                "duration": (total_frames - scene_start) / fps,
                "start_frame": scene_start,
                "end_frame": total_frames,
            })

        cap.release()

        logger.info(f"Detected {len(scenes)} scenes")
        return scenes

# ─── 关键帧提取 ───────────────────────────────────────────
class KeyFrameExtractor:
    """提取视频关键帧"""

    def __init__(self, max_frames: int = 20):
        self.max_frames = max_frames

    def extract(self, video_path: str) -> list[dict]:
        """
        提取关键帧
        返回: [{timestamp, image_base64, frame_index}]
        """
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        # 均匀采样
        if total_frames <= self.max_frames:
            sample_indices = list(range(total_frames))
        else:
            step = total_frames // self.max_frames
            sample_indices = [i * step for i in range(self.max_frames)]

        keyframes = []
        prev_frame = None
        prev_hist = None

        for target_idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
            ret, frame = cap.read()
            if not ret:
                continue

            # 质量检查：跳过模糊帧
            if not self._is_sharp(frame):
                continue

            # 去重：跳过与前一帧太相似的帧
            if prev_frame is not None:
                similarity = self._frame_similarity(prev_frame, frame)
                if similarity > 0.95:
                    continue

            # 编码为 base64
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            img_b64 = base64.b64encode(buffer).decode()

            keyframes.append({
                "timestamp": target_idx / fps,
                "frame_index": target_idx,
                "image_base64": img_b64,
            })

            prev_frame = frame

        cap.release()

        logger.info(f"Extracted {len(keyframes)} keyframes from {total_frames} frames")
        return keyframes

    def extract_scene_keyframes(self, video_path: str, scenes: list[dict]) -> list[dict]:
        """为每个场景提取一个代表帧"""
        cap = cv2.VideoCapture(video_path)
        keyframes = []

        for scene in scenes:
            mid_frame = (scene["start_frame"] + scene["end_frame"]) // 2
            cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
            ret, frame = cap.read()

            if ret:
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                img_b64 = base64.b64encode(buffer).decode()

                keyframes.append({
                    "timestamp": mid_frame / cap.get(cv2.CAP_PROP_FPS),
                    "scene_start": scene["start_time"],
                    "scene_end": scene["end_time"],
                    "image_base64": img_b64,
                })

        cap.release()
        return keyframes

    def _is_sharp(self, frame: np.ndarray, threshold: float = 100.0) -> bool:
        """拉普拉斯方差检查清晰度"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return laplacian_var > threshold

    def _frame_similarity(self, frame1: np.ndarray, frame2: np.ndarray) -> float:
        """帧间相似度"""
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)

        hist1 = cv2.calcHist([gray1], [0], None, [256], [0, 256])
        hist2 = cv2.calcHist([gray2], [0], None, [256], [0, 256])

        cv2.normalize(hist1, hist1)
        cv2.normalize(hist2, hist2)

        return cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

# ─── 目标检测与跟踪 ───────────────────────────────────────
class ObjectDetector:
    """YOLO 目标检测 & 跟踪"""

    def __init__(self, model_name: str = "yolov8n.pt"):
        self.model = YOLO(model_name)
        self.class_names = self.model.names

    def detect_frame(self, frame: np.ndarray, conf_threshold: float = 0.3) -> list[dict]:
        """检测单帧"""
        results = self.model(frame, conf=conf_threshold, verbose=False)

        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = self.class_names.get(cls_id, "unknown")

                detections.append({
                    "class": cls_name,
                    "confidence": conf,
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                })

        return detections

    def detect_video(self, video_path: str, sample_rate: int = 30) -> list[dict]:
        """
        定时采样检测视频
        sample_rate: 每 N 帧检测一次
        """
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)

        timeline = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_rate == 0:
                detections = self.detect_frame(frame)
                if detections:
                    timeline.append({
                        "timestamp": frame_idx / fps,
                        "frame_index": frame_idx,
                        "detections": detections,
                    })

            frame_idx += 1

        cap.release()
        return timeline

    def track_objects(self, video_path: str, target_class: Optional[str] = None) -> list[dict]:
        """
        目标跟踪（特定类别，如 person / car）
        返回: [{object_id, class_name, track: [{timestamp, bbox}]}]
        """
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)

        # 使用 YOLO 跟踪模式
        tracks: dict[int, dict] = {}  # track_id -> track_data
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            results = self.model.track(
                frame,
                persist=True,
                conf=0.3,
                verbose=False,
                classes=[0] if target_class == "person" else None,
            )

            if results[0].boxes and results[0].boxes.id is not None:
                boxes = results[0].boxes
                for i in range(len(boxes)):
                    track_id = int(boxes.id[i])
                    cls_id = int(boxes.cls[i])
                    cls_name = self.class_names.get(cls_id, "unknown")
                    x1, y1, x2, y2 = boxes.xyxy[i].tolist()

                    if track_id not in tracks:
                        tracks[track_id] = {
                            "object_id": track_id,
                            "class_name": cls_name,
                            "track": [],
                        }

                    tracks[track_id]["track"].append({
                        "timestamp": frame_idx / fps,
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    })

            frame_idx += 1

        cap.release()
        return list(tracks.values())

# ─── 视频字幕/文字提取 (OCR) ──────────────────────────────
class VideoOCR:
    """视频帧文字提取"""

    def __init__(self):
        import easyocr
        self.reader = easyocr.Reader(['ch_sim', 'en'])

    def extract_text(self, frame: np.ndarray) -> list[dict]:
        """从单帧提取文字"""
        results = self.reader.readtext(frame)

        texts = []
        for bbox, text, confidence in results:
            if confidence > 0.5:
                texts.append({
                    "text": text,
                    "confidence": confidence,
                    "bbox": bbox,
                })

        return texts

    def extract_timeline(self, video_path: str, sample_rate: int = 30) -> list[dict]:
        """定时采样 OCR"""
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)

        timeline = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_rate == 0:
                texts = self.extract_text(frame)
                if texts:
                    timeline.append({
                        "timestamp": frame_idx / fps,
                        "texts": texts,
                    })

            frame_idx += 1

        cap.release()
        return timeline

# ─── 视频摘要（多模态 LLM） ───────────────────────────────
class VideoSummarizer:
    """基于多模态 LLM 的视频摘要"""

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def summarize_from_keyframes(
        self, keyframes: list[dict], transcript: str = ""
    ) -> str:
        """从关键帧 + 音频转写生成视频摘要"""

        # 构建多模态消息
        content = []

        # 添加关键帧（最多 10 张以控制 Token）
        for i, kf in enumerate(keyframes[:10]):
            content.append({
                "type": "text",
                "text": f"画面 {i+1} (时间: {kf['timestamp']:.1f}s):",
            })
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{kf['image_base64']}",
                    "detail": "low",
                },
            })

        # 添加音频转写
        if transcript:
            content.insert(0, {
                "type": "text",
                "text": f"视频音频转写内容:\n{transcript[:3000]}\n\n请结合画面内容生成摘要。",
            })

        content.append({
            "type": "text",
            "text": "请生成这个视频的摘要（200-500字），包括：1. 视频主题和内容概述 2. 关键场景 3. 核心信息或结论。",
        })

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            temperature=0.3,
            max_tokens=1000,
        )

        return response.choices[0].message.content.strip()

    def video_qa(self, keyframes: list[dict], question: str, transcript: str = "") -> str:
        """视频问答"""
        content = []

        if transcript:
            content.append({
                "type": "text",
                "text": f"音频转写：{transcript[:2000]}",
            })

        for kf in keyframes[:8]:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{kf['image_base64']}",
                    "detail": "low",
                },
            })

        content.append({
            "type": "text",
            "text": f"问题：{question}\n\n请根据视频画面和音频内容回答。",
        })

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            temperature=0.2,
            max_tokens=500,
        )

        return response.choices[0].message.content.strip()

# ─── 视频分析管线 ─────────────────────────────────────────
class VideoAnalysisPipeline:
    """完整的视频分析管线"""

    def __init__(self):
        self.analyzer = VideoAnalyzer()
        self.scene_detector = SceneDetector()
        self.keyframe_extractor = KeyFrameExtractor()
        self.detector = ObjectDetector()
        self.ocr = VideoOCR()
        self.summarizer = VideoSummarizer()

    def analyze(self, video_path: str) -> VideoAnalysisResult:
        """完整分析视频"""
        logger.info(f"Analyzing: {video_path}")

        # 1. 基本信息
        info = self.analyzer.get_info(video_path)
        result = VideoAnalysisResult(
            duration=info["duration"],
            fps=info["fps"],
            resolution=(info["width"], info["height"]),
        )

        # 2. 场景切分
        result.scenes = self.scene_detector.detect_scenes(video_path)

        # 3. 关键帧提取
        scene_kfs = self.keyframe_extractor.extract_scene_keyframes(video_path, result.scenes)
        uniform_kfs = self.keyframe_extractor.extract(video_path)
        result.keyframes = uniform_kfs[:15]  # 限制数量

        # 4. 目标检测（采样）
        try:
            result.objects = self.detector.detect_video(video_path, sample_rate=60)[:50]
        except Exception as e:
            logger.warning(f"Object detection failed: {e}")

        # 5. 字幕提取
        try:
            result.captions = self.ocr.extract_timeline(video_path)[:30]
        except Exception as e:
            logger.warning(f"OCR failed: {e}")

        # 6. 摘要生成
        try:
            result.summary = self.summarizer.summarize_from_keyframes(result.keyframes)
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            result.summary = "摘要生成失败"

        return result

# ─── 使用示例 ─────────────────────────────────────────────
if __name__ == "__main__":
    pipeline = VideoAnalysisPipeline()

    result = pipeline.analyze("sample_video.mp4")

    print(f"\n{'='*60}")
    print(f"视频时长: {result.duration:.1f}s")
    print(f"分辨率: {result.resolution[0]}x{result.resolution[1]}")
    print(f"场景数: {len(result.scenes)}")
    print(f"关键帧: {len(result.keyframes)}")
    print(f"{'='*60}\n")

    print("📝 视频摘要:\n")
    print(result.summary)

    print(f"\n🎬 场景切分 ({len(result.scenes)} 个):")
    for i, scene in enumerate(result.scenes[:5]):
        print(f"  场景{i+1}: {scene['start_time']:.1f}s - {scene['end_time']:.1f}s ({scene['duration']:.1f}s)")

    if result.objects:
        print(f"\n🔍 检测到 {len(result.objects)} 个目标帧")
        # 统计目标类型
        from collections import Counter
        all_objects = []
        for obj_frame in result.objects:
            for det in obj_frame.get('detections', []):
                all_objects.append(det['class'])
        obj_counts = Counter(all_objects).most_common(10)
        for cls, count in obj_counts:
            print(f"  {cls}: {count}次")
