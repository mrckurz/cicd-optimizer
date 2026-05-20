from cicd_optimizer.pricing import Pricing


def test_default_rates_present():
    """Verified against https://docs.github.com/en/billing/reference/actions-runner-pricing"""
    p = Pricing()
    assert p.rate_for("ubuntu-latest") == 0.006
    assert p.rate_for("ubuntu-latest-16-core") == 0.042
    assert p.rate_for("macos-latest") == 0.062
    assert p.rate_for("windows-latest") == 0.010


def test_self_hosted_default_zero():
    p = Pricing()
    assert p.rate_for("self-hosted") == 0.0
    assert p.rate_for(["self-hosted", "linux", "x64"]) == 0.0


def test_overrides():
    p = Pricing.from_overrides({"ubuntu-latest": 0.02})
    assert p.rate_for("ubuntu-latest") == 0.02
    # untouched rates remain
    assert p.rate_for("macos-latest") == 0.062


def test_unknown_label_falls_back():
    p = Pricing()
    assert p.rate_for("mystery-runner") == 0.006
    assert p.rate_for("macos-13-arm-monster") == 0.062


def test_arm64_and_gpu_present():
    p = Pricing()
    # arm64 Linux is cheaper than x64
    assert p.rate_for("ubuntu-latest-16-core-arm") == 0.026
    # GPU runner
    assert p.rate_for("ubuntu-latest-4-core-gpu") == 0.052
