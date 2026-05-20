from cicd_optimizer.pricing import Pricing


def test_default_rates_present():
    p = Pricing()
    assert p.rate_for("ubuntu-latest") == 0.008
    assert p.rate_for("ubuntu-latest-16-core") == 0.064
    assert p.rate_for("macos-latest") == 0.08
    assert p.rate_for("windows-latest") == 0.016


def test_self_hosted_default_zero():
    p = Pricing()
    assert p.rate_for("self-hosted") == 0.0
    assert p.rate_for(["self-hosted", "linux", "x64"]) == 0.0


def test_overrides():
    p = Pricing.from_overrides({"ubuntu-latest": 0.02})
    assert p.rate_for("ubuntu-latest") == 0.02
    # untouched rates remain
    assert p.rate_for("macos-latest") == 0.08


def test_unknown_label_falls_back():
    p = Pricing()
    assert p.rate_for("mystery-runner") == 0.008
    assert p.rate_for("macos-13-arm-monster") == 0.08
