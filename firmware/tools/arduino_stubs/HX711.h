#pragma once
#include "Arduino.h"
struct HX711 { void begin(uint8_t,uint8_t); bool is_ready(); long read(); long read_average(uint8_t=10); };
