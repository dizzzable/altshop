from collections import Counter

import scripts.backend_audit_report as backend_audit_report


def test_backend_audit_report_shows_no_payment_compatibility_after_cleanup(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        backend_audit_report,
        "_run_mypy",
        lambda _repo_root: (0, Counter(), Counter()),
    )

    exit_code = backend_audit_report.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "## Auth compatibility surface" in output
    assert "## Auth compatibility surface\n- none detected" in output
    assert "## Payment compatibility code present" in output
    assert "## Payment compatibility code present\n- none detected" in output
    assert "heleket_provider_legacy_fallback" not in output
    assert "platega_webhook_legacy_payload" not in output
    assert "pal24_legacy_json_contract" not in output
