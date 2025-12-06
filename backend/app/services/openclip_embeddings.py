"""
Класс для генерации эмбеддингов через OpenCLIP (из sam2seg)

Использует OpenCLIP для создания мультимодальных эмбеддингов
текста и изображений в едином векторном пространстве.
"""

import logging
from typing import List, Optional
from pathlib import Path
import os

logger = logging.getLogger(__name__)

# Проверка доступности OpenCLIP
try:
    import torch
    import open_clip
    from PIL import Image
    import numpy as np
    OPENCLIP_AVAILABLE = True
except ImportError:
    OPENCLIP_AVAILABLE = False
    torch = None
    open_clip = None
    Image = None
    np = None


class OpenCLIPEmbeddings:
    """Класс для генерации эмбеддингов через OpenCLIP."""
    
    def __init__(
        self, 
        model_name: str = "ViT-B-16", 
        pretrained: str = "openai",
        device: Optional[str] = None
    ):
        """
        Инициализация OpenCLIP.
        
        Args:
            model_name: Название модели (ViT-B-32, ViT-B-16, ViT-L-14)
            pretrained: Предобученная версия (openai, laion400m, laion2b)
            device: Устройство (cuda/cpu). Если None, определяется автоматически
        """
        if not OPENCLIP_AVAILABLE:
            raise ImportError(
                "open_clip не установлен. Установите: pip install open-clip-torch"
            )
        
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_name = model_name
        self.pretrained = pretrained
        
        try:
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                model_name, 
                pretrained=pretrained,
                device=self.device
            )
            self.tokenizer = open_clip.get_tokenizer(model_name)
            self.model.eval()
            
            # Определяем размерность эмбеддинга
            with torch.no_grad():
                dummy_img = torch.zeros(1, 3, 224, 224).to(self.device)
                dummy_text = self.tokenizer(["test"]).to(self.device)
                img_emb = self.model.encode_image(dummy_img)
                txt_emb = self.model.encode_text(dummy_text)
                self.embedding_dim = img_emb.shape[1]
            
            logger.info(
                f"✅ OpenCLIP инициализирован: {model_name}/{pretrained} "
                f"на {self.device}, размерность: {self.embedding_dim}"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации OpenCLIP: {e}")
            raise
    
    def encode_image(self, image_path: str, normalize: bool = True) -> List[float]:
        """
        Генерирует эмбеддинг для изображения.
        
        Args:
            image_path: Путь к изображению
            normalize: Нормализовать эмбеддинг (для cosine similarity)
        
        Returns:
            Список чисел (эмбеддинг)
        """
        try:
            if not Path(image_path).exists():
                logger.warning(f"Изображение не найдено: {image_path}")
                return [0.0] * self.embedding_dim
            
            image = Image.open(image_path).convert("RGB")
            image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                embedding = self.model.encode_image(image_tensor)
                
                if normalize:
                    # Нормализуем для cosine similarity
                    embedding = embedding / embedding.norm(dim=-1, keepdim=True)
            
            return embedding.cpu().numpy().tolist()[0]
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации эмбеддинга изображения {image_path}: {e}")
            return [0.0] * self.embedding_dim
    
    def encode_text(self, text: str, normalize: bool = True) -> List[float]:
        """
        Генерирует эмбеддинг для текста.
        
        Args:
            text: Текст для эмбеддинга
            normalize: Нормализовать эмбеддинг (для cosine similarity)
        
        Returns:
            Список чисел (эмбеддинг)
        """
        try:
            if not text or not text.strip():
                logger.warning("Пустой текст для эмбеддинга")
                return [0.0] * self.embedding_dim
            
            text_tokens = self.tokenizer([text]).to(self.device)
            
            with torch.no_grad():
                embedding = self.model.encode_text(text_tokens)
                
                if normalize:
                    # Нормализуем для cosine similarity
                    embedding = embedding / embedding.norm(dim=-1, keepdim=True)
            
            return embedding.cpu().numpy().tolist()[0]
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации эмбеддинга текста '{text[:50]}...': {e}")
            return [0.0] * self.embedding_dim
    
    @property
    def embedding_dimension(self) -> int:
        """Возвращает размерность эмбеддинга."""
        return self.embedding_dim


# Глобальный экземпляр
_openclip_embeddings: Optional[OpenCLIPEmbeddings] = None


def get_openclip_embeddings(
    model_name: str = "ViT-B-16",
    pretrained: str = "openai",
    device: Optional[str] = None
) -> OpenCLIPEmbeddings:
    """
    Получает глобальный экземпляр OpenCLIPEmbeddings.
    
    Args:
        model_name: Название модели
        pretrained: Предобученная версия
        device: Устройство
    
    Returns:
        Экземпляр OpenCLIPEmbeddings
    """
    global _openclip_embeddings
    
    if _openclip_embeddings is None:
        _openclip_embeddings = OpenCLIPEmbeddings(
            model_name=model_name,
            pretrained=pretrained,
            device=device
        )
    elif (
        _openclip_embeddings.model_name != model_name or
        _openclip_embeddings.pretrained != pretrained
    ):
        # Пересоздаем если параметры изменились
        _openclip_embeddings = OpenCLIPEmbeddings(
            model_name=model_name,
            pretrained=pretrained,
            device=device
        )
    
    return _openclip_embeddings



