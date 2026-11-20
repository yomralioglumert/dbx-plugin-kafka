# Alba Kafka Connect review candidate

Version: `0.1.58-alba.1`. This is a downstream build, not an official DBX Store
release. Source contribution: https://github.com/jinpy666/dbx-plugin-kafka/pull/86.
The upstream plugin ID stays `io.dbx.kafka`; the publisher and source identify
this fork explicitly. Existing MIT attribution is preserved in every package.

Build the frontend from the pinned frontend package manager, then invoke
`scripts/build_alba_candidates.py` with explicit packager, signing-environment
and empty output directory arguments. The reviewed standalone signer is
`t8y2/dbx` tag `plugin-cli-v0.1.2`, commit
`68afe616937dbbbf1d3ea9f15af4a27bdf378412`,
`plugins/sdk/packager`. Compile it with its own `Cargo.lock`.

The helper cross-compiles Go payloads for the five existing targets, packages
with the reviewed signer, preserves checksums, signs with the private Alba key,
and emits artifact metadata and a public-key record. It never installs keys
or modifies a server. Native runtime CI for every target remains separate
from successful cross-compilation and signature/checksum checks. Never put the
private signing environment file in Git, artifacts, logs or release metadata.

Repository ID: `alba-kafka`; signing key ID: `alba.dbx.kafka.release`. Publish
only the generated public-key record through a trusted operator channel.
A private catalog must identify the fork and set `verified: false`; it must not
claim the official DBX Store signing identity.

Before any HEL1 rollout, pass the isolated DBX Web install/secret/persistence
checks, inspect the actual guest architecture/version/capacity without printing
container environment values, take a consistent backup, and preserve the old
plugin and whole DBX data volume for rollback. Keep the portal authentication,
private networking and read-only production policies. The Kafka UI remains.

Live deployment is blocked until the HEL1 SSH host trust and approved operator
access are resolved. No production credentials or brokers are used by tests.
Do not treat this review candidate as deployed or full Kafbat feature parity.
