.PHONY: verify test replay capture-fixture

verify:
	python tools/verify.py

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

replay:
	PYTHONPATH=src python tools/replay_run.py experiments/evidence_replay_example

capture-fixture:
	PYTHONPATH=src python tools/capture_cs.py --input experiments/phase0_cs/fixtures/bbo_vendor_smoke.log --run-root /tmp/putttrack-runs --run-id fixture --anchor-id A --reflector-id ball-reference --truth-distance-m 1.0 --condition fixture --anchor-config configs/anchors/phase0.example.json --max-records 2
