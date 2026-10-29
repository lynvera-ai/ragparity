# External beta review

Independent acceptance is pending. Maintainer tests and application pilots do not
replace a different person installing and evaluating the package.

Follow [Getting started](getting-started.md) in a new environment. Verify the installed
version, the initial PASS, the deliberate version mismatch and both report formats.
Then, if appropriate, connect a small metadata projection from an application you own
using a SELECT-only account. Record the scope and expected outcomes before running.
Do not start with private documents or production changes.

Report whether known matching records pass, known differences fail, and missing evidence
is inconclusive. An application chat can return a poor answer while its index metadata
is consistent. Review those two outcomes separately.

Copy the following into a GitHub issue or send it to the maintainer listed in the README.
Do not include credentials, database URLs, document bodies or unredacted reports. Security
problems follow [the private reporting policy](../SECURITY.md).

```text
Version and installation source:
Operating system, architecture and Python version:
Installation completed: yes / no
Initial example returned PASS: yes / no
Deliberate mismatch returned FAIL: yes / no
JSON and HTML reports opened: yes / no
Application tested, if any:
Source/index type and approximate metadata record count:
Expected result and observed status/exit code:
Minimal sanitized reproduction:
Error message, with private values removed:
Installation time and observed resource issues, if measured:
Documentation that was unclear:
```

No external reviewer results have been received as part of this preparation. Do not
mark this acceptance complete until actual observations are recorded with reviewer
consent and appropriate privacy controls.
