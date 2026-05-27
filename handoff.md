# EGGSORT — Handoff de proyecto

> Referencia interna para continuidad entre sesiones.  
> Última actualización: Mayo 2026

---

## 1. Descripción

EggSort es un prototipo de bajo costo para clasificación automatizada de huevos de aves. El sistema pesa cada huevo con una celda de carga HX711, lo clasifica en tres categorías (S, M, L) y activa un servo modificado para rotación continua que desvía el huevo al canal correspondiente mediante un mecanismo físico en forma de C.

Proyecto académico — Robótica, 5° semestre, Ingeniería de Software. Gestionado bajo Scrum.

---

## 2. Hardware

| Componente | Detalle |
|---|---|
| Microcontrolador | Arduino |
| Sensor de peso | Celda de carga 5 kg + módulo HX711 (DAT→A0, CLK→A1) |
| Actuador | Servo SG90 modificado para rotación continua 360° (Pin 9) |
| Estructura física | Mecanismo en C sobre riel de clasificación — 3 canales: S, M, L |
| Comunicación | Serial 9600 baud, comandos por newline |

---

## 3. Lógica de clasificación

| Categoría | Rango | Dirección servo (Ida) | Dirección servo (Retorno) |
|---|---|---|---|
| S (Small) | < 53 g | CW — tiempo `PS` (500ms) | CCW — tiempo `RS` (500ms) |
| M (Medium) | 53–62 g | CW — tiempo `PM` (700ms) | CCW — tiempo `RM` (700ms) |
| L (Large) | > 62 g | CCW — tiempo `PL` (900ms) | CW — tiempo `RL` (900ms) |

El servo 360° no controla ángulos sino velocidad. El control de posición se hace por **tiempo de giro**. Todos los tiempos deben determinarse empíricamente en la práctica.

---

## 4. Estado actual

| Componente / tarea | Estado |
|---|---|
| Firmware base (clasificación + comandos serial) | ✅ Completo |
| Servo 360° — punto neutro calibrado | ✅ Completo |
| Estructura física (mecanismo en C + rieles) | ✅ Funcional |
| Fijación mecánica del horn del servo | ✅ Resuelto |
| Tiempos de retorno por canal (RS, RM, RL) | ✅ Implementado |
| Ciclo completo: pesar → desviar → regresar | ✅ Implementado |
| Soporte de pesos simulados (M<peso>) | ✅ Implementado |
| Aplicación de pruebas y calibración (`test_sort.py`) | ✅ Implementado |
| Celda de carga HX711 — instalación física | ⏳ Pendiente |
| Calibración del factor HX711 (comando `K`) | ⏳ Pendiente |
| Calibración de tiempos (PS, PM, PL, RS, RM, RL) | ⏳ Pendiente |

---

## 5. Ciclo Completo y Retorno de la C

El ciclo completo por huevo tiene tres fases implementadas en `measureAndSort()`:

1. **Pesar el huevo:** Clasificar en S, M o L. Se puede usar el sensor real o ingresar un peso simulado por serial (e.g. `M55.0`) para pruebas sin sensor.
2. **Girar a canal:** Girar la C hacia el canal (CW para S/M, CCW para L) durante el tiempo calibrado (`TS`, `TM`, `TL`).
3. **Retorno a origen:** Esperar `T_ESPERA_HUEVO` (1000ms) para que el huevo caiga en el riel, y luego girar en la dirección inversa por el tiempo de retorno respectivo (`RS`, `RM`, `RL`) para regresar la C a su posición de inicio.

---

## 6. Retos identificados

**Mecánicos — resueltos**
- Horn del servo patinaba sobre el eje → resuelto apretando tornillo y verificando encaje en estrías del eje

**Electrónicos — en proceso**
- Celda de carga pendiente de instalación física
- Factor de calibración K aún no determinado — requiere pesa de referencia conocida
- Neutro real del servo estaba fuera del rango 80–100 del firmware original → corregido, rango ampliado a 80–140

**Firmware — resueltos**
- Tiempos de retorno RS, RM, RL implementados y configurables.
- Conflicto de comandos resuelto: los comandos de dos caracteres (`TS`, `TM`, `TL`, `RS`, `RM`, `RL`, `TC`) ahora se filtran primero en `handleCommand()` para evitar que colisionen con `T` (Tare) y causen tara involuntaria.

---

## 7. Referencia de comandos serial

| Comando | Función | Estado |
|---|---|---|
| `T` | Tara la balanza | ✅ |
| `M` | Medición única en sensor real + sorteo | ✅ |
| `M<peso>` | Simula peso (e.g. `M55.5`), sorteo inmediato bypass sensor | ✅ |
| `A` | Toggle modo automático (loop cada 3 s) | ✅ |
| `L` | Toggle lectura en vivo sin sorteo | ✅ |
| `S` | Stop — detiene todo y mata señal PWM | ✅ |
| `K<val>` | Set factor de calibración HX711 | ✅ |
| `N<val>` | Set punto neutro del servo (rango 80–140) | ✅ |
| `TS<ms>` | Set tiempo de ida canal S | ✅ |
| `TM<ms>` | Set tiempo de ida canal M | ✅ |
| `TL<ms>` | Set tiempo de ida canal L | ✅ |
| `RS<ms>` | Set tiempo de retorno canal S | ✅ |
| `RM<ms>` | Set tiempo de retorno canal M | ✅ |
| `RL<ms>` | Set tiempo de retorno canal L | ✅ |
| `TCCW` | Test continuo CW hasta recibir S | ✅ |
| `TCCCW` | Test continuo CCW hasta recibir S | ✅ |
| `?` | Query estado actual de todos los parámetros | ✅ |

---

## 8. Próximos pasos (orden sugerido)

1. **Pruebas en PC con `test_sort.py`:**
   Ejecutar `python3 test_sort.py` para verificar los tiempos de giro y retorno de la C físicamente usando pesos simulados (S: 45g, M: 57g, L: 68g) sin necesidad de conectar la celda de carga.
2. **Instalar celda de carga HX711** físicamente en la plataforma de pesaje.
3. **Calibrar factor `K`** con pesa de referencia conocida (usar live-mode con `L` para ver lectura en vivo y `K<val>` para ajustar).
4. **Calibrar tiempos finales (`TS`, `TM`, `TL`, `RS`, `RM`, `RL`)** con huevos reales.
5. **Comitear/sincronizar cambios** adicionales en el repositorio de GitHub: `https://github.com/sebastian66cs/eggsort.git`.
