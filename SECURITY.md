# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

**Note:** As this project is in early development (0.1.x), we recommend always using the latest release.

## Reporting a Vulnerability

We take the security of httptap seriously. If you discover a security vulnerability, please follow these guidelines:

### **Please DO NOT**

- ❌ Open a public GitHub issue
- ❌ Post details on social media
- ❌ Share vulnerability details publicly before a fix is available

### **Please DO**

**Report privately via GitHub Security Advisories**
- Go to: https://github.com/ozeranskii/httptap/security/advisories/new
- Click "Report a vulnerability"
- Provide detailed information (see below)

### What to Include in Your Report

A good security report should include:

- **Description**: Clear description of the vulnerability
- **Impact**: What could an attacker achieve?
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Proof of Concept**: Code snippet or example demonstrating the vulnerability
- **Affected Versions**: Which versions are impacted?
- **Suggested Fix**: (Optional) Proposed solution or patch
- **Environment**: Python version, OS, relevant dependencies

**Example Template:**

```
## Vulnerability Description
[Describe the security issue]

## Impact
[What can an attacker do?]

## Steps to Reproduce
1. [First step]
2. [Second step]
3. [Result]

## Proof of Concept
Your PoC code here
```

## Affected Versions
- Version X.Y.Z
- All versions >= X.Y.Z

## Suggested Fix
[Your suggestion if you have one]

## Environment
- Python: 3.10-3.15
- OS: macOS/Linux/Windows
- httptap version: X.Y.Z

## Response Timeline

We are committed to responding promptly to security reports:

| Stage                        | Timeline                                              |
|------------------------------|-------------------------------------------------------|
| **Initial Response**         | Within 48 hours                                       |
| **Vulnerability Assessment** | Within 7 days                                         |
| **Fix Development**          | Within 30 days (severity dependent)                   |
| **Patch Release**            | Immediately after fix is ready                        |
| **Public Disclosure**        | After patch is released and users have time to update |

### Severity Levels

We assess vulnerabilities using the following criteria:

- **Critical**: Remote code execution, authentication bypass, data loss
- **High**: Information disclosure, privilege escalation
- **Medium**: Denial of service, non-critical information disclosure
- **Low**: Minor security improvements

Response times may be faster for Critical and High severity issues.

## Security Update Process

When a security vulnerability is fixed:

1. **Private Fix**: We develop and test the fix privately
2. **Security Advisory**: We create a GitHub Security Advisory
3. **Patch Release**: We release a new version with the fix
4. **Changelog Update**: We document the fix in CHANGELOG.md
5. **User Notification**: We notify users via:
   - GitHub Release notes
   - Security Advisory
   - Dependabot alerts (for users using our package)

## Security Best Practices for Users

### Installation

Always install from trusted sources:

```bash
# ✅ Good: Install from PyPI
pip install httptap

# ✅ Good: Install specific version
pip install httptap==X.Y.Z

# ⚠️ Caution: Verify source before installing from git
pip install git+https://github.com/ozeranskii/httptap.git
```

### Dependency Management

- **Use lockfiles**: `uv.lock`, `requirements.txt`, or `poetry.lock`
- **Pin versions**: Specify exact versions in production
- **Regular updates**: Keep dependencies up to date
- **Security audits**: Run `pip-audit` or similar tools

```bash
# Check for known vulnerabilities
uv tool install pip-audit
uv tool run pip-audit

# Update dependencies
uv lock --upgrade
```

### Safe Usage

httptap is designed for network diagnostics. Follow these guidelines:

#### ✅ **Safe Use Cases**

- Diagnosing your own applications
- Testing APIs you own or have permission to test
- Network performance analysis of authorized endpoints
- Development and debugging

#### ⚠️ **Use Responsibly**

- Always get permission before testing third-party services
- Respect rate limits and terms of service
- Don't use for unauthorized security testing
- Be mindful of sensitive data in logs and output

#### 🔒 **Handle Sensitive Data**

```bash
# ❌ Bad: Exposing sensitive headers in logs
httptap https://api.example.com -H "Authorization: Bearer secret_token"

# ✅ Good: Headers are automatically masked in logs
# The tool masks Authorization, Cookie, and other sensitive headers
```

### Environment Variables

If you use environment variables for configuration, protect them:

```bash
# ✅ Good: Use .env file (add to .gitignore)
echo "API_KEY=secret" > .env

# ❌ Bad: Hardcoding secrets in scripts
export API_KEY="secret_token"  # Don't commit this
```

## Security Features

httptap includes several security features:

### 1. **Automatic Header Masking**

Sensitive headers are automatically masked in output:
- `Authorization`
- `Cookie`
- `Set-Cookie`
- `X-API-Key`
- And other authentication headers

### 2. **TLS Certificate Validation**

- TLS certificates are validated by default
- Certificate information is displayed for transparency
- Warnings are shown for expiring certificates

### 3. **No Data Collection**

- httptap does not collect or transmit telemetry
- All operations are local
- Network requests only go to user-specified URLs

### 4. **Input Validation**

- URL validation prevents malformed requests
- Header validation prevents injection attacks
- Timeout controls prevent resource exhaustion

## Known Security Considerations

### Network Tool Nature

httptap is a network diagnostic tool that makes HTTP(S) requests. Be aware:

- **DNS Resolution**: The tool resolves DNS names and may reveal internal network topology
- **TLS Inspection**: TLS connection details are displayed, including certificate information
- **Request Timing**: Detailed timing data may reveal network architecture
- **Error Messages**: Error messages may contain network information

**Recommendation**: Use in trusted networks. Be cautious when testing production systems.

### TLS Protocol Versions

**Important**: httptap intentionally accepts all TLS versions (including TLSv1.0 and TLSv1.1) to enable diagnosis of legacy servers.

**Why this is safe:**
- httptap is a **diagnostic tool**, not a production application
- It does not transmit sensitive data (passwords, tokens, PII)
- The purpose is to **inspect** TLS connections, not to secure them
- Rejecting old TLS versions would make the tool useless for troubleshooting legacy systems

**Security implications:**
- ✅ Safe: Diagnosing your own legacy APIs
- ✅ Safe: Testing connectivity to third-party services
- ⚠️ Caution: Do not use httptap to transmit sensitive authentication credentials to servers using TLSv1.0/1.1
- ⚠️ Caution: The tool will connect to any server, regardless of TLS version

**If you need to enforce minimum TLS version** for your own servers, httptap will help you identify which servers need upgrading.

### Dependencies

We regularly monitor dependencies for security vulnerabilities:

- **Automated Scans**: Weekly `pip-audit` runs in CI
- **Dependabot**: Automatic dependency updates
- **Manual Review**: Major updates are reviewed before merging

Current security-relevant dependencies:
- `httpx[http2]` - HTTP client (handles network requests)
- `dnspython` - DNS resolution
- `rich` - Terminal output (display only)

## Vulnerability Disclosure Policy

### Our Commitment

- We will acknowledge your report within 48 hours
- We will keep you informed of our progress
- We will credit you in the security advisory (unless you prefer to remain anonymous)
- We will not take legal action against security researchers who:
  - Report vulnerabilities responsibly
  - Don't exploit vulnerabilities beyond proof-of-concept
  - Don't access, modify, or delete user data
  - Keep vulnerability details confidential until fixed

### Public Disclosure

We follow **coordinated disclosure**:

1. **Private Period**: 90 days from initial report (or until fix is deployed)
2. **Public Advisory**: Published after users have time to update
3. **CVE Assignment**: For medium+ severity vulnerabilities
4. **Credit**: Security researcher credited in advisory

## Security-Related Configuration

### Recommended pyproject.toml settings

If using httptap as a dependency:

```toml
[tool.uv]
# Use locked dependencies for reproducible builds
locked = true

[dependency-groups]
security = [
    "pip-audit>=2.9.0",
]
```

### CI/CD Security

Our CI/CD pipeline includes:

- ✅ Automated security scanning (`pip-audit`)
- ✅ Dependency vulnerability checks (Dependabot)
- ✅ Code quality checks (Ruff with security rules)
- ✅ Type checking (mypy for type safety)

## Resources

### Security Tools

- [pip-audit](https://pypi.org/project/pip-audit/) - Scan Python dependencies
- [safety](https://pypi.org/project/safety/) - Alternative dependency scanner
- [bandit](https://pypi.org/project/bandit/) - Python code security scanner

### Documentation

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [GitHub Security Features](https://docs.github.com/en/code-security)

### External Security Audits

We welcome external security audits. If you're interested in conducting a formal audit, please contact the maintainers.

## Hall of Fame

We acknowledge security researchers who have responsibly disclosed vulnerabilities:

<!--
- [Name/Handle] - [Date] - [Brief description]
-->

*No vulnerabilities have been reported yet.*

---

**Thank you for helping keep httptap and its users safe!**

For non-security issues, please use [GitHub Issues](https://github.com/ozeranskii/httptap/issues).
