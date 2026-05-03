# seo-audit (paid)

Runs a full technical and on-page audit of a client site. Crawls the
target domain through whichever fetch backend the operator has wired up,
flags broken links, missing metadata, slow pages, and duplicate content,
and writes a remediation plan ranked by traffic impact.

## Tier
Paid — included in every paid bundle.

## Triggers
The agent invokes this skill when the operator asks for an audit, a site
crawl, a technical review, or a top-issues list.

## Inputs
- The target site root.
- Crawl depth — pages or hops.
- A scope — full site, single section, or a list of priority paths.

## Outputs
- A ranked remediation list in the operator's reports directory.
- A summary scorecard suitable for the client report skill.

## Compatibility
Hermes default; OpenClaw fork; BYOA Codex; BYOA Claude Code.
