#pragma once
#include "Arduino.h"
struct IPAddress { String toString() const; };
#define WL_CONNECTED 3
#define WIFI_STA 1
struct WiFiClient {};
struct WiFiClass { int status(); void disconnect(); void begin(const char*,const char*); void mode(int); void setAutoReconnect(bool); IPAddress localIP(); };
extern WiFiClass WiFi;
void configTime(long,int,const char*,const char* =0,const char* =0);
