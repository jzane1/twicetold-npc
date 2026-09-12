# Provenance — candidates-2026-08-07.jsonl labels

**Labeled:** 2026-08-12, by a single blind reference pass of **Claude Fable 5**
(`claude-fable-5`), per the dated "Gold-label workaround + measurement-line rulings —
2026-08-12" entry in `docs\decisions.md` (Jack ruled the single model pass over a
three-rater panel; hand-labeling was unavailable).

**Blindness protocol:** the labeler was a fresh-context subagent whose prompt contained
ONLY the three rubric criteria (sf-v1 / abst-v1 / rf-v1, verbatim from
`app\eval_judge.py`, minus the judge's output-format sentence) and an isolated copy of
this file's 78 blind rows. It received no artifact, no judge verdicts, and no aggregate
verdict distributions, and was instructed to read nothing else. Labels were merged back
mechanically (`load_gold` → fill `label` → `gold_line`), vocabulary-validated before
write.

**Epistemic status:** these are strong-model reference labels, not human gold.
`agreement` against them measures judge-vs-reference-model concordance. The judge is
Opus 4.8 (a different model class — the fork-3 self-agreement logic applied to the
rater); the compare arms (haiku, sonnet-5) were also excluded from the rater choice.

**Reference-label marginals:** selective_forgetting 20 pass / 4 fail; abstention
23 pass / 1 fail; reconstruction_faithfulness 30 supported / 0 unsupported.

**Jack's standing override:** any row Jack re-labels wins over this pass; re-run
`agreement` after (seconds, offline). The join target is the judged-run artifact
(`run-2026-08-07-judged-artifact.json`), kept in the local eval record, not in the
public tip.
