from integration.simulate import make_stream, run


def test_stream_is_deterministic_and_has_expected_composition():
    a, kinds_a, d_a = make_stream(1500, seed=3)
    b, kinds_b, d_b = make_stream(1500, seed=3)
    assert a == b and kinds_a == kinds_b and d_a == d_b == 75
    assert len(a) == 1500 + 75 and len(kinds_a) == 1500


def test_simulation_is_reproducible():
    s, k, _ = make_stream(1500, seed=3)
    assert run(s, k) == run(s, k)


def test_retry_plus_idempotency_gives_near_complete_delivery_with_zero_duplicates():
    s, k, _ = make_stream(1500, seed=3)
    r = run(s, k)
    assert r["delivery_rate_of_deliverable_pct"] >= 99.5
    assert r["target_duplicate_deliveries"] == 0
    assert r["bad_messages_classified_correctly"] is True
    assert r["duplicates_suppressed"] > 0 and r["retries"] > 0


def test_retries_are_what_recovers_transient_failures():
    s, k, _ = make_stream(1500, seed=3)
    with_retry, no_retry = run(s, k), run(s, k, max_attempts=1)
    assert no_retry["delivery_rate_of_deliverable_pct"] < 90 < with_retry["delivery_rate_of_deliverable_pct"]
    assert "bad_messages_classified_correctly" not in no_retry     # check intentionally skipped without retries


def test_removing_idempotency_lets_duplicates_reach_the_target():
    s, k, _ = make_stream(1500, seed=3)
    assert run(s, k, idempotent=False)["target_duplicate_deliveries"] > 0


def test_redrive_recovers_exhausted_letters_once_target_is_healthy():
    s, k, _ = make_stream(5000, seed=1)            # large enough that at least one message exhausts its retries
    r = run(s, k, redrive=True)
    assert r["redrive"]["attempted"] >= 1 and r["redrive"]["delivered"] == r["redrive"]["attempted"]
