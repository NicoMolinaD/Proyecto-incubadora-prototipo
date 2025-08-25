import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import sqlite3
import schedule
import time


class AnomalyDetector:
    def __init__(self):
        self.model = IsolationForest(
            n_estimators=100,
            contamination=0.1,  # 10% de anomal�as esperadas
            random_state=42
        )
        self.is_trained = False

    def load_data(self, db_path='sensor_data.db'):
        """Cargar datos hist�ricos para entrenamiento"""
        conn = sqlite3.connect(db_path)
        query = "SELECT temperature, humidity FROM sensor_readings WHERE timestamp > datetime('now', '-7 days')"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def train(self, data=None):
        """Entrenar el modelo de detecci�n de anomal�as"""
        if data is None:
            data = self.load_data()

        if len(data) < 50:
            print("Datos insuficientes para entrenamiento")
            return False

        # Entrenar modelo
        self.model.fit(data[['temperature', 'humidity']])
        self.is_trained = True

        # Guardar modelo
        joblib.dump(self.model, 'models/anomaly_detector.pkl')
        print("Modelo entrenado y guardado correctamente")
        return True

    def predict(self, temperature, humidity):
        """Predecir si una lectura es an�mala"""
        if not self.is_trained:
            self.train()

        data_point = np.array([[temperature, humidity]])
        prediction = self.model.predict(data_point)

        # IsolationForest devuelve -1 para anomal�as, 1 para normales
        return prediction[0] == -1, self.model.decision_function(data_point)[0]


def retrain_job():
    """Tarea programada para reentrenamiento"""
    print("Ejecutando reentrenamiento programado...")
    detector = AnomalyDetector()
    detector.train()


# Programar reentrenamiento diario
schedule.every().day.at("02:00").do(retrain_job)

if __name__ == "__main__":
    # Entrenamiento inicial
    detector = AnomalyDetector()
    detector.train()

    # Ejemplo de predicci�n
    is_anomaly, score = detector.predict(36.5, 45.0)
    print(f"Predicci�n: Anomal�a={is_anomaly}, Score={score}")

    # Mantener el programa en ejecuci�n para las tareas programadas
    while True:
        schedule.run_pending()
        time.sleep(60)