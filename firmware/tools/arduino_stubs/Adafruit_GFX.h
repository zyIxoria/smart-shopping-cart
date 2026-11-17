#pragma once
#include "Arduino.h"
struct Adafruit_GFX { void setTextColor(uint16_t); void setTextSize(uint8_t); void setCursor(int,int); void print(const char*); void println(const char*);
 void printf(const char*,...) __attribute__((format(printf,2,3))); };
