# Forge — Vision

*Last updated: April 21, 2026*

Forge was originally scoped as an internal AI tool marketplace with an automated governance review pipeline — an app store for your company's AI tools, with governance built in. The catalog and 6-agent review are still core mechanics, but they're not the product anymore.

**The vision has expanded: Forge is the platform that makes Claude Code usable at scale inside a company.** Governance is still the mechanism; the product is enablement. Every "New Claude Code Project" click is an onboarding moment — someone who doesn't know where to start gets a scaffolded, opinionated project with the company's skills and governance baked in from second zero. The catalog and review pipeline exist to feed that scaffolding with vetted skills, not the other way around.

The build methodology has shifted along with the product. The old pattern — spawn multiple Claude Code terminals and have a coordinator agent orchestrate them by appending status blocks to PROGRESS.md — is archived under `_archive/`. The current pattern is **one Claude Code session per project**, with skills auto-scaffolded at init time and a validator agent gating what ships to the catalog. The codebase is now built with the same pattern it delivers.

Brand-kit enforcement (see `docs/future/brand-kit-enforcement.md`) is the next layer: the same governance mechanism extended from security scanning to visual consistency and iframe rendering. Same pipeline, new dimension — an app that ships with the wrong fonts or color tokens gets caught by the same review that catches unsafe eval patterns.
