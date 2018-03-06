import pytest

from etcd3.client import Etcd3APIClient
from etcd3.errors import Etcd3APIError
from .envs import protocol, host, port
from .etcd_go_cli import etcdctl, NO_ETCD_SERVICE
from .mocks import fake_request


@pytest.fixture(scope='session')
def client():
    """
    init Etcd3Client, close its connection-pool when teardown
    """
    c = Etcd3APIClient(host, port, protocol)
    yield c
    c.close()


@pytest.mark.skipif(NO_ETCD_SERVICE, reason="no etcd service available")
def test_request_and_model(client):
    etcdctl('put test_key test_value')
    result = client.call_rpc('/v3alpha/kv/range', {'key': 'test_key'})
    # {"header":{"cluster_id":11588568905070377092,"member_id":128088275939295631,"revision":3,"raft_term":2},"kvs":[{"key":"dGVzdF9rZXk=","create_revision":3,"mod_revision":3,"version":1,"value":"dGVzdF92YWx1ZQ=="}],"count":1}'
    assert result.kvs[0].key == b'test_key'
    assert result.kvs[0].value == b'test_value'
    etcdctl('del test_key')


@pytest.mark.skipif(NO_ETCD_SERVICE, reason="no etcd service available")
def test_stream(client):
    r = client.call_rpc('/v3alpha/watch', {'create_request': {'key': 'test_key'}}, stream=True)
    times = 3
    header_times = 1
    for i in r:
        if not times:
            break
        etcdctl('put test_key test_value')
        if hasattr(i, 'events'):
            assert i.events[0].kv.key == b'test_key'
            assert i.events[0].kv.value == b'test_value'
            times -= 1
        else:
            header_times -= 1
            assert header_times >= 0
    r.close()


@pytest.mark.skipif(NO_ETCD_SERVICE, reason="no etcd service available")
def test_request_exception(client):
    with pytest.raises(Etcd3APIError, match=r".*'Not Found'.*"):
        client.call_rpc('/v3alpha/kv/rag', {})  # non exist path


def test_patched_stream(client, monkeypatch):
    s = b'{"result": {"header": {"raft_term": 7, "member_id": 128088275939295631, "cluster_id": 11588568905070377092, "revision": 378}, "created": true}}' \
        b'{"result": {"header": {"raft_term": 7, "member_id": 128088275939295631, "cluster_id": 11588568905070377092, "revision": 379}, "events": [{"kv": {"mod_revision": 379, "value": "dGVzdF92YWx1ZQ==", "create_revision": 379, "version": 1, "key": "dGVzdF9rZXk="}}]}}' \
        b'{"result": {"header": {"raft_term": 7, "member_id": 128088275939295631, "cluster_id": 11588568905070377092, "revision": 380}, "events": [{"kv": {"mod_revision": 380, "value": "dGVzdF92YWx1ZQ==", "create_revision": 379, "version": 2, "key": "dGVzdF9rZXk="}}]}}' \
        b'{"result": {"header": {"raft_term": 7, "member_id": 128088275939295631, "cluster_id": 11588568905070377092, "revision": 381}, "events": [{"kv": {"mod_revision": 381, "value": "dGVzdF92YWx1ZQ==", "create_revision": 379, "version": 3, "key": "dGVzdF9rZXk="}}]}}'
    post = fake_request(200, s, client.response_class)
    monkeypatch.setattr(client.session, 'post', post)
    r = client.call_rpc('/v3alpha/watch', {'create_request': {'key': 'test_key'}}, stream=True)
    times = 3
    header_times = 1
    for i in r:
        if not times:
            break
        if hasattr(i, 'events'):
            assert i.events[0].kv.key == b'test_key'
            assert i.events[0].kv.value == b'test_value'
            times -= 1
        else:
            header_times -= 1
            assert header_times >= 0


def test_patched_request_and_model(client, monkeypatch):
    s = b'{"header":{"cluster_id":11588568905070377092,"member_id":128088275939295631,"revision":3,"raft_term":2},' \
        b'"kvs":[{"key":"dGVzdF9rZXk=","create_revision":3,"mod_revision":3,"version":1,"value":"dGVzdF92YWx1ZQ=="}],' \
        b'"count":1}'
    post = fake_request(200, s, client.response_class)
    monkeypatch.setattr(client.session, 'post', post)
    result = client.call_rpc('/v3alpha/kv/range', {'key': 'test_key'})
    assert post.call_args[1]['json']['key'] == 'dGVzdF9rZXk='
    assert result.kvs[0].key == b'test_key'
    assert result.kvs[0].value == b'test_value'


def test_patched_request_exception(client, monkeypatch):
    post = fake_request(404, 'Not Found', client.response_class)
    monkeypatch.setattr(client.session, 'post', post)
    with pytest.raises(Etcd3APIError, match=r".*'Not Found'.*"):
        client.call_rpc('/v3alpha/kv/rag', {})  # non exist path