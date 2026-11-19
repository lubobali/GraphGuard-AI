"""MLflow refuses whoever should be refused (S5b.7), on the live server."""

import urllib.error

import pytest

from graphguard.ops import mlflow_auth as ma

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (ma.SECRETS / "mlflow-admin.env").exists(), reason="MLflow login not set up (S5b.7)"
    ),
]


def _code(method, path, body, auth):
    try:
        ma.call(method, path, body, auth)
    except urllib.error.HTTPError as e:
        return e.code
    return 200


SEARCH = "/api/2.0/mlflow/experiments/search?max_results=5"


def test_anonymous_is_refused_but_health_is_open():
    import urllib.request

    assert _code("GET", SEARCH, None, None) == 401
    with urllib.request.urlopen(f"{ma.URL}/health", timeout=5) as r:  # the container probe
        assert r.status == 200


def test_a_wrong_password_is_refused():
    assert (
        _code("GET", SEARCH, None, ("research", "wrong")) == 401
    )  # betterleaks:allow -- deliberately wrong


def test_each_login_works():
    for user in ("admin", *ma.USERS):
        assert _code("GET", SEARCH, None, ma.credentials(user)) == 200


def test_no_job_can_delete_the_real_experiment():
    exp = ma._experiment_id("graphguard", ma.credentials("admin"))
    for user in ma.USERS:
        code = _code("POST", "/api/2.0/mlflow/experiments/delete", {"experiment_id": exp},
                     ma.credentials(user))  # fmt: skip
        assert code == 403, user


def test_the_trainer_cannot_see_the_test_experiment():
    admin = ma.credentials("admin")
    exp = ma._experiment_id("graphguard-tests", admin)
    trainer = ma.credentials("trainer")
    # Search is filtered to what the caller may read; direct reads are refused.
    found = ma.call("POST", "/api/2.0/mlflow/runs/search", {"experiment_ids": [exp]}, trainer)
    assert found.get("runs", []) == []
    assert (
        _code("GET", f"/api/2.0/mlflow/experiments/get?experiment_id={exp}", None, trainer) == 403
    )
    one = {"experiment_ids": [exp], "max_results": 1}
    research_runs = ma.call("POST", "/api/2.0/mlflow/runs/search", one, ma.credentials("research"))
    rid = research_runs["runs"][0]["info"]["run_id"]
    assert _code("GET", f"/api/2.0/mlflow/runs/get?run_id={rid}", None, trainer) == 403


def test_the_trainer_can_log_into_the_real_experiment():
    exp = ma._experiment_id("graphguard", ma.credentials("admin"))
    auth = ma.credentials("trainer")
    body = {"experiment_id": exp, "run_name": "auth-probe",
            "tags": [{"key": "probe", "value": "S5b.7"}]}  # fmt: skip
    run = ma.call("POST", "/api/2.0/mlflow/runs/create", body, auth)
    rid = run["run"]["info"]["run_id"]
    ma.call("POST", "/api/2.0/mlflow/runs/update", {"run_id": rid, "status": "FINISHED"}, auth)
    # and it cannot delete what it wrote: deleting needs MANAGE, which only admin has
    assert _code("POST", "/api/2.0/mlflow/runs/delete", {"run_id": rid}, auth) == 403
    ma.call("POST", "/api/2.0/mlflow/runs/delete", {"run_id": rid}, ma.credentials("admin"))
