import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "detect_transient.py"


def run(text: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=text,
        capture_output=True,
        text=True,
        check=False,
    )


# Several of these are verbatim from the maintainer's own re-run workflow logs.
TRANSIENT_SAMPLES = (
    "curl: (28) Operation timed out after 300000 milliseconds",
    "curl: (6) Could not resolve host: github.com",
    "fatal: unable to access 'https://github.com/x': Could not resolve host: github.com",
    "mise ERROR failed to download node@20.11.0: request timed out",
    "E: Failed to fetch http://azure.archive.ubuntu.com/ubuntu/pool 503",
    "Error: The requested URL returned error: 502",
    "net/http: TLS handshake timeout",
    "The runner has received a shutdown signal.",
    "Warning: Could not get lock /var/lib/dpkg/lock-frontend",
    "fatal: the remote end hung up unexpectedly",
    "no space left on device",
    "429 Too Many Requests",
    "Error: We were unable to download the archive.",
    "gnutls_handshake() failed: The TLS connection was non-properly terminated.",
    # GitHub API rate limit (pinact, unauthenticated api.github.com) — 403, not 429
    (
        "GET https://api.github.com/repos/actions/checkout/commits/v7.0.0: 403 "
        "API rate limit exceeded for 52.157.33.162."
    ),
    "403 API rate limit of 60 still exceeded until 2026-07-11 12:55:44 +0000 UTC",
    "You have exceeded a secondary rate limit",
    # mise tool install: sigstore/TUF CDN flake
    (
        "mise ERROR Failed to install aqua:tombi-toml/tombi@1.2.0: GitHub artifact "
        "attestations verification failed: Verification failed: Sigstore error: "
        "TUF error: TUF repository load failed: transport error: GET "
        "https://tuf-repo-cdn.sigstore.dev/16.root.json failed: error sending request for url"
    ),
    # PyPI OIDC
    "##[error]Trusted publishing exchange failure:",
    # GitHub Pages backend flake
    (
        "##[error]Creating Pages deployment failed\n"
        "##[error]Error: Failed to create deployment (status: 404) with build version abc123"
    ),
    "HTTP status server error (504 Gateway Timeout) for url",
)

REAL_FAILURE_SAMPLES = (
    "FAIL: test_parses_config (tests.test_config.ConfigTest)\nAssertionError: 1 != 2",
    "./main.go:42:2: undefined: doThing",
    "error: linting failed: 3 problems",
    "Error: Process completed with exit code 1.",
    "panic: runtime error: index out of range [3] with length 3",
    "hk: check 'gitleaks' failed",
    "The job was canceled because a matrix leg failed.",
    # A flaky test whose OWN assertion text mentions a deadline — must NOT match.
    (
        "FAIL: internal/backend TestRunCommand_NonInteractiveDoesNotHangOnOrphanedChild\n"
        "        Error: Target error should be in err chain:\n"
        '        expected: "context deadline exceeded"'
    ),
    # deadcode linter listing call paths through TLS/net — must NOT match.
    (
        "internal/cmd/config.go:1:1: RoundTrip calls http.Transport.RoundTrip, "
        "which eventually calls tls.Dialer.DialContext"
    ),
    (
        "Can't find 'action.yml', 'action.yaml' or 'Dockerfile' under "
        "'/home/runner/work/x/x/release-pypi'. Did you forget to run actions/checkout"
    ),
    "goreleaser check: configuration is valid, but uses deprecated properties",
)


class DetectTransientTest(unittest.TestCase):
    def test_flags_transient_samples(self) -> None:
        for sample in TRANSIENT_SAMPLES:
            with self.subTest(sample=sample):
                proc = run(sample)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertTrue(proc.stdout.strip())

    def test_ignores_real_failures(self) -> None:
        for sample in REAL_FAILURE_SAMPLES:
            with self.subTest(sample=sample):
                proc = run(sample)
                self.assertEqual(proc.returncode, 1, f"flagged: {sample!r}")

    def test_finds_transient_line_buried_in_noise(self) -> None:
        log = (
            "Run actions/checkout@v4\n"
            "Syncing repository\n"
            "curl: (56) Recv failure: Connection reset by peer\n"
            "cleaning up\n"
        )
        self.assertEqual(run(log).returncode, 0)

    def test_empty_input_is_not_transient(self) -> None:
        self.assertEqual(run("").returncode, 1)

    def test_patterns_file_append_adds_custom_signature(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("# custom\nwidget service returned garbage\n")
            extra = fh.name
        try:
            self.assertEqual(
                run(
                    "widget service returned garbage", "--patterns-file", extra
                ).returncode,
                0,
            )
            # built-ins still active in append mode
            self.assertEqual(
                run(
                    "curl: (6) Could not resolve host", "--patterns-file", extra
                ).returncode,
                0,
            )
        finally:
            Path(extra).unlink()

    def test_patterns_file_replace_drops_builtins(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("widget service returned garbage\n")
            extra = fh.name
        try:
            self.assertEqual(
                run(
                    "curl: (6) Could not resolve host",
                    "--patterns-file",
                    extra,
                    "--mode",
                    "replace",
                ).returncode,
                1,
            )
            self.assertEqual(
                run(
                    "widget service returned garbage",
                    "--patterns-file",
                    extra,
                    "--mode",
                    "replace",
                ).returncode,
                0,
            )
        finally:
            Path(extra).unlink()

    def test_invalid_custom_pattern_is_skipped_not_fatal(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("(unclosed group\n")
            extra = fh.name
        try:
            proc = run("curl: (6) Could not resolve host", "--patterns-file", extra)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("skipping invalid pattern", proc.stderr)
        finally:
            Path(extra).unlink()


if __name__ == "__main__":
    unittest.main()
