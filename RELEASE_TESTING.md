# Release testing

A successful build on the maintainer’s Mac does not establish that an app is self-contained. Test the exact ZIP intended for release on a clean machine or virtual machine without Homebrew, Python, pip, or other developer tools.

1. Record the app version, ZIP filename and checksum, OS version, and CPU architecture.
2. Extract the ZIP and launch the app as an ordinary user.
3. Exercise each major feature, including a typical file or network workflow, and verify saved output.
4. Inspect executable and library dependencies for non-system paths. Test each supported architecture and platform separately.
5. Record the result and any missing dependencies or failures before publishing.

A Windows build must be built and tested on Windows.
