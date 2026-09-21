# Invalid command-line values

Invalid `--cacert`, `--proxy`, and `--method` values are usage errors and must
return exit code 64. Exit code 70 is reserved for unexpected internal failures;
keeping the distinction lets scripts report a bad invocation separately from a
tool defect.
