# Updating and removing an installation

The beta has no automatic updater. The Python environment owns the installed code;
your TOML configurations, reports and optional pilot data remain separate. Review the
[compatibility policy](releases.md) before changing versions.

## Update using a reviewed artifact

1. Record the current version with `python -m lynvera_ragparity version` and retain the
   exact old wheel or source revision if you may need to return to it.
2. Obtain the intended reviewed wheel or source archive and check it against that
   candidate's `SHA256SUMS`. The final preparation also supplies `BUILD_INFO.json` with
   its source commit. A checksum is not an independent signature.
3. Create a new environment using an unused directory name. Install the new package
   there and run `python -m pip check`, the memory example and a controlled application
   audit before switching your own commands to it.
4. Retain the previous environment and original configuration until the replacement is
   verified. Update configuration or report consumers only when migration notes require it.

On macOS or Linux, with the reviewed wheel in the current directory:

```bash
python3 -m venv .venv-next
.venv-next/bin/python -m pip install --upgrade 'pip>=26.2,<27'
.venv-next/bin/python -m pip install ./lynvera_ragparity-0.2.0b1-py3-none-any.whl
.venv-next/bin/python -m pip check
.venv-next/bin/python -m lynvera_ragparity version
```

Choose another directory if `.venv-next` already exists. On PowerShell, use
`py -3.12 -m venv .venv-next` and `.venv-next\Scripts\python.exe` for the Python commands.
Install the `postgres` extra separately if your application needs it. Neither example
starts a database, chat or background service.

For source installations, select a reviewed commit or release tag before building.
Moving `main` can contain later work; record the actual commit rather than assuming
that two checkouts with the same branch name contain the same code. A prepared local
candidate is not a published GitHub Release.

## Return to a previous version

Use the retained environment or install the previously reviewed wheel into another
clean environment. Apply the appropriate configuration and report-schema compatibility
notes. Replacing code does not reverse changes you made to your application's source
or index, and older report readers may not accept newer schemas. Keep the original
reports instead of overwriting them during validation.

## Remove only the package

In the selected environment:

```bash
python -m pip uninstall lynvera-ragparity
```

This removes the distribution's installed files and command entry point. It does not
delete your TOML files, reports, databases, source checkout, environments or optional
pilot data. Dependencies installed alongside it can remain in the environment.

The core registers no operating-system service or listener. If you ran an experimental
pilot, use that pilot's documented stop command before separately deciding what data
to retain. Do not delete its data directory as an installation-repair step.

[Back to documentation](README.md).
