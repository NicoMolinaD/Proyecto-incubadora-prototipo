const express = require('express');
const mqtt = require('mqtt');
const cors = require('cors');
const jwt = require('jsonwebtoken');

const app = express();
app.use(cors());
app.use(express.json());

// Configuración MQTT
const mqttClient = mqtt.connect('mqtt://broker.hivemq.com');
const JWT_SECRET = process.env.JWT_SECRET || 'incubadora-secret-key';

// Almacenamiento en memoria (luego reemplazar con base de datos)
let sensorData = [];
let alerts = [];

// Conexión MQTT
mqttClient.on('connect', () => {
    console.log('Conectado al broker MQTT');
    mqttClient.subscribe('incubadora/+/sensors');
});

// Recepción de datos MQTT
mqttClient.on('message', (topic, message) => {
    try {
        const data = JSON.parse(message.toString());
        console.log('Datos recibidos:', data);

        // Guardar datos
        sensorData.push({
            ...data,
            topic,
            timestamp: new Date()
        });

        // Verificar alertas (lógica simple)
        if (data.temperature > 37.5 || data.temperature < 36.0) {
            const alert = {
                type: 'temperature',
                value: data.temperature,
                threshold: data.temperature > 37.5 ? 37.5 : 36.0,
                timestamp: new Date(),
                device_id: topic.split('/')[1]
            };
            alerts.push(alert);
            console.log('ALERTA:', alert);
        }
    } catch (error) {
        console.error('Error procesando mensaje MQTT:', error);
    }
});

// Rutas HTTP
app.post('/api/auth/login', (req, res) => {
    // Autenticación simple (en producción usar base de datos)
    const { username, password } = req.body;

    if (username === 'admin' && password === 'password') {
        const token = jwt.sign({ userId: 1, username }, JWT_SECRET, { expiresIn: '1h' });
        return res.json({ token, user: { id: 1, username, role: 'admin' } });
    }

    res.status(401).json({ error: 'Credenciales inválidas' });
});

app.get('/api/sensor-data', authenticateToken, (req, res) => {
    res.json(sensorData.slice(-100)); // Últimos 100 registros
});

app.get('/api/alerts', authenticateToken, (req, res) => {
    res.json(alerts.slice(-20)); // Últimas 20 alertas
});

// Middleware de autenticación
function authenticateToken(req, res, next) {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];

    if (!token) return res.sendStatus(401);

    jwt.verify(token, JWT_SECRET, (err, user) => {
        if (err) return res.sendStatus(403);
        req.user = user;
        next();
    });
}

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
    console.log(`Servidor Express ejecutándose en puerto ${PORT}`);
});