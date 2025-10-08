#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <ESP8266HTTPClient.h>
#include <Wire.h>
#include <Adafruit_MLX90614.h>
// -------------------- Pins & Devices --------------------
#define SDA_PIN D2   // GPIO4
#define SCL_PIN D1   // GPIO5
// WiFi / Supabase
const char* WIFI_SSID = "Student";
const char* WIFI_PW   = "student@ku321.";
const char* SUPA_URL  = "https://zpqiiynzkrfswhsffkoa.supabase.co/rest/v1/sensor_readings";
const char* ANON_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpwcWlpeW56a3Jmc3doc2Zma29hIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkyMjg5NTcsImV4cCI6MjA3NDgwNDk1N30.YQX33Kj4H1tkpsd16XMRXsLGIJQBBQZtPFQ3mHUrLMg";
const char* DEVICE_ID = "esp8266-01";
// MLX90614 (IR)
Adafruit_MLX90614 mlx;
// MAX30205 (contact temp) - direct I2C
const uint8_t MAX_ADDR      = 0x48;   // from your scan
const uint8_t MAX_REG_TEMP  = 0x00;
const uint8_t MAX_REG_CONF  = 0x01;
// -------------------- Helpers: MAX30205 --------------------
bool max_write_conf(uint8_t val){
  Wire.beginTransmission(MAX_ADDR);
  Wire.write(MAX_REG_CONF);
  Wire.write(val);
  return Wire.endTransmission(true) == 0;
}
bool max_read_temp(float &tC){
  Wire.beginTransmission(MAX_ADDR);
  Wire.write(MAX_REG_TEMP);
  if (Wire.endTransmission(true) != 0) return false;
  if (Wire.requestFrom((int)MAX_ADDR, 2) != 2) return false;
  uint8_t msb = Wire.read();
  uint8_t lsb = Wire.read();
  int16_t raw = (int16_t)((msb << 8) | lsb);   // signed
  tC = raw * (1.0f / 256.0f);
  return true;
}
// -------------------- I2C Bus Recovery & Robust MLX Read --------------------
// Pulse SCL to release a stuck slave holding SDA low, then re-init Wire.
void i2cBusRecover() {
  pinMode(SCL_PIN, OUTPUT);
  pinMode(SDA_PIN, INPUT_PULLUP);
  // 9 clock pulses recommended by NXP to free the bus
  for (int i = 0; i < 9; i++) {
    digitalWrite(SCL_PIN, LOW);  delayMicroseconds(5);
    digitalWrite(SCL_PIN, HIGH); delayMicroseconds(5);
  }
  // Generate a STOP
  pinMode(SDA_PIN, OUTPUT);
  digitalWrite(SDA_PIN, LOW);    delayMicroseconds(5);
  digitalWrite(SCL_PIN, HIGH);   delayMicroseconds(5);
  digitalWrite(SDA_PIN, HIGH);   delayMicroseconds(5);
  // Restore Wire and slower clock for reliability
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(50000); // 50 kHz
}
// Read MLX with retries; filter bogus 1037.55 values and out-of-range
bool readMLXObjectC(float &tC) {
  for (int attempt = 0; attempt < 3; attempt++) {
    float v = mlx.readObjectTempC();
    if (!isnan(v) && v > -40 && v < 100 && fabsf(v - 1037.55f) > 1.0f) {
      tC = v;
      return true;
    }
    delay(5); // brief yield
  }
  // Recover the bus and try once more
  i2cBusRecover();
  delay(5);
  mlx.begin();  // re-init MLX on recovered bus
  delay(5);
  float v = mlx.readObjectTempC();
  if (!isnan(v) && v > -40 && v < 100 && fabsf(v - 1037.55f) > 1.0f) {
    tC = v;
    return true;
  }
  return false;
}
// -------------------- WiFi & Supabase --------------------
void connectWiFi(){
  Serial.printf("Connecting to %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PW);
  for (int i=0; i<60 && WiFi.status()!=WL_CONNECTED; i++){
    delay(250);
    Serial.print(".");
    yield();
  }
  Serial.println();
  if (WiFi.status()==WL_CONNECTED) {
    Serial.print("WiFi IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WiFi FAILED");
  }
}
bool sendToSupabase(float core_c, float peripheral_c){
  if (WiFi.status()!=WL_CONNECTED) return false;
  WiFiClientSecure client;
  client.setInsecure(); // using HTTPS without CA for simplicity
  HTTPClient http;
  if (!http.begin(client, SUPA_URL)) {
    Serial.println("http.begin failed");
    return false;
  }
  http.addHeader("apikey", ANON_KEY);
  http.addHeader("Authorization", String("Bearer ") + ANON_KEY);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Prefer", "return=representation");
  http.addHeader("Connection", "close");
  String body = String("{\"device_id\":\"") + DEVICE_ID + "\"," +
                "\"core_c\":" + String(core_c,2) + "," +
                "\"peripheral_c\":" + String(peripheral_c,2) + "}";
  int code = http.POST(body);
  Serial.printf("POST -> %d\n", code);
  if (code > 0) Serial.println(http.getString());
  http.end();
  return code>=200 && code<300;
}
// -------------------- Timing --------------------
const unsigned long READ_INTERVAL_MS = 10000;  // 10 seconds
unsigned long last_read_ms = 0;
// -------------------- Setup & Loop --------------------
void setup(){
  Serial.begin(115200);
  delay(150);
  Serial.println("\n=== MLX90614 + MAX30205 on one I2C bus (D2/D1) ===");
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(50000); // slower clock for reliability
  // init MLX
  if (!mlx.begin()) Serial.println("❌ MLX init failed (expect 0x5A)");
  else              Serial.println("✅ MLX OK (0x5A)");
  // init MAX: continuous conversion (0x00)
  if (!max_write_conf(0x00)) Serial.println("⚠️ MAX config write failed (still trying reads)");
  else                       Serial.println("✅ MAX config OK (0x48)");
  connectWiFi();
  last_read_ms = millis();
}
void loop(){
  // keep the watchdog happy during idle
  delay(5);
  unsigned long now = millis();
  if ((unsigned long)(now - last_read_ms) < READ_INTERVAL_MS) return;
  last_read_ms = now;
  // ----- Read sensors -----
  // MLX (object temp)
  float core = NAN;
  bool core_ok = readMLXObjectC(core);
  // MAX30205 (contact temp)
  float peri = NAN;
  bool peri_ok = max_read_temp(peri) && peri > -40 && peri < 125;
  if (!core_ok) Serial.println("MLX read bad/out-of-range");
  if (!peri_ok) Serial.println("MAX read bad/out-of-range");
  Serial.printf("Core: %s | Peripheral: %s\n",
    core_ok ? String(core,2).c_str() : "NaN",
    peri_ok ? String(peri,2).c_str() : "NaN");
  // ----- Send if both valid -----
  if (core_ok && peri_ok) {
    if (sendToSupabase(core, peri)) Serial.println("Sent ✓");
    else Serial.println("Send failed");
  } else {
    Serial.println("Skip send (bad read)");
  }
}
