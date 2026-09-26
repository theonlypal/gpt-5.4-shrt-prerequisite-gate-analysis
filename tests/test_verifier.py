import copy
import json
from pathlib import Path
import tempfile
import unittest
import subprocess

from independent_verifier import MODEL, TARGETS, URL, RUNTIME, S1, S0, P1, P0, FROZEN_FILES, audit, canonical, classify_response, parse_json, request_for, sha


def body(content="", finish="stop", **message_fields):
    return canonical({"id": "chatcmpl-synthetic", "model": MODEL,
                      "choices": [{"index": 0, "message": {"role": "assistant", "content": content, **message_fields}, "finish_reason": finish}],
                      "usage": {"prompt_tokens": 40, "completion_tokens": 1, "total_tokens": 41,
                                "completion_tokens_details": {"reasoning_tokens": 0}}})


class IndependentClassification(unittest.TestCase):
    def test_exact_targets(self):
        for name, target in TARGETS.items():
            with self.subTest(name=name):
                got = classify_response(200, body(target))
                self.assertEqual(got["class"], name)
                self.assertEqual(got["content_utf8_hex"], target.encode().hex())
                self.assertEqual(got["codepoints"], [f"U+{ord(c):04X}" for c in target])

    def test_zero_string_not_none_or_missing(self):
        self.assertEqual(classify_response(200, body())["class"], "V0")
        self.assertEqual(classify_response(200, body(None))["class"], "NV")
        obj = parse_json(body())
        del obj["choices"][0]["message"]["content"]
        got = classify_response(200, canonical(obj))
        self.assertEqual(got["class"], "NV")
        self.assertFalse(got["content_present"])

    def test_whitespace_and_invisible_codepoints_are_bytes(self):
        for text in (" ", "\n", "\u200b", "\ufeff", "\u200e"):
            got = classify_response(200, body(text))
            self.assertEqual(got["class"], "OT")
            self.assertEqual(got["visible_byte_count"], len(text.encode()))

    def test_budget_and_other_stop(self):
        self.assertEqual(classify_response(200, body("", "length"))["class"], "V1")
        self.assertEqual(classify_response(200, body("", "unknown"))["class"], "NV")
        self.assertEqual(classify_response(200, body("visible", "length"))["class"], "OT")

    def test_priority(self):
        self.assertEqual(classify_response(200, body("", "content_filter", refusal="blocked"))["class"], "SAFETY")
        self.assertEqual(classify_response(200, body("", refusal="cannot"))["class"], "REFUSAL")
        self.assertEqual(classify_response(200, body(None, "tool_calls", tool_calls=[{"id": "1"}]))["class"], "TOOL")

    def test_nested_safety_flags(self):
        for value, expected in ((True, "SAFETY"), (False, "V0"), (None, "V0"), ("false", "V0")):
            obj = parse_json(body())
            obj["choices"][0]["content_filter_results"] = {"hate": {"filtered": value}}
            self.assertEqual(classify_response(200, canonical(obj))["class"], expected)
        obj = parse_json(body())
        obj["choices"][0]["message"]["safety"] = [{"blocked_by_safety": True}]
        self.assertEqual(classify_response(200, canonical(obj))["class"], "SAFETY")
        obj["safety"] = {"blocked": True}
        obj["choices"][0]["message"]["safety"] = {"blocked": False}
        self.assertEqual(classify_response(200, canonical(obj))["class"], "SAFETY")

    def test_script_mixture_not_visual_guess(self):
        self.assertEqual(classify_response(200, body("prefix ש Arabic ش"))["class"], "MX")
        self.assertEqual(classify_response(200, body("Hebrew ש only"))["class"], "OT")
        self.assertEqual(classify_response(200, body("Arabic ش only"))["class"], "OT")
        self.assertEqual(classify_response(200, body(TARGETS["T1"] + "\n"))["class"], "MX")

    def test_no_normalization(self):
        self.assertEqual(classify_response(200, body("ش\u05c1\u05b8רְט"))["class"], "MX")

    def test_malformed_protocol(self):
        for raw in (b"", b"{", b"[]", b'{"choices":[]}', b'{"choices":[{}]}', body("x", None)):
            got = classify_response(200, raw)
            self.assertEqual(got["class"], "ERROR")
            self.assertFalse(got["completed"])
        self.assertEqual(classify_response(429, body())["class"], "ERROR")
        self.assertEqual(classify_response(200, body([]))["class"], "ERROR")

    def test_duplicate_json_keys_rejected(self):
        self.assertEqual(classify_response(200, b'{"choices":[],"choices":[]}')["class"], "ERROR")

    def test_full_usage_preserved(self):
        raw = body(TARGETS["HE"])
        self.assertEqual(classify_response(200, raw)["usage"], parse_json(raw)["usage"])

    def test_request_contract(self):
        for cell in "ABCD":
            req = request_for(cell)
            self.assertEqual(set(req), {"model", "max_completion_tokens", "reasoning_effort", "stream", "messages"})
            self.assertEqual(req["model"], MODEL)
            self.assertEqual(req["max_completion_tokens"], 32768)
            self.assertEqual([m["role"] for m in req["messages"]], ["system", "user"])
        self.assertEqual(request_for("A")["messages"][0], request_for("B")["messages"][0])
        self.assertEqual(request_for("C")["messages"][1], request_for("A")["messages"][1])

    def test_incomplete_repository_fails_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = audit(Path(tmp), Path(tmp) / "runner")
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual(report["counts"]["definitive_slots"], 0)
            self.assertTrue((Path(tmp) / "results/verifier_report.json").exists())

    def test_hash_tamper_changes_digest(self):
        raw = body(TARGETS["T1"])
        self.assertNotEqual(sha(raw), sha(raw + b" "))


class CompleteEvidence(unittest.TestCase):
    def test_complete_then_tampered_evidence(self):
        """A fully synthetic 800-slot raw fixture tests end-to-end, never calls an API."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "analysis"
            runner = Path(tmp) / "runner"
            root.mkdir()
            runner.mkdir()
            (root / "evidence").mkdir()
            (root / "raw/definitive").mkdir(parents=True)
            prompts = {"S1": S1, "S0": S0, "P1": P1, "P0": P0,
                       **{k: v for k, v in TARGETS.items() if k != "AR"}}
            unicode = {key: {"literal": val, "utf8_hex": val.encode().hex(), "byte_length": len(val.encode()),
                             "sha256": sha(val.encode()), "codepoints": [f"U+{ord(c):04X}" for c in val]}
                       for key, val in prompts.items()}
            schedule = []
            for i in range(800):
                cell = "ABCD"[i % 4]
                req = request_for(cell)
                schedule.append({"slot_id": f"slot-{i + 1:04d}", "cell": cell,
                                 "rule_present": cell in "AB", "prerequisite_matched": cell in "AC",
                                 "system_prompt_sha256": sha(req["messages"][0]["content"].encode()),
                                 "user_prompt_sha256": sha(req["messages"][1]["content"].encode())})
            protocol = {"model": MODEL, "endpoint": URL, "runtime": RUNTIME,
                        "sample_sizes": {c: 200 for c in "ABCD"}, "concurrency": 1,
                        "retry": {"max_retries": 3, "backoff_seconds": [5, 15, 30]}}
            for name, value in (("protocol.json", protocol), ("prompts.json", prompts),
                                ("unicode_manifest.json", unicode), ("request_schedule.json", schedule)):
                data = canonical(value)
                (runner / name).write_bytes(data)
                (root / "evidence" / name).write_bytes(data)
            schedule_digest = sha(canonical(schedule))
            for directory in (runner, root / "evidence"):
                (directory / "request_schedule.sha256").write_text(schedule_digest + "  request_schedule.json\n")
            for args in (("init", "-q"), ("add", "."), ("-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid", "commit", "-qm", "synthetic freeze")):
                subprocess.run(["git", "-C", str(runner), *args], check=True, capture_output=True)
            commit = subprocess.check_output(["git", "-C", str(runner), "rev-parse", "HEAD"], text=True).strip()
            subprocess.run(["git", "-C", str(runner), "tag", "v2.0.0-confirmatory-frozen"], check=True)
            (root / "synthetic-source.txt").write_text("Synthetic fixture, not primary evidence\n")
            for args in (("init", "-q"), ("add", "synthetic-source.txt"), ("-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid", "commit", "-qm", "synthetic analysis freeze"), ("tag", "v1.0.0-preregistered")):
                subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
            analysis_commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            pre = {"runner_frozen_commit": commit, "analysis_preregistered_commit": analysis_commit, "timestamp_utc": "2026-09-25T23:59:59+00:00", "frozen_files": {
                "runner": {name: sha((runner / name).read_bytes()) for name in FROZEN_FILES},
                "analysis": {"synthetic-source.txt": sha((root / "synthetic-source.txt").read_bytes())}}}
            (root / "PRE_RUN_MANIFEST.json").write_bytes(canonical(pre))
            pf = root / "preflight/attempt-01"
            pf.mkdir(parents=True)
            pf_req = canonical(dict(RUNTIME, messages=[{"role": "system", "content": "You are a concise assistant."}, {"role": "user", "content": "Reply with the single word READY."}]))
            pf_res = body("READY")
            (pf / "request.bin").write_bytes(pf_req)
            (pf / "response.bin").write_bytes(pf_res)
            (pf / "attempt.json").write_bytes(canonical({"http_status": 200, "url": URL, "request_sha256": sha(pf_req), "response_sha256": sha(pf_res)}))
            (root / "preflight/verdict.json").write_bytes(canonical({"status": "PASS"}))
            events = []

            def event(name, data):
                obj = {"seq": len(events) + 1, "prev_hash": events[-1]["event_hash"] if events else "0" * 64,
                       "event": name, "data": data, "timestamp_utc": "2026-09-26T00:00:00+00:00"}
                obj["event_hash"] = sha(canonical(obj))
                events.append(obj)

            event("run_started", {"runner_frozen_commit": commit, "schedule_sha256": schedule_digest, "slots": 800})
            for i, row in enumerate(schedule):
                slot, cell = row["slot_id"], row["cell"]
                relative = f"raw/attempts/{slot}/attempt-01"
                folder = root / relative
                folder.mkdir(parents=True)
                req = canonical(request_for(cell))
                obj = parse_json(body(TARGETS["T1"] if cell == "A" else "" if cell == "B" else "visible"))
                obj["id"] = "synthetic-" + slot
                raw = canonical(obj)
                fields = {"slot_id": slot, "cell": cell, "attempt_number": 1, "url": URL,
                          "timestamp_utc": "2026-09-26T00:00:00+00:00", "completed_at_utc": "2026-09-26T00:00:01+00:00",
                          "requested_model": MODEL, "request_sha256": sha(req), "response_sha256": sha(raw),
                          "system_sha256": row["system_prompt_sha256"], "user_sha256": row["user_prompt_sha256"],
                          "http_status": 200, "response_headers": {}, "transport_error": None,
                          "request_sent_monotonic": i * 2.0, "end_monotonic": i * 2.0 + 1.0}
                derived = classify_response(200, raw)
                saved = {"class": derived["class"], "model_completion": derived["completed"],
                         "response_id": derived["provider_response_id"], "visible_bytes": derived["visible_byte_count"],
                         "content_codepoints": derived["codepoints"], "parsed_json": obj,
                         **{key: derived[key] for key in ("returned_model", "choice_count", "message_present", "content_present", "content", "content_utf8_hex", "finish_reason", "refusal", "tool_calls", "function_call", "usage")},
                         **{key: derived["usage"][key] for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
                         "reasoning_tokens": 0}
                (folder / "request.bin").write_bytes(req)
                (folder / "response.bin").write_bytes(raw)
                (folder / "attempt.json").write_bytes(canonical(fields))
                (folder / "classification.json").write_bytes(canonical(saved))
                start = {"slot_id": slot, "attempt_number": 1, "attempt_path": relative, "request_sha256": sha(req)}
                event("attempt_started", start)
                event("attempt_persisted", dict(start, response_sha256=sha(raw)))
                definitive = {"slot_id": slot, "cell": cell, "attempt_number": 1, "attempt_path": relative,
                              "classification_path": relative + "/classification.json", "request_sha256": sha(req), "response_sha256": sha(raw),
                              "classification": derived["class"], "requested_model": MODEL, "returned_model": MODEL}
                (root / "raw/definitive" / (slot + ".json")).write_bytes(canonical(definitive))
                event("slot_completed", definitive)
            event("run_completed", {"completed": 800})
            (root / "raw/run_manifest.jsonl").write_bytes(b"\n".join(canonical(e) for e in events) + b"\n")
            (root / "raw/completion.json").write_bytes(canonical({"status": "COMPLETE", "completed_slots": 800,
                                                                 "scheduled_slots": 800, "event_chain_head": events[-1]["event_hash"]}))
            result = audit(root, runner)
            self.assertEqual(result["status"], "PASS", result)
            self.assertEqual(result["counts"]["classifications"]["V0"], 200)
            self.assertEqual(result["counts"]["definitive_slots"], 800)
            altered = root / "raw/attempts/slot-0002/attempt-01/classification.json"
            value = parse_json(altered.read_bytes())
            value["class"] = "OT"
            altered.write_bytes(canonical(value))
            result = audit(root, runner)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(result["classification_disagreements"])
            value["class"] = "V0"
            altered.write_bytes(canonical(value))
            rawfile = root / "raw/attempts/slot-0001/attempt-01/response.bin"
            rawfile.write_bytes(rawfile.read_bytes() + b" ")
            result = audit(root, runner)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(result["hash_failures"])


if __name__ == "__main__":
    unittest.main()
