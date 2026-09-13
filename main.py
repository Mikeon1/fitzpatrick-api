# -*- coding: utf-8 -*-
"""
API REST (FastAPI) para servir o classificador de fototipos Fitzpatrick
(ResNet-18 treinada em PyTorch).

Como rodar:
    pip install -r requirements.txt
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Endpoint principal:
    POST /predict  (multipart/form-data, campo 'file' = imagem)

Certifique-se de que o arquivo 'modelo_fitzpatrick_resnet18.pth' está
no mesmo diretório deste script (ou ajuste MODEL_PATH abaixo).
"""

import io
import logging

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models, transforms
from PIL import Image, UnidentifiedImageError

from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ============================================================
# Configurações
# ============================================================
MODEL_PATH = "modelo_fitzpatrick_resnet18.pth"
NUM_CLASSES = 6
DEVICE = torch.device("cpu")  # conforme solicitado: modo CPU

# Rótulos na mesma ordem usada no treino (label = group - 1, ou seja,
# índice 0 = Fototipo 1 / Tipo I, ... índice 5 = Fototipo 6 / Tipo VI)
CLASS_NAMES = ["Tipo 1", "Tipo 2", "Tipo 3", "Tipo 4", "Tipo 5", "Tipo 6"]

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/webp"}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fitzpatrick-api")

# ============================================================
# Pré-processamento (Com corte automático de bordas)
# ============================================================
transform_model = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

def preprocess_image(image_bytes: bytes) -> torch.Tensor:
    """Converte bytes de imagem em um tensor com crop das bordas para isolar a pele."""
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=400,
            detail="Não foi possível ler o arquivo como imagem. "
                   "Envie um arquivo JPEG, PNG ou WEBP válido."
        )
    
    # --- CROP AUTOMÁTICO ---
    # Corta 25% das bordas esquerda e direita para eliminar o fundo branco/externo
    w, h = image.size
    crop_box = (w * 0.25, h * 0.10, w * 0.75, h * 0.90)
    image_cropped = image.crop(crop_box)
    
    # Aplica o redimensionamento e a normalização ImageNet
    tensor = transform_model(image_cropped)
    return tensor.unsqueeze(0)  # [1, 3, 224, 224]


# ============================================================
# Modelo
# ============================================================
def build_model(num_classes: int = NUM_CLASSES) -> nn.Module:
    """Recria a arquitetura ResNet-18 com o cabeçalho customizado (fc)
    usado durante o treinamento."""
    model = models.resnet18(weights=None)
    
    # Ajusta o cabeçalho fc.0, fc.1, fc.4 conforme treinado no checkpoint
    in_features = model.fc.in_features  # 512 para ResNet-18
    model.fc = nn.Sequential(
        nn.Linear(in_features, 256),  # fc.0
        nn.BatchNorm1d(256),          # fc.1
        nn.ReLU(),                   # fc.2
        nn.Dropout(0.3),             # fc.3
        nn.Linear(256, num_classes)  # fc.4
    )
    return model


def load_model(model_path: str = MODEL_PATH) -> nn.Module:
    model = build_model()
    try:
        state_dict = torch.load(model_path, map_location=DEVICE)
        model.load_state_dict(state_dict)
    except FileNotFoundError:
        raise RuntimeError(
            f"Arquivo de pesos '{model_path}' não encontrado. "
            "Coloque o .pth no mesmo diretório da API ou ajuste MODEL_PATH."
        )
    model.to(DEVICE)
    model.eval()
    return model


# ============================================================
# Schemas de resposta
# ============================================================
class PredictionResponse(BaseModel):
    predicao_principal: str
    confianca: float
    probabilidades: dict[str, float]


# ============================================================
# Gerenciador do ciclo de vida (Lifespan)
# ============================================================
model: nn.Module | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    logger.info("Carregando modelo a partir de '%s'...", MODEL_PATH)
    model = load_model(MODEL_PATH)
    logger.info("Modelo carregado com sucesso (dispositivo: %s).", DEVICE)
    yield

# ============================================================
# App FastAPI
# ============================================================
app = FastAPI(
    title="Fitzpatrick Skin Phototype Classifier API",
    description="API para classificação de fototipos de pele (Escala Fitzpatrick) "
                "a partir de imagens de antebraço, usando ResNet-18.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS liberado para qualquer origem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Fitzpatrick Skin Phototype Classifier API",
        "endpoint_predicao": "/predict (POST, multipart/form-data, campo 'file')",
    }


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model is not None}


@app.post("/predict", response_model=PredictionResponse)
async def predict(file: UploadFile = File(...)):
    if model is None:
        raise HTTPException(status_code=503, detail="Modelo ainda não foi carregado.")

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo não suportado: {file.content_type}. "
                   f"Envie uma imagem JPEG, PNG ou WEBP."
        )

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Arquivo de imagem vazio.")

    input_tensor = preprocess_image(image_bytes).to(DEVICE)

    with torch.no_grad():
        logits = model(input_tensor)
        probs = F.softmax(logits, dim=1).squeeze(0)  # shape: [6]

    probs_percent = (probs * 100).tolist()
    probabilidades = {
        CLASS_NAMES[i]: round(probs_percent[i], 2) for i in range(NUM_CLASSES)
    }

    top_idx = int(torch.argmax(probs).item())
    predicao_principal = CLASS_NAMES[top_idx]
    confianca = round(probs_percent[top_idx], 2)

    return PredictionResponse(
        predicao_principal=predicao_principal,
        confianca=confianca,
        probabilidades=probabilidades,
    )


# ============================================================
# Execução direta (alternativa ao comando uvicorn no terminal)
# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)