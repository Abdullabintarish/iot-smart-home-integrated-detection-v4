CONTROLLED ABLATION - HOW TO RUN

1. Copy run_ablation.py into your code folder, next to run_pipeline.py.
   Copy test_ablation.py into code\tests\.
2. Keep data\processed from the verified run. This script needs
   data\processed\stage3_events and data\processed\stage2_feature_plan.csv.
   If they are missing, re-run the pipeline first.
3. In PowerShell, from the code folder, test it:
      .venv\Scripts\python.exe -m unittest tests.test_ablation
4. Quick check (one seed, 300 s window):
      .venv\Scripts\python.exe run_ablation.py --seeds 42 --windows 300
   Check results_ablation\checks.json before going further:
      groups_at_300s must be 704,090 and n_novel must be 1,463,143.
   If either number differs, stop. The saved data are not the Run B data.
5. Full run (5 seeds, 5 windows, 300 trees):
      .venv\Scripts\python.exe run_ablation.py

It does not change results\, models\ or any Run B file. Output goes to
results_ablation\. Send me these four files and I will write them into the thesis:
   ablation_summary.csv, ablation_results.csv, bootstrap.json, checks.json

Tested here on synthetic data only, on Python 3.13. It has not been run on your
real data or on Python 3.15. Decide the feature sets, windows and seeds with
Dr. Shah before the full run, and report all of them, whichever way they turn out.
