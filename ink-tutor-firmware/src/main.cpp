#include <Arduino.h>
#include <Wire.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLE2902.h>
#include <SparkFun_BMI270_Arduino_Library.h>

const int FSR_PIN = 34;

#define SERVICE_UUID        "12345678-1234-1234-1234-123456789abc"
#define CHARACTERISTIC_UUID "abcd1234-ab12-ab12-ab12-abcdef123456"

BLECharacteristic* pCharacteristic = nullptr;
bool deviceConnected = false;
BMI270 imu;

class ServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer* s)    { deviceConnected = true; }
    void onDisconnect(BLEServer* s) { deviceConnected = false; s->startAdvertising(); }
};

void setup() {
    Serial.begin(115200);
    delay(500);

    Wire.begin(21, 22);
    if (imu.beginI2C(0x68) != BMI2_OK)
        Serial.println("BMI270 not found!");
    else
        Serial.println("BMI270 ready");

    BLEDevice::init("InkTutor-Pen");
    BLEServer* pServer = BLEDevice::createServer();
    pServer->setCallbacks(new ServerCallbacks());

    BLEService* pService = pServer->createService(SERVICE_UUID);
    pCharacteristic = pService->createCharacteristic(
        CHARACTERISTIC_UUID, BLECharacteristic::PROPERTY_NOTIFY);
    pCharacteristic->addDescriptor(new BLE2902());
    pService->start();

    BLEDevice::getAdvertising()->addServiceUUID(SERVICE_UUID);
    BLEDevice::startAdvertising();
    Serial.println("BLE advertising as InkTutor-Pen");
}

void loop() {
    imu.getSensorData();
    int fsr = analogRead(FSR_PIN);

    char buf[128];
    snprintf(buf, sizeof(buf),
        "{\"fsr\":%d,\"ax\":%.2f,\"ay\":%.2f,\"az\":%.2f,\"gx\":%.2f,\"gy\":%.2f,\"gz\":%.2f}",
        fsr,
        imu.data.accelX, imu.data.accelY, imu.data.accelZ,
        imu.data.gyroX,  imu.data.gyroY,  imu.data.gyroZ);

    Serial.println(buf);
    if (deviceConnected) {
        pCharacteristic->setValue(buf);
        pCharacteristic->notify();
    }

    delay(50);  // 20 Hz
}
