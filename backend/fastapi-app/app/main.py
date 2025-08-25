from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest
import numpy as np

app = FastAPI(title="Incubadora Neonatal API")


# Modelos de datos
class SensorData(BaseModel):
    device_id: str
    temperature: float
    humidity: float
    light_level: Optional[float] = None
    timestamp: datetime = datetime.now()


class PredictionRequest(BaseModel):
    temperature: float
    humidity: float
    values: List[float]


# Modelo de ML (simple inicialmente)
model = None


def load_model():
    global model
    try:
        model = joblib.load('model/anomaly_detector.pkl')
    except:
        # Crear modelo inicial si no existe
        model = IsolationForest(contamination=0.1, random_state=42)
        # Entrenar con datos dummy iniciales
        X_dummy = np.random.rand(100, 2) * 10 + 30  # Datos simulados
        model.fit(X_dummy)
        joblib.dump(model, 'model/anomaly_detector.pkl')


@app.on_event("startup")
async def startup_event():
    load_model()


@app.post("/api/sensor-data")
async def receive_sensor_data(data: SensorData):
    # Aquí procesaríamos y guardaríamos los datos
    # Por ahora, solo devolvemos confirmación
    return {"status": "received", "device_id": data.device_id}


@app.post("/api/predict-anomaly")
async def predict_anomaly(request: PredictionRequest):
    # Preparar datos para predicción
    X = np.array([[request.temperature, request.humidity]])

    # Predecir anomalía (-1 para anomalía, 1 para normal)
    prediction = model.predict(X)

    return {
        "is_anomaly": bool(prediction[0] == -1),
        "temperature": request.temperature,
        "humidity": request.humidity
    }


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}