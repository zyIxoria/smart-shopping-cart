#pragma once
#include "Adafruit_GFX.h"
#include "Wire.h"
#define SSD1306_WHITE 1
#define SSD1306_SWITCHCAPVCC 2
struct Adafruit_SSD1306 : Adafruit_GFX { Adafruit_SSD1306(uint8_t,uint8_t,TwoWire*,int8_t); bool begin(uint8_t,uint8_t); void clearDisplay(); void display(); };
