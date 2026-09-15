# Canonical Identity v1

`elpis.canonical_identity` is the canonical byte and digest contract for new
cross-component content identities.

## Canonical byte form

- dictionaries require string keys and are key-sorted;
- tuples and lists become JSON arrays;
- dataclasses normalize through their fields;
- `Enum` values normalize through `.value`;
- `bytes` normalize to `{"__bytes__":"<lowercase hex>"}`;
- strings are emitted as UTF-8 with `ensure_ascii=False`;
- separators are compact `,` and `:`;
- NaN and infinities are rejected.

## Domain framing

`UTF8(domain) || 0x00 || canonical_json_bytes(payload)`

The digest is lowercase SHA-256 hex.

## Nonclaims

This is deterministic content identity/integrity only. It is not
authentication, authorization, provenance, or issuer proof.

## Historical identities

Existing versioned digest namespaces are not rewritten by this contract.
Changing an already-persisted digest algorithm in place would silently change
object identity. Each historical namespace must migrate explicitly across a
protocol/schema version boundary with compatibility evidence.

New cross-component identity comparisons must use this module rather than
redeclaring JSON or domain-framing rules.
