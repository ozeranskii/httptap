# VEX (Vulnerability Exploitability eXchange) documents

This directory holds the project's VEX document
([`httptap.openvex.json`](./httptap.openvex.json)) in the
[OpenVEX](https://github.com/openvex/spec) format.

A VEX document describes, for each known vulnerability that has been
reported against one of the project's dependencies, whether the project
itself is actually affected. Automated scanners read VEX alongside the
SBOM to suppress false-positive alerts when the vulnerable code path
is not reachable from `httptap`.

## When to update

Open a pull request touching `httptap.openvex.json` whenever:

- A new CVE is published against a direct or transitive dependency of
  `httptap` (watch GitHub Security Advisories and Dependabot alerts).
- An existing VEX statement needs to be revised (e.g., status changes
  from `under_investigation` to `not_affected` after analysis).

Always bump the top-level `"version"` field and the `"timestamp"`
field to the current UTC time when you amend the document, per the
OpenVEX specification.

## Status and justification vocabulary

Each entry uses one of four OpenVEX statuses:

| Status                | Meaning                                                      |
|-----------------------|--------------------------------------------------------------|
| `not_affected`        | httptap is not affected; a justification is required.        |
| `affected`            | httptap is affected; an `action_statement` should follow.    |
| `fixed`               | httptap released a fix; point at the fixed version.          |
| `under_investigation` | Analysis in progress.                                        |

For `not_affected`, the OpenVEX vocabulary of justifications is:

- `component_not_present`
- `vulnerable_code_not_present`
- `vulnerable_code_not_in_execute_path`
- `vulnerable_code_cannot_be_controlled_by_adversary`
- `inline_mitigations_already_exist`

## Example statement

```json
{
  "vulnerability": {"name": "CVE-2099-0001"},
  "products": [
    {
      "@id": "pkg:pypi/httptap@0.4.8",
      "subcomponents": [{"@id": "pkg:pypi/httpx@0.28.1"}]
    }
  ],
  "status": "not_affected",
  "justification": "vulnerable_code_not_in_execute_path",
  "impact_statement": "httptap does not call the vulnerable API."
}
```

## Distribution

The VEX document is attached to every GitHub Release alongside the
CycloneDX and SPDX SBOMs, so end-users can verify the contents
without cloning the repository:

- [Latest release assets](https://github.com/ozeranskii/httptap/releases/latest)

Verification:

```shell
gh release download v0.4.8 --pattern 'httptap*.openvex.json'
jq . httptap-0.4.8.openvex.json
```
