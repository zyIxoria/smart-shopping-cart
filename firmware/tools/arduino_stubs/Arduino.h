#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT_PULLUP 2
#define SERIAL_8N1 0x800001c
#define ADC_11db 3
uint32_t millis(); void delay(uint32_t); void pinMode(int,int); void digitalWrite(int,int); int digitalRead(int);
uint32_t analogReadMilliVolts(int); void analogSetPinAttenuation(int,int);
struct String { const char* c_str() const; };
struct HardwareSerial { size_t setRxBufferSize(size_t); void begin(unsigned long,uint32_t=0,int8_t=-1,int8_t=-1); int available(); int read(); void println(const char*); void print(const char*);
  void printf(const char*,...) __attribute__((format(printf,2,3))); };
extern HardwareSerial Serial, Serial2;
