# Trusted content packs

This directory is the default administrator-owned root for installed D&D
engine content packs.

Each immediate child pack must contain a validated `content-pack.toml`, a
declared Python package, and only trusted code/assets. Pack discovery happens
once during process startup; changes require a restart. The gameplay API does
not install, upload, enable, disable, or delete packs.

Additional absolute roots may be supplied with the platform path separator in
`DND_CONTENT_PACK_ROOTS`. A malformed, incompatible, or partially loadable pack
fails startup instead of being skipped.
