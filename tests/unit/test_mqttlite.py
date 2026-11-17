import time

import pytest

from shared.mqttlite import MqttClient
from tests.conftest import wait_until
from tools.dev_broker import DevBroker, topic_matches


@pytest.fixture()
def broker():
    b = DevBroker("127.0.0.1", 0).start_in_thread()
    yield b
    b.stop()


def test_topic_matching():
    assert topic_matches("smartcart/+/scan", "smartcart/CART_001/scan")
    assert not topic_matches("smartcart/+/scan", "smartcart/CART_001/ack")
    assert topic_matches("smartcart/#", "smartcart/a/b") and not topic_matches("a/+", "a/b/c")


def test_pubsub_and_wildcard(broker):
    got = []
    sub = MqttClient("sub", "127.0.0.1", broker.port)
    sub.on_message = lambda t, p: got.append((t, p))
    sub.subscribe("smartcart/+/scan")
    sub.start()
    pub = MqttClient("pub", "127.0.0.1", broker.port)
    pub.start()
    assert sub.wait_connected() and pub.wait_connected()
    time.sleep(0.2)
    assert pub.publish("smartcart/CART_001/scan", b'{"x":1}')
    pub.publish("smartcart/CART_001/ack", b"ignored")
    wait_until(lambda: got)
    assert got == [("smartcart/CART_001/scan", b'{"x":1}')]
    sub.stop(); pub.stop()


def test_large_payload(broker):
    got = []
    sub = MqttClient("sub", "127.0.0.1", broker.port)
    sub.on_message = lambda t, p: got.append(p)
    sub.subscribe("big")
    sub.start(); assert sub.wait_connected()
    pub = MqttClient("pub", "127.0.0.1", broker.port); pub.start(); pub.wait_connected()
    time.sleep(0.2)
    blob = b"x" * 70000          # remaining length cần 3 byte
    pub.publish("big", blob)
    wait_until(lambda: got)
    assert got[0] == blob
    sub.stop(); pub.stop()


def test_publish_when_disconnected_returns_false():
    c = MqttClient("nobody", "127.0.0.1", 1)   # cổng đóng
    assert c.publish("a/b", b"x") is False


def test_auto_reconnect_and_resubscribe(broker):
    got = []
    sub = MqttClient("sub", "127.0.0.1", broker.port, reconnect_min=0.1)
    sub.on_message = lambda t, p: got.append(p)
    sub.subscribe("t/1")
    sub.start(); assert sub.wait_connected()
    # ngắt kết nối thô từ phía broker
    for s in list(broker.sessions):
        broker._loop.call_soon_threadsafe(s.writer.close)
    wait_until(lambda: not sub.connected, timeout=3)
    wait_until(lambda: sub.connected, timeout=5, msg="reconnect")
    time.sleep(0.3)
    pub = MqttClient("pub", "127.0.0.1", broker.port); pub.start(); pub.wait_connected()
    time.sleep(0.2)
    pub.publish("t/1", b"after")
    wait_until(lambda: got == [b"after"], msg="subscription được khôi phục")
    sub.stop(); pub.stop()


def test_stop_unclean_then_start_again(broker):
    c = MqttClient("c", "127.0.0.1", broker.port, reconnect_min=0.1)
    c.start(); assert c.wait_connected()
    c.stop(clean=False)
    assert not c.connected
    c.start(); assert c.wait_connected()
    c.stop()
