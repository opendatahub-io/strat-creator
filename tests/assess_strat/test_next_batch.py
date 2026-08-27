"""Tests for next_batch.py — queue popping and output format."""
import os

from conftest import run_script


class TestNextBatch:
    def _write_queue(self, run_dir, keys):
        queue = os.path.join(str(run_dir), "queue.txt")
        with open(queue, "w") as f:
            for k in keys:
                f.write(k + "\n")

    def _read_queue(self, run_dir):
        queue = os.path.join(str(run_dir), "queue.txt")
        with open(queue) as f:
            return [line.strip() for line in f if line.strip()]

    def _parse_batch_output(self, stdout):
        lines = stdout.strip().splitlines()
        kv = {}
        keys = []
        past_separator = False
        for line in lines:
            if line.strip() == "---":
                past_separator = True
                continue
            if not past_separator and "=" in line:
                k, _, v = line.partition("=")
                kv[k] = v
            elif past_separator:
                keys.append(line.strip())
        return kv, keys

    def test_pop_batch(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        all_keys = [f"RHAISTRAT-{i}" for i in range(1, 11)]
        self._write_queue(run_dir, all_keys)

        result = run_script("next_batch.py", [str(run_dir), "--batch-size", "3"])
        assert result.returncode == 0

        kv, keys = self._parse_batch_output(result.stdout)
        assert kv["BATCH_SIZE"] == "3"
        assert kv["REMAINING"] == "7"
        assert len(keys) == 3
        assert keys == all_keys[:3]

        remaining = self._read_queue(run_dir)
        assert len(remaining) == 7
        assert remaining == all_keys[3:]

    def test_pop_all_when_smaller_than_batch(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        all_keys = ["RHAISTRAT-1", "RHAISTRAT-2"]
        self._write_queue(run_dir, all_keys)

        result = run_script("next_batch.py", [str(run_dir), "--batch-size", "10"])
        assert result.returncode == 0

        kv, keys = self._parse_batch_output(result.stdout)
        assert kv["BATCH_SIZE"] == "2"
        assert kv["REMAINING"] == "0"
        assert len(keys) == 2

        remaining = self._read_queue(run_dir)
        assert remaining == []

    def test_missing_queue_file(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        result = run_script("next_batch.py", [str(run_dir)])
        assert result.returncode == 0

        kv, keys = self._parse_batch_output(result.stdout)
        assert kv["BATCH_SIZE"] == "0"
        assert kv["REMAINING"] == "0"
        assert keys == []

    def test_default_batch_size_30(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        all_keys = [f"RHAISTRAT-{i}" for i in range(1, 51)]
        self._write_queue(run_dir, all_keys)

        result = run_script("next_batch.py", [str(run_dir)])
        assert result.returncode == 0

        kv, keys = self._parse_batch_output(result.stdout)
        assert kv["BATCH_SIZE"] == "30"
        assert kv["REMAINING"] == "20"
        assert len(keys) == 30

    def test_sequential_pops_drain_queue(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        self._write_queue(run_dir, ["K-1", "K-2", "K-3", "K-4", "K-5"])

        # Pop 2
        run_script("next_batch.py", [str(run_dir), "--batch-size", "2"])
        assert self._read_queue(run_dir) == ["K-3", "K-4", "K-5"]

        # Pop 2 more
        run_script("next_batch.py", [str(run_dir), "--batch-size", "2"])
        assert self._read_queue(run_dir) == ["K-5"]

        # Pop remaining
        run_script("next_batch.py", [str(run_dir), "--batch-size", "2"])
        assert self._read_queue(run_dir) == []
