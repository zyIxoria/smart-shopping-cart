#pragma once
#include "Arduino.h"
struct Preferences { bool begin(const char*,bool=false); float getFloat(const char*,float); size_t putFloat(const char*,float); bool isKey(const char*); };
