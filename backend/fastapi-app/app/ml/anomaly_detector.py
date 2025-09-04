"""
Detector de anomalías para sensores de incubadora neonatal usando ML
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Detector de anomalías para sensores de incubadora neonatal
    """

    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = [
            'temperatura', 'humedad', 'oxigeno', 'frecuencia_cardiaca',
            'frecuencia_respiratoria', 'presion_arterial_sistolica',
            'presion_arterial_diastolica'
        ]
        self.normal_ranges = {
            'temperatura': (36.0, 37.5),  # °C
            'humedad': (40.0, 70.0),      # %
            'oxigeno': (21.0, 100.0),     # %
            'frecuencia_cardiaca': (100, 180),  # bpm
            'frecuencia_respiratoria': (30, 60),  # rpm
            'presion_arterial_sistolica': (50, 90),   # mmHg
            'presion_arterial_diastolica': (25, 50)   # mmHg
        }

    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Prepara los datos para el entrenamiento/predicción
        """
        try:
            # Verificar que todas las columnas necesarias estén presentes
            missing_features = set(self.feature_names) - set(data.columns)
            if missing_features:
                raise ValueError(f"Faltan las siguientes características: {missing_features}")

            # Seleccionar solo las características necesarias
            prepared_data = data[self.feature_names].copy()

            # Remover valores nulos
            prepared_data = prepared_data.dropna()

            # Agregar características derivadas
            prepared_data['temp_deviation'] = abs(prepared_data['temperatura'] - 36.75)
            prepared_data['humidity_deviation'] = abs(prepared_data['humedad'] - 55.0)
            prepared_data['hr_rr_ratio'] = prepared_data['frecuencia_cardiaca'] / prepared_data['frecuencia_respiratoria']
            prepared_data['bp_diff'] = prepared_data['presion_arterial_sistolica'] - prepared_data['presion_arterial_diastolica']

            return prepared_data

        except Exception as e:
            logger.error(f"Error preparando datos: {str(e)}")
            raise

    def train(self, training_data: pd.DataFrame, contamination: float = 0.1) -> Dict:
        """
        Entrena el modelo de detección de anomalías
        """
        try:
            logger.info("Iniciando entrenamiento del detector de anomalías")

            # Preparar datos
            prepared_data = self.prepare_data(training_data)

            if len(prepared_data) < 50:
                raise ValueError("Se necesitan al menos 50 muestras para entrenar el modelo")

            # Normalizar datos
            scaled_data = self.scaler.fit_transform(prepared_data)

            # Entrenar modelo Isolation Forest
            self.model = IsolationForest(
                contamination=contamination,
                random_state=42,
                n_estimators=100,
                max_samples='auto',
                bootstrap=False
            )

            self.model.fit(scaled_data)
            self.is_trained = True

            # Evaluar el modelo con los datos de entrenamiento
            predictions = self.model.predict(scaled_data)
            anomaly_score = self.model.decision_function(scaled_data)

            n_anomalies = np.sum(predictions == -1)
            anomaly_rate = n_anomalies / len(predictions)

            logger.info(f"Modelo entrenado exitosamente. Anomalías detectadas: {n_anomalies}/{len(predictions)} ({anomaly_rate:.2%})")

            return {
                'status': 'success',
                'samples_trained': len(prepared_data),
                'anomalies_detected': int(n_anomalies),
                'anomaly_rate': float(anomaly_rate),
                'mean_anomaly_score': float(np.mean(anomaly_score))
            }

        except Exception as e:
            logger.error(f"Error entrenando modelo: {str(e)}")
            raise

    def predict(self, sensor_data: Dict) -> Dict:
        """
        Predice si los datos del sensor son anómalos
        """
        if not self.is_trained:
            raise ValueError("El modelo no ha sido entrenado")

        try:
            # Convertir a DataFrame
            df = pd.DataFrame([sensor_data])
            prepared_data = self.prepare_data(df)

            # Normalizar
            scaled_data = self.scaler.transform(prepared_data)

            # Predicción
            prediction = self.model.predict(scaled_data)[0]
            anomaly_score = self.model.decision_function(scaled_data)[0]

            # Análisis de rangos normales
            range_violations = self._check_normal_ranges(sensor_data)

            # Determinar nivel de alerta
            alert_level = self._determine_alert_level(prediction, anomaly_score, range_violations)

            return {
                'is_anomaly': bool(prediction == -1),
                'anomaly_score': float(anomaly_score),
                'alert_level': alert_level,
                'range_violations': range_violations,
                'timestamp': datetime.utcnow().isoformat(),
                'confidence': float(abs(anomaly_score))
            }

        except Exception as e:
            logger.error(f"Error en predicción: {str(e)}")
            raise

    def _check_normal_ranges(self, sensor_data: Dict) -> List[Dict]:
        """
        Verifica violaciones de rangos normales
        """
        violations = []

        for feature, (min_val, max_val) in self.normal_ranges.items():
            if feature in sensor_data:
                value = sensor_data[feature]
                if value < min_val or value > max_val:
                    violations.append({
                        'parameter': feature,
                        'value': value,
                        'normal_range': [min_val, max_val],
                        'deviation': min(abs(value - min_val), abs(value - max_val))
                    })

        return violations

    def _determine_alert_level(self, prediction: int, anomaly_score: float,
                              range_violations: List[Dict]) -> str:
        """
        Determina el nivel de alerta basado en múltiples factores
        """
        critical_violations = [
            v for v in range_violations
            if v['parameter'] in ['temperatura', 'oxigeno', 'frecuencia_cardiaca']
        ]

        if critical_violations and prediction == -1:
            return 'CRITICO'
        elif prediction == -1 and anomaly_score < -0.1:
            return 'ALTO'
        elif range_violations or (prediction == -1 and anomaly_score < -0.05):
            return 'MEDIO'
        elif anomaly_score < -0.02:
            return 'BAJO'
        else:
            return 'NORMAL'

    def save_model(self, filepath: str) -> bool:
        """
        Guarda el modelo entrenado
        """
        try:
            if not self.is_trained:
                raise ValueError("No hay modelo entrenado para guardar")

            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names,
                'normal_ranges': self.normal_ranges,
                'is_trained': self.is_trained
            }

            joblib.dump(model_data, filepath)
            logger.info(f"Modelo guardado en: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error guardando modelo: {str(e)}")
            return False

    def load_model(self, filepath: str) -> bool:
        """
        Carga un modelo previamente entrenado
        """
        try:
            model_data = joblib.load(filepath)

            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_names = model_data['feature_names']
            self.normal_ranges = model_data['normal_ranges']
            self.is_trained = model_data['is_trained']

            logger.info(f"Modelo cargado desde: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error cargando modelo: {str(e)}")
            return False

    def get_model_info(self) -> Dict:
        """
        Retorna información sobre el modelo actual
        """
        return {
            'is_trained': self.is_trained,
            'feature_names': self.feature_names,
            'normal_ranges': self.normal_ranges,
            'model_type': 'IsolationForest' if self.model else None,
            'model_params': self.model.get_params() if self.model else None
        }


# Instancia global del detector
anomaly_detector = AnomalyDetector()