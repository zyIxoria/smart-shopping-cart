// Bản thay thế tối thiểu của Unity CHỈ để chạy test trên máy không có PlatformIO (tools/run_native_tests.sh).
// Khi chạy `pio test -e native` thì PlatformIO dùng Unity thật, file này không được dùng.
#pragma once
#include <math.h>
#include <stdio.h>
#include <string.h>

static int unity_run = 0, unity_fail = 0, unity_cur_failed = 0;
void setUp(void);
void tearDown(void);

#define UNITY_BEGIN() (unity_run = unity_fail = 0, 0)
#define UNITY_END() (printf("\n%d tests, %d failures\n", unity_run, unity_fail), unity_fail ? 1 : 0)
#define RUN_TEST(fn) do { unity_run++; unity_cur_failed = 0; setUp(); fn(); tearDown(); \
  if (unity_cur_failed) { unity_fail++; } printf("%s %s\n", unity_cur_failed ? "FAIL" : "PASS", #fn); } while (0)
#define UNITY_FAIL_(msg) do { printf("  %s:%d: %s\n", __FILE__, __LINE__, msg); unity_cur_failed = 1; return; } while (0)

#define TEST_ASSERT_TRUE(c) do { if (!(c)) UNITY_FAIL_("expected TRUE: " #c); } while (0)
#define TEST_ASSERT_FALSE(c) do { if (c) UNITY_FAIL_("expected FALSE: " #c); } while (0)
#define TEST_ASSERT_EQUAL_INT(a, b) do { long long _a = (a), _b = (b); if (_a != _b) { printf("  expected %lld got %lld\n", _a, _b); UNITY_FAIL_("not equal"); } } while (0)
#define TEST_ASSERT_EQUAL(a, b) TEST_ASSERT_EQUAL_INT(a, b)
#define TEST_ASSERT_EQUAL_UINT32(a, b) TEST_ASSERT_EQUAL_INT(a, b)
#define TEST_ASSERT_EQUAL_STRING(a, b) do { const char* _a = (a); const char* _b = (b); if (strcmp(_a, _b) != 0) { printf("  expected \"%s\" got \"%s\"\n", _a, _b); UNITY_FAIL_("strings differ"); } } while (0)
#define TEST_ASSERT_FLOAT_WITHIN(d, a, b) do { double _d = (d), _a = (a), _b = (b); if (fabs(_a - _b) > _d) { printf("  expected %f +/- %f got %f\n", _a, _d, _b); UNITY_FAIL_("float out of range"); } } while (0)
