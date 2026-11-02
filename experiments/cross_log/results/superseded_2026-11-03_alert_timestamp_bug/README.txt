SUPERSEDED - do not cite.

These Stage 3, Stage 4 and robustness outputs were produced with a bug in
src/zeek_io.py read_eve(): alert timestamps were divided by 1e9 assuming
nanosecond datetimes, but pandas 3 parses them at microsecond resolution, so
every Suricata alert time was 1,000x too small (e.g. 1.547e6 instead of
1.547e9 s). Effects: all alert window features were zero (conditions C and D
had no alert information), and Stage 3 linking placed alert-containing flow
groups in wrong time buckets. Label matching, DNS features and the ablation
were not affected. Found 2026-11-03 during the robustness analyses; fixed in
zeek_io.py with a regression test (tests/test_zeek_io.py). All outputs were
regenerated with the same pre-registered design. See RUN_LOG.md.
