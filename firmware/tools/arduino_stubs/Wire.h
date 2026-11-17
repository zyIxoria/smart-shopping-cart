#pragma once
#include "Arduino.h"
struct TwoWire { void begin(int,int); void setClock(uint32_t); void beginTransmission(uint8_t); uint8_t endTransmission(); }; extern TwoWire Wire;
