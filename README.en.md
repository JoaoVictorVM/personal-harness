# Personal Harness

Personal Harness is a local-first, open-source workflow for AI-assisted development with PRDs, feature specs, recoverable state, budget controls, quality gates and Orca-managed worktrees.

## Profiles

- `manual-classic` preserves the detailed interview and G1 to G4 workflow.
- `lean` uses progressive context, feature smoke checks and final review.
- `strict` performs deeper validation and review for each feature.

## Install into a project

```bash
git clone <repository-url> personal-harness
python personal-harness/scripts/install.py --target /path/to/project
```

The installer performs a complete conflict check before writing and never overwrites existing files. It runs the local bootstrap by default.

Then, from the consumer project:

```bash
python .harness/scripts/harness.py doctor
```

Do not run `.harness/scripts/bootstrap.py` inside the Personal Harness source repository. It is intended for consumer projects and adds local harness files to their Git exclusion file.

## Repository checks

```bash
python scripts/repository_check.py
python .harness/scripts/self_test.py
python .harness/scripts/harness.py doctor
python .harness/scripts/model_router.py validate
```

See the [Portuguese README](README.md) and [.harness/README.md](.harness/README.md) for the full workflow.

## License

MIT. See [LICENSE](LICENSE).
