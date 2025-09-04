"""
Tests para el módulo de machine learning del sistema de incubadora
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
import tempfile
import os

from app.ml.anomaly_detector import AnomalyDetector


class TestAnomalyDetector:
    """Tests para la clase AnomalyDetector"""

    @pytest.fixture
    def detector(self):
        """Fixture que retorna una instancia fresca del detector"""
        return AnomalyDetector()

    @pytest.fixture
    def sample_data(self):
        """Fixture con datos de ejemplo para testing"""
        np.random.seed(42)
        n_samples = 100

        data = {
            'temperatura': np.random.normal(36.5, 0.2, n_samples),
            'humedad': np.random.normal(55, 5, n_samples),
            'oxigeno': np.random.normal(95, 3, n_samples),
            'frecuencia_cardiaca': np.random.normal(130, 10, n_samples),
            'frecuencia_respiratoria': np.random.normal(45, 5, n_samples),
            'presion_arterial_sistolica': np.random.normal(70, 8, n_samples),
            'presion_arterial_diastolica': np.random.normal(40, 5, n_samples)
        }

        return pd.DataFrame(data)

    @pytest.fixture
    def anomalous_data(self):
        """Fixture con datos anómalos para testing"""
        return {
            'temperatura': 40.0,  # Muy alta
            'humedad': 90.0,  # Muy alta
            'oxigeno': 80.0,  # Baja
            'frecuencia_cardiaca': 200,  # Muy alta
            'frecuencia_respiratoria': 70,  # Alta
            'presion_arterial_sistolica': 100,  # Alta
            'presion_arterial_diastolica': 60  # Alta
        }

    @pytest.fixture
    def normal_data(self):
        """Fixture con datos normales para testing"""
        return {
            'temperatura': 36.7,
            'humedad': 55.0,
            'oxigeno': 95.0,
            'frecuencia_cardiaca': 130,
            'frecuencia_respiratoria': 45,
            'presion_arterial_sistolica': 70,
            'presion_arterial_diastolica': 40
        }

    def test_init(self, detector):
        """Test inicialización del detector"""
        assert detector.model is None
        assert not detector.is_trained
        assert len(detector.feature_names) == 7
        assert len(detector.normal_ranges) == 7

    def test_prepare_data_success(self, detector, sample_data):
        """Test preparación exitosa de datos"""
        prepared = detector.prepare_data(sample_data)

        # Verificar que se agregaron características derivadas
        expected_cols = detector.feature_names + [
            'temp_deviation', 'humidity_deviation', 'hr_rr_ratio', 'bp_diff'
        ]
        assert all(col in prepared.columns for col in expected_cols)
        assert len(prepared) <= len(sample_data)  # Puede ser menor por dropna

    def test_prepare_data_missing_features(self, detector):
        """Test preparación de datos con características faltantes"""
        incomplete_data = pd.DataFrame({
            'temperatura': [36.5],
            'humedad': [55.0]
        })

        with pytest.raises(ValueError, match="Faltan las siguientes características"):
            detector.prepare_data(incomplete_data)

    def test_train_success(self, detector, sample_data):
        """Test entrenamiento exitoso del modelo"""
        result = detector.train(sample_data)

        assert detector.is_trained
        assert detector.model is not None
        assert result['status'] == 'success'
        assert result['samples_trained'] > 0
        assert 'anomaly_rate' in result

    def test_train_insufficient_data(self, detector):
        """Test entrenamiento con datos insuficientes"""
        small_data = pd.DataFrame({
            col: [36.5] * 10 for col in detector.feature_names
        })

        with pytest.raises(ValueError, match="Se necesitan al menos 50 muestras"):
            detector.train(small_data)

    def test_predict_without_training(self, detector, normal_data):
        """Test predicción sin entrenar el modelo"""
        with pytest.raises(ValueError, match="El modelo no ha sido entrenado"):
            detector.predict(normal_data)

    def test_predict_normal_data(self, detector, sample_data, normal_data):
        """Test predicción con datos normales"""
        detector.train(sample_data)
        result = detector.predict(normal_data)

        assert 'is_anomaly' in result
        assert 'anomaly_score' in result
        assert 'alert_level' in result
        assert 'range_violations' in result
        assert 'timestamp' in result
        assert 'confidence' in result
        assert isinstance(result['is_anomaly'], bool)

    def test_predict_anomalous_data(self, detector, sample_data, anomalous_data):
        """Test predicción con datos anómalos"""
        detector.train(sample_data)
        result = detector.predict(anomalous_data)

        # Los datos anómalos deberían ser detectados
        assert len(result['range_violations']) > 0
        assert result['alert_level'] != 'NORMAL'

    def test_check_normal_ranges_violations(self, detector, anomalous_data):
        """Test verificación de violaciones de rangos normales"""
        violations = detector._check_normal_ranges(anomalous_data)

        assert len(violations) > 0
        for violation in violations:
            assert 'parameter' in violation
            assert 'value' in violation
            assert 'normal_range' in violation
            assert 'deviation' in violation

    def test_check_normal_ranges_no_violations(self, detector, normal_data):
        """Test verificación sin violaciones"""
        violations = detector._check_normal_ranges(normal_data)
        assert len(violations) == 0

    def test_determine_alert_level_critical(self, detector):
        """Test determinación de nivel crítico"""
        critical_violations = [
            {'parameter': 'temperatura', 'value': 40.0, 'normal_range': [36.0, 37.5], 'deviation': 2.5}
        ]

        level = detector._determine_alert_level(-1, -0.2, critical_violations)
        assert level == 'CRITICO'

    def test_determine_alert_level_normal(self, detector):
        """Test determinación de nivel normal"""
        level = detector._determine_alert_level(1, 0.1, [])
        assert level == 'NORMAL'

    def test_save_and_load_model(self, detector, sample_data):
        """Test guardado y carga del modelo"""
        # Entrenar modelo
        detector.train(sample_data)

        # Guardar en archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as tmp:
            tmp_path = tmp.name

        try:
            # Guardar modelo
            success = detector.save_model(tmp_path)
            assert success
            assert os.path.exists(tmp_path)

            # Crear nuevo detector y cargar modelo
            new_detector = AnomalyDetector()
            load_success = new_detector.load_model(tmp_path)

            assert load_success
            assert new_detector.is_trained
            assert new_detector.model is not None

        finally:
            # Limpiar archivo temporal
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_save_model_not_trained(self, detector):
        """Test guardado de modelo no entrenado"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as tmp:
            tmp_path = tmp.name

        try:
            success = detector.save_model(tmp_path)
            assert not success

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_load_nonexistent_model(self, detector):
        """Test carga de modelo inexistente"""
        success = detector.load_model('nonexistent_file.pkl')
        assert not success
        assert not detector.is_trained

    def test_get_model_info_untrained(self, detector):
        """Test información de modelo no entrenado"""
        info = detector.get_model_info()

        assert not info['is_trained']
        assert info['model_type'] is None
        assert info['model_params'] is None
        assert 'feature_names' in info
        assert 'normal_ranges' in info

    def test_get_model_info_trained(self, detector, sample_data):
        """Test información de modelo entrenado"""
        detector.train(sample_data)
        info = detector.get_model_info()

        assert info['is_trained']
        assert info['model_type'] == 'IsolationForest'
        assert info['model_params'] is not None
        assert 'feature_names' in info
        assert 'normal_ranges' in info


@pytest.mark.integration
class TestAnomalyDetectorIntegration:
    """Tests de integración para el detector de anomalías"""

    def test_full_workflow(self):
        """Test del flujo completo de entrenamiento y predicción"""
        detector = AnomalyDetector()

        # Generar datos de entrenamiento
        np.random.seed(42)
        training_data = pd.DataFrame({
            'temperatura': np.random.normal(36.5, 0.2, 200),
            'humedad': np.random.normal(55, 5, 200),
            'oxigeno': np.random.normal(95, 3, 200),
            'frecuencia_cardiaca': np.random.normal(130, 10, 200),
            'frecuencia_respiratoria': np.random.normal(45, 5, 200),
            'presion_arterial_sistolica': np.random.normal(70, 8, 200),
            'presion_arterial_diastolica': np.random.normal(40, 5, 200)
        })

        # Entrenar modelo
        train_result = detector.train(training_data)
        assert train_result['status'] == 'success'

        # Probar con datos normales
        normal_sample = {
            'temperatura': 36.6,
            'humedad': 55.0,
            'oxigeno': 95.0,
            'frecuencia_cardiaca': 130,
            'frecuencia_respiratoria': 45,
            'presion_arterial_sistolica': 70,
            'presion_arterial_diastolica': 40
        }

        normal_result = detector.predict(normal_sample)
        assert normal_result['alert_level'] in ['NORMAL', 'BAJO']

        # Probar con datos anómalos
        anomalous_sample = {
            'temperatura': 39.5,  # Muy alta
            'humedad': 90.0,  # Muy alta
            'oxigeno': 85.0,  # Baja
            'frecuencia_cardiaca': 190,  # Muy alta
            'frecuencia_respiratoria': 65,  # Alta
            'presion_arterial_sistolica': 95,  # Alta
            'presion_arterial_diastolica': 55  # Alta
        }

        anomalous_result = detector.predict(anomalous_sample)
        assert len(anomalous_result['range_violations']) > 0
        assert anomalous_result['alert_level'] in ['ALTO', 'CRITICO']


if __name__ == '__main__':
    pytest.main([__file__])