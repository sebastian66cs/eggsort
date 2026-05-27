// EGGSORT — HX711 Weight Classification + Servo Sorting
// Servo MODIFICADO para rotación continua (360°)
//
// Wiring:
//   HX711 DAT → A0, CLK → A1
//   Servo signal → Pin 9, VCC → 5V, GND → GND
//
// Clasificación por peso:
//   S (Small)  < 53g  → Canal S
//   M (Medium) 53-62g → Canal M
//   L (Large)  > 62g  → Canal L
//
// Para servo 360°, el control es por TIEMPO, no por ángulo.
// Calibrá los tiempos con el comando de prueba antes de usar en producción.
//
// Serial protocol (9600 baud, newline-terminated):
//   T          — Tare the scale
//   M          — Single measurement + sort
//   A          — Toggle auto mode (continuous measure+sort)
//   L          — Toggle live weight reading (no sorting)
//   S          — Stop all modes, detach servo (kills PWM signal)
//   K<val>     — Set calibration factor (e.g. K420.0)
//   N<val>     — Set servo neutral point (e.g. N90). Default 90.
//   TS<ms>     — Set tiempo giro canal S en ms (e.g. TS500)
//   TM<ms>     — Set tiempo giro canal M en ms (e.g. TM700)
//   TL<ms>     — Set tiempo giro canal L en ms (e.g. TL900)
//   TW<ms>     — Set tiempo espera huevo entre ida y retorno (e.g. TW1000)
//   TC<dir>    — Test continuo: gira en dir (CW o CCW) hasta recibir S
//   GP<dir><ms>— Go Pulse: giro temporizado (e.g. GPCW500, GPCCW300)
//   VCW<val>   — Set velocidad CW (0-89, más bajo=más rápido). Default 80.
//   VCCW<val>  — Set velocidad CCW (91-180, más alto=más rápido). Default 100.
//   SAVE       — Save current configuration (speeds, timings, cal) to EEPROM
//   ?          — Query current status

#include <HX711.h>
#include <Servo.h>
#include <EEPROM.h>

#define DAT_PIN   A0
#define CLK_PIN   A1
#define SERVO_PIN 9

// ── Velocidades del servo 360° modificado ──────────────────────────────────
// El servo modificado interpreta el pulso como velocidad, no posición:
//   ~90  → STOP (valor exacto depende del trimmer de tu servo específico)
//   < 90 → gira en sentido CW, más lento cuanto más cerca de 90
//   > 90 → gira en sentido CCW, más lento cuanto más cerca de 90
//   0    → CW máxima velocidad
//   180  → CCW máxima velocidad
//
// IMPORTANTE: Ajustá SERVO_STOP con el comando N<val> hasta que el servo
// quede completamente inmóvil. Ese es tu punto neutro real.
// ──────────────────────────────────────────────────────────────────────────
int   servo_stop  = 90;   // Punto neutro — ajustar con comando N<val>
int   servo_cw    = 80;   // Velocidad CW (0=máx, 89=mín) — ajustar con VCW<val>
int   servo_ccw   = 100;  // Velocidad CCW (180=máx, 91=mín) — ajustar con VCCW<val>

// ── Tiempos de giro por canal (ms) ────────────────────────────────────────
// Estos valores determinan cuánto tiempo gira el servo hacia cada canal.
// Ajustar empíricamente con los comandos TS, TM, TL.
// Empezá con valores pequeños (ej. 300ms) e incrementá de a 50ms.
// ──────────────────────────────────────────────────────────────────────────
unsigned long t_canal_s = 500;   // ms para canal S — AJUSTAR
unsigned long t_canal_m = 700;   // ms para canal M — AJUSTAR
unsigned long t_canal_l = 900;   // ms para canal L — AJUSTAR

// ── Tiempos de retorno por canal (ms) ──────────────────────────────────────
// Estos valores determinan cuánto tiempo gira el servo en reversa.
// Ajustar empíricamente con los comandos RS, RM, RL.
// ──────────────────────────────────────────────────────────────────────────
unsigned long t_retorno_s = 500;  // ms para retorno canal S — AJUSTAR
unsigned long t_retorno_m = 700;  // ms para retorno canal M — AJUSTAR
unsigned long t_retorno_l = 900;  // ms para retorno canal L — AJUSTAR

// Tiempo de espera para que el huevo ruede al riel antes del retorno
// Ajustable con comando TW<ms>
unsigned long T_ESPERA_HUEVO = 1000;

// ── Tiempo de frenado post-giro ────────────────────────────────────────────
// Margen para que el servo responda al pulso de STOP antes del detach.
// No bajar de 150ms.
// ──────────────────────────────────────────────────────────────────────────
const unsigned long T_BRAKE = 200;

HX711 balanza;
Servo servo;

bool  hx711_ok = false;
float factor_calibracion = 420.0;
bool  auto_mode  = false;
bool  live_mode  = false;

unsigned long last_live = 0;
const unsigned long LIVE_INTERVAL = 300;

void handleCommand();
void measureAndSort(float mock_weight = -1.0);
void readLive();
void actuarServo(int velocidad, unsigned long tiempo_ms);

#define EEPROM_MAGIC 0x45

struct ConfigData {
  byte magic;
  int servo_stop;
  int servo_cw;
  int servo_ccw;
  unsigned long t_canal_s;
  unsigned long t_canal_m;
  unsigned long t_canal_l;
  unsigned long t_retorno_s;
  unsigned long t_retorno_m;
  unsigned long t_retorno_l;
  unsigned long t_espera_huevo;
  float factor_calibracion;
};

void loadConfig() {
  ConfigData cfg;
  EEPROM.get(0, cfg);
  if (cfg.magic == EEPROM_MAGIC) {
    servo_stop = cfg.servo_stop;
    servo_cw = cfg.servo_cw;
    servo_ccw = cfg.servo_ccw;
    t_canal_s = cfg.t_canal_s;
    t_canal_m = cfg.t_canal_m;
    t_canal_l = cfg.t_canal_l;
    t_retorno_s = cfg.t_retorno_s;
    t_retorno_m = cfg.t_retorno_m;
    t_retorno_l = cfg.t_retorno_l;
    T_ESPERA_HUEVO = cfg.t_espera_huevo;
    factor_calibracion = cfg.factor_calibracion;
    Serial.println("EEPROM_LOADED");
  } else {
    Serial.println("EEPROM_DEFAULT");
  }
}

void saveConfig() {
  ConfigData cfg;
  cfg.magic = EEPROM_MAGIC;
  cfg.servo_stop = servo_stop;
  cfg.servo_cw = servo_cw;
  cfg.servo_ccw = servo_ccw;
  cfg.t_canal_s = t_canal_s;
  cfg.t_canal_m = t_canal_m;
  cfg.t_canal_l = t_canal_l;
  cfg.t_retorno_s = t_retorno_s;
  cfg.t_retorno_m = t_retorno_m;
  cfg.t_retorno_l = t_retorno_l;
  cfg.t_espera_huevo = T_ESPERA_HUEVO;
  cfg.factor_calibracion = factor_calibracion;
  EEPROM.put(0, cfg);
  Serial.println("OK SAVED_TO_EEPROM");
}

void setup() {
  Serial.begin(9600);
  loadConfig();

  // ── HX711 init con timeout ─────────────────────────────────────
  // Si el sensor no está conectado, is_ready() nunca retorna true
  // y tare() bloquearía para siempre. Esperamos hasta 2 s.
  // ──────────────────────────────────────────────────────────────
  balanza.begin(DAT_PIN, CLK_PIN);
  balanza.set_scale(factor_calibracion);

  unsigned long t0 = millis();
  while (!balanza.is_ready() && millis() - t0 < 2000) {
    delay(10);
  }

  if (balanza.is_ready()) {
    balanza.tare();
    hx711_ok = true;
    Serial.println("HX711_OK");
  } else {
    hx711_ok = false;
    Serial.println("HX711_NOT_FOUND — mock weights only (M<peso>)");
  }

  // Inicializar servo al neutro y desconectar para matar la señal PWM.
  // Esto evita el salto inicial en el primer attach().
  servo.attach(SERVO_PIN);
  servo.write(servo_stop);
  delay(600);
  servo.detach();

  Serial.println("EGGSORT_READY");
  Serial.print("CAL=");
  Serial.println(factor_calibracion, 1);
  Serial.print("NEUTRAL=");
  Serial.println(servo_stop);
  Serial.print("VCW=");
  Serial.print(servo_cw);
  Serial.print(" VCCW=");
  Serial.println(servo_ccw);
  Serial.print("T_S=");
  Serial.print(t_canal_s);
  Serial.print("ms T_M=");
  Serial.print(t_canal_m);
  Serial.print("ms T_L=");
  Serial.print(t_canal_l);
  Serial.println("ms");
  Serial.print("R_S=");
  Serial.print(t_retorno_s);
  Serial.print("ms R_M=");
  Serial.print(t_retorno_m);
  Serial.print("ms R_L=");
  Serial.print(t_retorno_l);
  Serial.println("ms");
}

void loop() {
  if (Serial.available()) {
    handleCommand();
  }

  if (live_mode && millis() - last_live > LIVE_INTERVAL) {
    last_live = millis();
    readLive();
  }

  if (auto_mode) {
    measureAndSort();
    delay(3000);
  }
}

// ═════════════════════════════════════════════════════════
//  Actuación del servo 360°
//  attach → velocidad → esperar tiempo_ms → STOP → frenar → detach
// ═════════════════════════════════════════════════════════

void actuarServo(int velocidad, unsigned long tiempo_ms) {
  servo.attach(SERVO_PIN);
  servo.write(velocidad);
  delay(tiempo_ms);
  servo.write(servo_stop);  // frenar antes de detach
  delay(T_BRAKE);           // dar tiempo al servo para responder al STOP
  servo.detach();           // matar señal PWM
}

// ═════════════════════════════════════════════════════════
//  Command handler
// ═════════════════════════════════════════════════════════

void handleCommand() {
  String input = Serial.readStringUntil('\n');
  input.trim();
  if (input.length() == 0) return;

  if (input == "SAVE") {
    saveConfig();
    return;
  }

  // ── Comandos de dos o más caracteres (TS, TM, TL, RS, RM, RL, TC) ───────
  // Se procesan primero para evitar conflictos de prefijo con comandos de un
  // solo caracter como 'T'.
  // ──────────────────────────────────────────────────────────────────────────
  if (input.length() >= 2) {
    String prefix = input.substring(0, 2);

    if (prefix == "TS") {
      unsigned long t = input.substring(2).toInt();
      if (t > 0 && t <= 5000) {
        t_canal_s = t;
        Serial.print("OK T_S=");
        Serial.print(t_canal_s);
        Serial.println("ms");
      } else {
        Serial.println("ERR T_RANGE (1-5000ms)");
      }
      return;
    }

    else if (prefix == "TM") {
      unsigned long t = input.substring(2).toInt();
      if (t > 0 && t <= 5000) {
        t_canal_m = t;
        Serial.print("OK T_M=");
        Serial.print(t_canal_m);
        Serial.println("ms");
      } else {
        Serial.println("ERR T_RANGE (1-5000ms)");
      }
      return;
    }

    else if (prefix == "TL") {
      unsigned long t = input.substring(2).toInt();
      if (t > 0 && t <= 5000) {
        t_canal_l = t;
        Serial.print("OK T_L=");
        Serial.print(t_canal_l);
        Serial.println("ms");
      } else {
        Serial.println("ERR T_RANGE (1-5000ms)");
      }
      return;
    }

    else if (prefix == "RS") {
      unsigned long t = input.substring(2).toInt();
      if (t > 0 && t <= 5000) {
        t_retorno_s = t;
        Serial.print("OK R_S=");
        Serial.print(t_retorno_s);
        Serial.println("ms");
      } else {
        Serial.println("ERR T_RANGE (1-5000ms)");
      }
      return;
    }

    else if (prefix == "RM") {
      unsigned long t = input.substring(2).toInt();
      if (t > 0 && t <= 5000) {
        t_retorno_m = t;
        Serial.print("OK R_M=");
        Serial.print(t_retorno_m);
        Serial.println("ms");
      } else {
        Serial.println("ERR T_RANGE (1-5000ms)");
      }
      return;
    }

    else if (prefix == "RL") {
      unsigned long t = input.substring(2).toInt();
      if (t > 0 && t <= 5000) {
        t_retorno_l = t;
        Serial.print("OK R_L=");
        Serial.print(t_retorno_l);
        Serial.println("ms");
      } else {
        Serial.println("ERR T_RANGE (1-5000ms)");
      }
      return;
    }

    // ── TC<CW|CCW> — Test continuo para calibrar el neutro ────────────────
    // Gira en la dirección indicada hasta que se reciba S.
    // Útil para verificar dirección antes de calibrar tiempos.
    // ──────────────────────────────────────────────────────────────────────
    else if (prefix == "TC") {
      String dir = input.substring(2);
      dir.toUpperCase();
      if (dir == "CW") {
        servo.attach(SERVO_PIN);
        servo.write(servo_cw);
        Serial.println("OK TEST_CW (send S to stop)");
      } else if (dir == "CCW") {
        servo.attach(SERVO_PIN);
        servo.write(servo_ccw);
        Serial.println("OK TEST_CCW (send S to stop)");
      } else {
        Serial.println("ERR USE: TCCW or TCCCW");
      }
      return;
    }

    // ── TW<ms> — Ajustar tiempo de espera entre ida y retorno ──────────
    else if (prefix == "TW") {
      unsigned long t = input.substring(2).toInt();
      if (t >= 100 && t <= 5000) {
        T_ESPERA_HUEVO = t;
        Serial.print("OK TW=");
        Serial.print(T_ESPERA_HUEVO);
        Serial.println("ms");
      } else {
        Serial.println("ERR TW_RANGE (100-5000ms)");
      }
      return;
    }

    // ── GP<dir><ms> — Go Pulse: giro temporizado ──────────────────────
    // Mueve el servo en la dirección indicada por el tiempo dado.
    // Ejemplo: GPCW500 → CW por 500ms, GPCCW300 → CCW por 300ms
    // ──────────────────────────────────────────────────────────────────
    else if (prefix == "GP") {
      String rest = input.substring(2);
      rest.toUpperCase();
      int dir_vel;
      String dir_name;
      unsigned long pulse_ms;
      if (rest.startsWith("CCW")) {
        dir_vel = servo_ccw;
        dir_name = "CCW";
        pulse_ms = rest.substring(3).toInt();
      } else if (rest.startsWith("CW")) {
        dir_vel = servo_cw;
        dir_name = "CW";
        pulse_ms = rest.substring(2).toInt();
      } else {
        Serial.println("ERR USE: GPCW<ms> or GPCCW<ms>");
        return;
      }
      if (pulse_ms > 0 && pulse_ms <= 10000) {
        Serial.print("OK PULSE ");
        Serial.print(dir_name);
        Serial.print(" ");
        Serial.print(pulse_ms);
        Serial.println("ms");
        actuarServo(dir_vel, pulse_ms);
        Serial.println("PULSE_DONE");
      } else {
        Serial.println("ERR PULSE_RANGE (1-10000ms)");
      }
      return;
    }

    // ── VCW<val> — Ajustar velocidad CW ──────────────────────────────
    // Valores válidos: 0-89. Más bajo = más rápido. Más cerca de 90 = más lento.
    // Ejemplo: VCW85 → giro CW suave, VCW50 → giro CW rápido
    // ──────────────────────────────────────────────────────────────────
    else if (input.startsWith("VCW")) {
      int v = input.substring(3).toInt();
      // toInt returns 0 on failure, so also accept 0 explicitly
      if (v >= 0 && v < servo_stop && (v > 0 || input.substring(3) == "0")) {
        servo_cw = v;
        Serial.print("OK VCW=");
        Serial.println(servo_cw);
      } else {
        Serial.print("ERR VCW_RANGE (0-");
        Serial.print(servo_stop - 1);
        Serial.println(")");
      }
      return;
    }

    // ── VCCW<val> — Ajustar velocidad CCW ─────────────────────────────
    // Valores válidos: 91-180. Más alto = más rápido. Más cerca de 90 = más lento.
    // Ejemplo: VCCW95 → giro CCW suave, VCCW150 → giro CCW rápido
    // ──────────────────────────────────────────────────────────────────
    else if (input.startsWith("VCCW")) {
      int v = input.substring(4).toInt();
      if (v > servo_stop && v <= 180) {
        servo_ccw = v;
        Serial.print("OK VCCW=");
        Serial.println(servo_ccw);
      } else {
        Serial.print("ERR VCCW_RANGE (");
        Serial.print(servo_stop + 1);
        Serial.println("-180)");
      }
      return;
    }
  }

  // ── Comandos de un solo caracter ─────────────────────────────────────────
  char cmd = input.charAt(0);

  switch (cmd) {

    case 'T':
      if (!hx711_ok || !balanza.is_ready()) {
        Serial.println("ERR HX711_NOT_READY");
      } else {
        balanza.tare();
        Serial.println("OK TARE");
      }
      break;

    case 'M': {
      if (input.length() > 1) {
        float mock_weight = input.substring(1).toFloat();
        measureAndSort(mock_weight);
      } else {
        measureAndSort(-1.0);
      }
      break;
    }

    case 'A':
      auto_mode = !auto_mode;
      if (auto_mode) live_mode = false;
      Serial.print("OK AUTO=");
      Serial.println(auto_mode ? "ON" : "OFF");
      break;

    case 'L':
      live_mode = !live_mode;
      if (live_mode) auto_mode = false;
      Serial.print("OK LIVE=");
      Serial.println(live_mode ? "ON" : "OFF");
      break;

    case 'K': {
      float f = input.substring(1).toFloat();
      if (f != 0) {
        factor_calibracion = f;
        balanza.set_scale(factor_calibracion);
        Serial.print("OK CAL=");
        Serial.println(factor_calibracion, 1);
      } else {
        Serial.println("ERR BAD_CAL");
      }
      break;
    }

    // ── N<val> — Ajustar punto neutro del servo ──────────────────────────
    // Usá este comando para calibrar el neutro real de tu servo.
    // Enviá N88, N89, N90, N91, N92... hasta que el servo quede inmóvil.
    // ──────────────────────────────────────────────────────────────────────
    case 'N': {
      int n = input.substring(1).toInt();
      if (n >= 80 && n <= 140) {
        servo_stop = n;
        // Aplicar inmediatamente para verificar visualmente
        servo.attach(SERVO_PIN);
        servo.write(servo_stop);
        Serial.print("OK NEUTRAL=");
        Serial.println(servo_stop);
        // No hacer detach aquí — dejar girando (o quieto) para ver el efecto.
        // Enviá S para detener cuando hayas encontrado el neutro correcto.
      } else {
        Serial.println("ERR NEUTRAL_RANGE (80-140)");
      }
      break;
    }

    case 'S':
      auto_mode = false;
      live_mode = false;
      servo.write(servo_stop);  // frenar primero si estaba girando
      delay(T_BRAKE);
      servo.detach();
      Serial.println("OK STOP");
      break;

    case '?':
      Serial.print("STATUS AUTO=");
      Serial.print(auto_mode ? "ON" : "OFF");
      Serial.print(" LIVE=");
      Serial.print(live_mode ? "ON" : "OFF");
      Serial.print(" CAL=");
      Serial.print(factor_calibracion, 1);
      Serial.print(" NEUTRAL=");
      Serial.print(servo_stop);
      Serial.print(" VCW=");
      Serial.print(servo_cw);
      Serial.print(" VCCW=");
      Serial.print(servo_ccw);
      Serial.print(" T_S=");
      Serial.print(t_canal_s);
      Serial.print("ms T_M=");
      Serial.print(t_canal_m);
      Serial.print("ms T_L=");
      Serial.print(t_canal_l);
      Serial.print("ms R_S=");
      Serial.print(t_retorno_s);
      Serial.print("ms R_M=");
      Serial.print(t_retorno_m);
      Serial.print("ms R_L=");
      Serial.print(t_retorno_l);
      Serial.print("ms TW=");
      Serial.print(T_ESPERA_HUEVO);
      Serial.println("ms");
      break;

    default:
      Serial.println("ERR UNKNOWN");
      break;
  }
}

// ═════════════════════════════════════════════════════════
//  Medir peso, clasificar, mover servo por tiempo
// ═════════════════════════════════════════════════════════

void measureAndSort(float mock_weight) {
  float peso;
  if (mock_weight >= 0.0) {
    peso = mock_weight;
  } else {
    if (!hx711_ok || !balanza.is_ready()) {
      Serial.println("ERR HX711_NOT_READY — use M<peso> for mock");
      return;
    }
    peso = balanza.get_units(10);
    if (peso < 0) peso = 0;
  }

  int            velocidad;
  unsigned long  tiempo_ms;
  int            velocidad_retorno;
  unsigned long  tiempo_retorno_ms;
  String         cat;

  if (peso < 53.0) {
    velocidad          = servo_cw;
    tiempo_ms          = t_canal_s;
    velocidad_retorno  = servo_ccw;
    tiempo_retorno_ms  = t_retorno_s;
    cat                = "S";
  } else if (peso <= 62.0) {
    velocidad          = servo_cw;
    tiempo_ms          = t_canal_m;
    velocidad_retorno  = servo_ccw;
    tiempo_retorno_ms  = t_retorno_m;
    cat                = "M";
  } else {
    velocidad          = servo_ccw;   // Dirección opuesta para canal L
    tiempo_ms          = t_canal_l;
    velocidad_retorno  = servo_cw;
    tiempo_retorno_ms  = t_retorno_l;
    cat                = "L";
  }

  // Reporte: W<peso>:<cat>:<tiempo_ms>ms
  Serial.print("W");
  Serial.print(peso, 1);
  Serial.print(":");
  Serial.print(cat);
  Serial.print(":");
  Serial.print(tiempo_ms);
  Serial.println("ms");

  // Fase 2: Girar a canal
  actuarServo(velocidad, tiempo_ms);

  Serial.print("DONE:");
  Serial.println(cat);

  // Fase 3: Esperar a que el huevo caiga y retornar
  delay(T_ESPERA_HUEVO);
  actuarServo(velocidad_retorno, tiempo_retorno_ms);
}

// ═════════════════════════════════════════════════════════
//  Live weight reading (sin movimiento de servo)
// ═════════════════════════════════════════════════════════

void readLive() {
  if (!balanza.is_ready()) return;
  float peso = balanza.get_units(3);
  if (peso < 0) peso = 0;
  Serial.print("R");
  Serial.println(peso, 1);
}