/*
  DUSTWAVE ESP32 sweep + burst controller (Arduino-ESP32 core 3.x API).
  UNTESTED on hardware - bench-test with a small piezo disc first.

  WIRING (required):
    GPIO 25  -> gate/input of a rated driver stage (e.g. logic-level MOSFET + resistor, or a piezo driver IC).
                NEVER connect a transducer directly to the GPIO pin.
    GPIO 34  <- vibration sensor analog output (keep within 0-3.3 V)
    GPIO 27  <- ARM switch to GND. Output is only enabled while this pin is held LOW.

  SERIAL COMMANDS (115200 baud):
    S               run a frequency sweep, prints "freq_hz,response" CSV lines
    B <hz> <duty>   run one burst, e.g.  B 41300 0.12   (duty clamped to 0.30, burst <= 200 ms)
    X               stop output immediately
*/
const int DRIVE_PIN = 25, SENSOR_PIN = 34, ARM_PIN = 27;
const int PWM_BITS = 8;
const float DUTY_MAX = 0.30;
const uint32_t FREQ_MIN = 20000, FREQ_MAX = 60000, BURST_MS_MAX = 200;
const uint32_t SWEEP_START = 30000, SWEEP_END = 55000, SWEEP_STEP = 250;

bool armed() { return digitalRead(ARM_PIN) == LOW; }

void driveOff() { ledcWrite(DRIVE_PIN, 0); }

void driveOn(uint32_t hz, float duty) {
  hz = constrain(hz, FREQ_MIN, FREQ_MAX);
  duty = constrain(duty, 0.0f, DUTY_MAX);
  ledcChangeFrequency(DRIVE_PIN, hz, PWM_BITS);
  ledcWrite(DRIVE_PIN, (uint32_t)(duty * ((1 << PWM_BITS) - 1)));
}

int readAmplitude(int samples = 200) {         // peak-to-peak of the sensor signal
  int lo = 4095, hi = 0;
  for (int i = 0; i < samples; i++) {
    int v = analogRead(SENSOR_PIN);
    lo = min(lo, v); hi = max(hi, v);
    delayMicroseconds(50);
  }
  return hi - lo;
}

void sweep() {
  if (!armed()) { Serial.println("ERROR: ARM switch is off"); return; }
  Serial.println("freq_hz,response");
  for (uint32_t f = SWEEP_START; f <= SWEEP_END; f += SWEEP_STEP) {
    if (!armed()) { driveOff(); Serial.println("ABORT: ARM released"); return; }
    driveOn(f, 0.10);
    delay(20);                                  // let the sensor settle
    int amp = readAmplitude();
    driveOff();
    Serial.print(f); Serial.print(","); Serial.println(amp);
    delay(30);                                  // rest between steps
  }
  Serial.println("DONE");
}

void burst(uint32_t hz, float duty) {
  if (!armed()) { Serial.println("ERROR: ARM switch is off"); return; }
  driveOn(hz, duty);
  uint32_t t0 = millis();
  while (millis() - t0 < BURST_MS_MAX && armed()) delay(1);
  driveOff();
  Serial.println("BURST_DONE");
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  pinMode(ARM_PIN, INPUT_PULLUP);
  ledcAttach(DRIVE_PIN, 40000, PWM_BITS);
  driveOff();
  Serial.println("DUSTWAVE ready. Commands: S | B <hz> <duty> | X");
}

void loop() {
  if (!armed()) driveOff();
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'S') sweep();
    else if (c == 'B') { uint32_t hz = Serial.parseInt(); float d = Serial.parseFloat(); burst(hz, d); }
    else if (c == 'X') { driveOff(); Serial.println("STOPPED"); }
  }
}
