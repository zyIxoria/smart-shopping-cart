#pragma once
#include "WiFi.h"
#include <functional>
struct PubSubClient { PubSubClient(WiFiClient&); bool connected(); bool connect(const char*); bool connect(const char*,const char*,const char*); bool subscribe(const char*);
 bool publish(const char*,const uint8_t*,unsigned int,bool); PubSubClient& setServer(const char*,uint16_t); bool setBufferSize(uint16_t);
 PubSubClient& setKeepAlive(uint16_t); PubSubClient& setSocketTimeout(uint16_t); PubSubClient& setCallback(void(*)(char*,uint8_t*,unsigned int)); int state(); bool loop(); };
