/**
 * Utilidades y helpers compartidos para el sistema de incubadora neonatal (Node.js)
 */

const crypto = require('crypto');
const fs = require('fs').promises;
const path = require('path');

/**
 * Valida rangos de sensores
 * @param {Object} sensorData - Datos de sensores
 * @returns {Array} Array de violaciones encontradas
 */
function validateSensorRanges(sensorData) {
    // Rangos aceptables para sensores
    const acceptableRanges = {
        temperatura: [30.0, 45.0],  // °C
        humedad: [0.0, 100.0],      // %
        oxigeno: [15.0, 100.0],     // %
        frecuencia_cardiaca: [50, 250],  // bpm
        frecuencia_respiratoria: [10, 100],  // rpm
        presion_arterial_sistolica: [30, 150],   // mmHg
        presion_arterial_diastolica: [15, 100]   // mmHg
    };

    const violations = [];

    for (const [parameter, value] of Object.entries(sensorData)) {
        if (acceptableRanges[parameter]) {
            const [minVal, maxVal] = acceptableRanges[parameter];

            if (typeof value !== 'number' || isNaN(value)) {
                violations.push({
                    parameter,
                    value,
                    error: 'Invalid data type, expected number',
                    acceptable_range: [minVal, maxVal]
                });
            } else if (value < minVal || value > maxVal) {
                violations.push({
                    parameter,
                    value,
                    error: 'Value outside acceptable range',
                    acceptable_range: [minVal, maxVal]
                });
            }
        }
    }

    return violations;
}

/**
 * Genera un timestamp actual en formato ISO
 * @returns {string} Timestamp en formato ISO UTC
 */
function getCurrentTimestamp() {
    return new Date().toISOString();
}

/**
 * Genera un token seguro aleatorio
 * @param {number} length - Longitud del token en bytes (default: 32)
 * @returns {string} Token en formato hexadecimal
 */
function generateSecureToken(length = 32) {
    return crypto.randomBytes(length).toString('hex');
}

/**
 * Hashea una contraseña de forma segura usando PBKDF2
 * @param {string} password - Contraseña en texto plano
 * @param {string} salt - Salt (opcional, se genera uno si no se proporciona)
 * @returns {Object} Objeto con hash y salt
 */
function hashPassword(password, salt = null) {
    if (!salt) {
        salt = crypto.randomBytes(16).toString('hex');
    }

    const hash = crypto.pbkdf2Sync(password, salt, 100000, 64, 'sha256').toString('hex');

    return { hash, salt };
}

/**
 * Verifica una contraseña contra su hash
 * @param {string} password - Contraseña en texto plano
 * @param {string} hashedPassword - Hash de la contraseña
 * @param {string} salt - Salt usado para el hash
 * @returns {boolean} True si la contraseña es correcta
 */
function verifyPassword(password, hashedPassword, salt) {
    const hash = crypto.pbkdf2Sync(password, salt, 100000, 64, 'sha256').toString('hex');
    return hash === hashedPassword;
}

/**
 * Parsea JSON de forma segura
 * @param {string} jsonString - String JSON a parsear
 * @param {*} defaultValue - Valor por defecto si falla el parsing
 * @returns {*} Objeto parseado o valor por defecto
 */
function safeJsonParse(jsonString, defaultValue = null) {
    try {
        return JSON.parse(jsonString);
    } catch (error) {
        return defaultValue;
    }
}

/**
 * Serializa objeto a JSON de forma segura
 * @param {*} obj - Objeto a serializar
 * @param {string} defaultValue - Valor por defecto si falla la serialización
 * @returns {string} String JSON o valor por defecto
 */
function safeJsonStringify(obj, defaultValue = 'null') {
    try {
        return JSON.stringify(obj);
    } catch (error) {
        return defaultValue;
    }
}

/**
 * Sanitiza un nombre de archivo eliminando caracteres peligrosos
 * @param {string} filename - Nombre de archivo original
 * @returns {string} Nombre de archivo sanitizado
 */
function sanitizeFilename(filename) {
    const invalidChars = /[<>:"/\\|?*]/g;
    let sanitized = filename.replace(invalidChars, '_');

    sanitized = sanitized.trim();

    if (!sanitized) {
        sanitized = `file_${getCurrentTimestamp().replace(/:/g, '-')}`;
    }

    return sanitized;
}

/**
 * Calcula estadísticas básicas de un array de números
 * @param {number[]} data - Array de números
 * @returns {Object} Objeto con estadísticas
 */
function calculateStatistics(data) {
    if (!Array.isArray(data) || data.length === 0) {
        return {
            count: 0,
            min: null,
            max: null,
            mean: null,
            median: null
        };
    }

    const sortedData = [...data].sort((a, b) => a - b);
    const n = data.length;

    // Mediana
    let median;
    if (n % 2 === 0) {
        median = (sortedData[n / 2 - 1] + sortedData[n / 2]) / 2;
    } else {
        median = sortedData[Math.floor(n / 2)];
    }

    return {
        count: n,
        min: Math.min(...data),
        max: Math.max(...data),
        mean: data.reduce((sum, val) => sum + val, 0) / n,
        median
    };
}

/**
 * Formatea un mensaje de alerta de forma consistente
 * @param {string} alertLevel - Nivel de alerta
 * @param {string} parameter - Parámetro afectado
 * @param {number} value - Valor actual
 * @param {number[]} normalRange - Rango normal [min, max]
 * @returns {string} Mensaje formateado
 */
function formatAlertMessage(alertLevel, parameter, value, normalRange) {
    const [minVal, maxVal] = normalRange;

    let status, deviation;
    if (value < minVal) {
        status = "BAJO";
        deviation = minVal - value;
    } else {
        status = "ALTO";
        deviation = value - maxVal;
    }

    return `ALERTA ${alertLevel}: ${parameter.toUpperCase()} ${status} - ` +
           `Valor: ${value.toFixed(2)}, Rango normal: ${minVal}-${maxVal}, ` +
           `Desviación: ${deviation.toFixed(2)}`;
}

/**
 * Divide un array en chunks de tamaño específico
 * @param {Array} array - Array a dividir
 * @param {number} chunkSize - Tamaño de cada chunk
 * @returns {Array[]} Array de chunks
 */
function chunkArray(array, chunkSize) {
    const chunks = [];
    for (let i = 0; i < array.length; i += chunkSize) {
        chunks.push(array.slice(i, i + chunkSize));
    }
    return chunks;
}

/**
 * Ejecuta una operación con reintentos en caso de error
 * @param {Function} operation - Función a ejecutar
 * @param {number} maxRetries - Número máximo de reintentos (default: 3)
 * @param {number} delay - Delay entre reintentos en ms (default: 1000)
 * @returns {Promise} Resultado de la operación
 */
async function retryOperation(operation, maxRetries = 3, delay = 1000) {
    let lastError;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            return await operation();
        } catch (error) {
            lastError = error;
            if (attempt < maxRetries) {
                console.warn(`Operation failed (attempt ${attempt + 1}/${maxRetries + 1}): ${error.message}`);
                await new Promise(resolve => setTimeout(resolve, delay));
            } else {
                console.error(`Operation failed after ${maxRetries + 1} attempts: ${error.message}`);
            }
        }
    }

    throw lastError;
}

/**
 * Valida un objeto de datos de sensor
 * @param {Object} sensorData - Datos del sensor
 * @returns {Object} Resultado de validación con isValid y errors
 */
function validateSensorData(sensorData) {
    const errors = [];
    const requiredFields = [
        'temperatura',
        'humedad',
        'oxigeno',
        'frecuencia_cardiaca',
        'frecuencia_respiratoria',
        'presion_arterial_sistolica',
        'presion_arterial_diastolica'
    ];

    // Verificar campos requeridos
    for (const field of requiredFields) {
        if (!(field in sensorData)) {
            errors.push(`Missing required field: ${field}`);
        }
    }

    // Verificar tipos de datos
    for (const [field, value] of Object.entries(sensorData)) {
        if (requiredFields.includes(field)) {
            if (typeof value !== 'number' || isNaN(value)) {
                errors.push(`Invalid data type for ${field}: expected number`);
            }
        }
    }

    // Verificar rangos si no hay errores de tipo
    if (errors.length === 0) {
        const rangeViolations = validateSensorRanges(sensorData);
        errors.push(...rangeViolations.map(v => v.error + ` for ${v.parameter}`));
    }

    return {
        isValid: errors.length === 0,
        errors
    };
}

/**
 * Genera un ID único usando timestamp y random
 * @returns {string} ID único
 */
function generateUniqueId() {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substr(2, 9);
    return `${timestamp}_${random}`;
}

/**
 * Convierte un objeto plano a estructura anidada usando notación de puntos
 * @param {Object} obj - Objeto plano
 * @param {string} separator - Separador (default: '.')
 * @returns {Object} Objeto anidado
 */
function unflattenObject(obj, separator = '.') {
    const result = {};

    for (const [key, value] of Object.entries(obj)) {
        const keys = key.split(separator);
        let current = result;

        for (let i = 0; i < keys.length - 1; i++) {
            const k = keys[i];
            if (!(k in current)) {
                current[k] = {};
            }
            current = current[k];
        }

        current[keys[keys.length - 1]] = value;
    }

    return result;
}

/**
 * Convierte un objeto anidado a estructura plana usando notación de puntos
 * @param {Object} obj - Objeto anidado
 * @param {string} prefix - Prefijo para las claves
 * @param {string} separator - Separador (default: '.')
 * @returns {Object} Objeto plano
 */
function flattenObject(obj, prefix = '', separator = '.') {
    const result = {};

    for (const [key, value] of Object.entries(obj)) {
        const newKey = prefix ? `${prefix}${separator}${key}` : key;

        if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
            Object.assign(result, flattenObject(value, newKey, separator));
        } else {
            result[newKey] = value;
        }
    }

    return result;
}

/**
 * Calcula la diferencia entre dos timestamps
 * @param {string|Date} timestamp1 - Primer timestamp
 * @param {string|Date} timestamp2 - Segundo timestamp
 * @returns {number} Diferencia en milisegundos
 */
function getTimestampDifference(timestamp1, timestamp2) {
    const date1 = new Date(timestamp1);
    const date2 = new Date(timestamp2);
    return Math.abs(date2.getTime() - date1.getTime());
}

/**
 * Formatea duración en milisegundos a string legible
 * @param {number} milliseconds - Duración en milisegundos
 * @returns {string} Duración formateada
 */
function formatDuration(milliseconds) {
    const seconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) {
        return `${days}d ${hours % 24}h ${minutes % 60}m`;
    } else if (hours > 0) {
        return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
        return `${minutes}m ${seconds % 60}s`;
    } else {
        return `${seconds}s`;
    }
}

/**
 * Clase para gestión de configuración
 */
class ConfigManager {
    constructor(configFile = 'config.json') {
        this.configFile = configFile;
        this.config = {};
        this.loadConfig();
    }

    /**
     * Carga configuración desde archivo
     */
    async loadConfig() {
        try {
            const data = await fs.readFile(this.configFile, 'utf8');
            this.config = JSON.parse(data);
        } catch (error) {
            console.warn(`Error loading config file ${this.configFile}: ${error.message}`);
            this.config = {};
        }
    }

    /**
     * Guarda configuración a archivo
     * @returns {Promise<boolean>} True si se guardó exitosamente
     */
    async saveConfig() {
        try {
            await fs.writeFile(this.configFile, JSON.stringify(this.config, null, 2));
            return true;
        } catch (error) {
            console.error(`Error saving config file ${this.configFile}: ${error.message}`);
            return false;
        }
    }

    /**
     * Obtiene valor de configuración
     * @param {string} key - Clave
     * @param {*} defaultValue - Valor por defecto
     * @returns {*} Valor de configuración
     */
    get(key, defaultValue = null) {
        return this.config[key] !== undefined ? this.config[key] : defaultValue;
    }

    /**
     * Establece valor de configuración
     * @param {string} key - Clave
     * @param {*} value - Valor
     */
    set(key, value) {
        this.config[key] = value;
    }

    /**
     * Obtiene valor anidado usando notación de puntos
     * @param {string} path - Ruta usando puntos (ej: 'database.host')
     * @param {*} defaultValue - Valor por defecto
     * @param {string} separator - Separador (default: '.')
     * @returns {*} Valor anidado
     */
    getNested(path, defaultValue = null, separator = '.') {
        const keys = path.split(separator);
        let value = this.config;

        try {
            for (const key of keys) {
                value = value[key];
            }
            return value !== undefined ? value : defaultValue;
        } catch {
            return defaultValue;
        }
    }

    /**
     * Establece valor anidado usando notación de puntos
     * @param {string} path - Ruta usando puntos
     * @param {*} value - Valor
     * @param {string} separator - Separador (default: '.')
     */
    setNested(path, value, separator = '.') {
        const keys = path.split(separator);
        let current = this.config;

        for (let i = 0; i < keys.length - 1; i++) {
            const key = keys[i];
            if (!(key in current) || typeof current[key] !== 'object') {
                current[key] = {};
            }
            current = current[key];
        }

        current[keys[keys.length - 1]] = value;
    }
}

/**
 * Logger simple para Node.js
 */
class Logger {
    constructor(name = 'incubadora_neonatal') {
        this.name = name;
    }

    _log(level, message, ...args) {
        const timestamp = new Date().toISOString();
        console.log(`${timestamp} - ${this.name} - ${level.toUpperCase()} - ${message}`, ...args);
    }

    debug(message, ...args) {
        this._log('debug', message, ...args);
    }

    info(message, ...args) {
        this._log('info', message, ...args);
    }

    warn(message, ...args) {
        this._log('warn', message, ...args);
    }

    error(message, ...args) {
        this._log('error', message, ...args);
    }
}

// Exportar todas las funciones y clases
module.exports = {
    validateSensorRanges,
    getCurrentTimestamp,
    generateSecureToken,
    hashPassword,
    verifyPassword,
    safeJsonParse,
    safeJsonStringify,
    sanitizeFilename,
    calculateStatistics,
    formatAlertMessage,
    chunkArray,
    retryOperation,
    validateSensorData,
    generateUniqueId,
    unflattenObject,
    flattenObject,
    getTimestampDifference,
    formatDuration,
    ConfigManager,
    Logger
};